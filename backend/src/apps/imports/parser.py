"""Bounded, model-independent parsing for the TB1 and TB2 Excel workbooks.

The parser deliberately does not use worksheet ``max_row`` or ``max_column``.
Several source workbooks contain formatting at Excel's last row or column, so
trusting those dimensions would turn a small import into an unbounded scan.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO, Final, Protocol

import pandas as pd  # type: ignore[import-untyped]
import pandera.pandas as pa
from openpyxl import load_workbook
from openpyxl.utils.datetime import (
    WINDOWS_EPOCH,
    from_excel,
)
from pandera.errors import SchemaErrors

type NormalizedValue = str | Decimal | date | None
type JsonScalar = str | int | float | bool | None
type WorkbookSource = str | Path | BinaryIO


class _WorksheetReader(Protocol):
    title: str

    def iter_rows(
        self,
        *,
        min_row: int,
        max_row: int,
        min_col: int,
        max_col: int,
        values_only: bool,
    ) -> Iterable[Sequence[object]]: ...

    def cell(self, row: int, column: int) -> object: ...


class WorkbookKind(StrEnum):
    """Workbook layouts currently supported by the import pipeline."""

    TB1 = "tb1"
    TB2 = "tb2"


class IssueSeverity(StrEnum):
    """Whether an issue quarantines a row or is informational."""

    WARNING = "warning"
    ERROR = "error"


class AgencySource(StrEnum):
    """Controlled origin used to resolve an agency identity."""

    NONE = "none"
    FILENAME = "filename"
    SHEET = "sheet"
    CELL = "cell"


class WorkbookParserError(Exception):
    """Base exception safe for callers to handle as an import failure."""


class InvalidWorkbookError(WorkbookParserError):
    """The supplied object is not a readable XLSX workbook."""


class UnsupportedWorkbookError(WorkbookParserError):
    """No supported TB1 or TB2 tabular layout was detected."""


class WorkbookLimitError(WorkbookParserError):
    """A configured workbook, sheet, row, or column safety limit was exceeded."""


class ParserConfigurationError(WorkbookParserError):
    """Parser limits or a controlled header override are invalid."""


class CellValueError(ValueError):
    """A non-empty cell cannot be converted to its canonical value type."""


REFERENCE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<agency_code>\d{4})/(?P<sequence>\d{3,5})/(?P<type_code>[A-Z]{1,2})/(?P<date>\d{8})$"
)


@dataclass(frozen=True, slots=True)
class CanonicalReference:
    """The governed, non-sensitive components of a request reference."""

    agency_code: str
    sequence: str
    type_code: str
    request_date: date


def parse_canonical_reference(value: object) -> CanonicalReference:
    """Parse the exact governed ``CCCC/NNN/T/DDMMAAAA`` reference format."""

    if not isinstance(value, str):
        raise CellValueError("The reference must be stored as Excel text.")
    match = REFERENCE_PATTERN.fullmatch(value)
    if match is None:
        raise CellValueError("The reference does not use the governed format.")
    try:
        embedded_date = datetime.strptime(match.group("date"), "%d%m%Y").date()
    except ValueError as exc:
        raise CellValueError("The reference contains an invalid calendar date.") from exc
    return CanonicalReference(
        agency_code=match.group("agency_code"),
        sequence=match.group("sequence"),
        type_code=match.group("type_code"),
        request_date=embedded_date,
    )


@dataclass(frozen=True, slots=True)
class ParserLimits:
    """Hard bounds used instead of potentially corrupted worksheet dimensions."""

    max_sheets: int = 64
    max_header_rows: int = 15
    max_columns: int = 64
    max_rows_per_sheet: int = 50_000
    max_total_rows: int = 100_000
    consecutive_blank_rows: int = 30

    def __post_init__(self) -> None:
        values = (
            self.max_sheets,
            self.max_header_rows,
            self.max_columns,
            self.max_rows_per_sheet,
            self.max_total_rows,
            self.consecutive_blank_rows,
        )
        if any(value <= 0 for value in values):
            raise ParserConfigurationError("All parser limits must be positive integers.")
        if self.max_columns > 16_384:
            raise ParserConfigurationError("max_columns cannot exceed the XLSX column limit.")
        if self.max_header_rows + self.max_rows_per_sheet + self.consecutive_blank_rows > 1_048_576:
            raise ParserConfigurationError("The configured row scan exceeds the XLSX row limit.")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A value-free diagnostic safe to expose in an import report."""

    code: str
    message: str
    severity: IssueSeverity
    field: str | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    column_number: int | None = None


@dataclass(frozen=True, slots=True)
class HeaderBinding:
    """Lineage from an XLSX column to one controlled canonical field."""

    column_number: int
    original_header: str
    normalized_header: str
    canonical_field: str


@dataclass(frozen=True, slots=True)
class ParsedRow:
    """One staged row, including its source coordinate and raw representation."""

    sheet_name: str
    source_row: int
    agency: str | None
    agency_source: AgencySource
    reporting_period: date | None
    data: Mapping[str, NormalizedValue]
    raw_data: Mapping[str, JsonScalar]
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        """Return whether the row has no quarantining errors."""

        return not any(issue.severity is IssueSeverity.ERROR for issue in self.issues)


@dataclass(frozen=True, slots=True)
class SheetMetadata:
    """Detected schema and bounded-scan information for one worksheet."""

    name: str
    kind: WorkbookKind
    header_row: int
    last_scanned_row: int
    columns_scanned: int
    agency: str | None
    agency_source: AgencySource
    reporting_period: date | None
    bindings: tuple[HeaderBinding, ...]
    blank_terminated: bool
    row_count: int


@dataclass(frozen=True, slots=True)
class ParsedSheet:
    """A recognized worksheet and its parsed staging rows."""

    metadata: SheetMetadata
    rows: tuple[ParsedRow, ...]
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class WorkbookMetadata:
    """Source-level metadata inferred without consulting application models."""

    source_name: str
    kind: WorkbookKind
    agency: str | None
    reporting_period: date | None
    source_sheet_count: int
    parsed_sheet_count: int


@dataclass(frozen=True, slots=True)
class BatchProfile:
    """Privacy-safe pandas/Pandera profile of the normalized batch."""

    row_count: int
    valid_row_count: int
    invalid_row_count: int
    warning_count: int
    agency_count: int
    period_count: int
    missing_required_counts: Mapping[str, int]
    schema_valid: bool


@dataclass(frozen=True, slots=True)
class ParsedWorkbook:
    """Complete parser result ready for a staging persistence service."""

    metadata: WorkbookMetadata
    sheets: tuple[ParsedSheet, ...]
    profile: BatchProfile
    issues: tuple[ValidationIssue, ...]

    @property
    def rows(self) -> tuple[ParsedRow, ...]:
        """Flatten all parsed sheet rows in deterministic workbook order."""

        return tuple(row for sheet in self.sheets for row in sheet.rows)


CANONICAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "agency",
        "reference",
        "request_date",
        "request_type",
        "amount",
        "credit_type",
        "received_at_agency_date",
        "assigned_to_gp_date",
        "gp_name",
        "visit_date",
        "status",
        "outcome_date",
        "rejection_reason",
        "activity_category",
        "counsellor_name",
    }
)

DATE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "request_date",
        "received_at_agency_date",
        "assigned_to_gp_date",
        "visit_date",
        "outcome_date",
        "decision_date",
        "disbursement_date",
        "rejection_date",
    }
)
DECIMAL_FIELDS: Final[frozenset[str]] = frozenset({"amount"})
DECIMAL_STORAGE: Final[Mapping[str, tuple[int, int]]] = {
    "amount": (18, 3),
}
REQUIRED_FIELDS: Final[Mapping[WorkbookKind, frozenset[str]]] = {
    WorkbookKind.TB1: frozenset(
        {
            "reference",
            "request_date",
            "request_type",
            "amount",
            "credit_type",
            "activity_category",
        }
    ),
    WorkbookKind.TB2: frozenset(
        {
            "reference",
            "request_date",
            "request_type",
            "amount",
            "status",
        }
    ),
}


def normalize_header(value: object) -> str:
    """Normalize accents, case, punctuation, and whitespace for alias matching."""

    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.casefold().replace("&", " et ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


TEMPLATE_HEADERS: Final[Mapping[WorkbookKind, Mapping[str, str]]] = {
    WorkbookKind.TB1: {
        "Référence de la demande": "reference",
        "Date de la demande": "request_date",
        "Type de demande": "request_type",
        "Montant demandé": "amount",
        "Type de crédit": "credit_type",
        "Catégorie d\u2019activité": "activity_category",
    },
    WorkbookKind.TB2: {
        "AGENCE": "agency",
        "Référence de la demande": "reference",
        "Date de la demande": "request_date",
        "Type de demande": "request_type",
        "Montant demandé": "amount",
        "Date réception Chef d\u2019agence": "received_at_agency_date",
        "Nom du conseiller CA/CAA": "counsellor_name",
        "Date d\u2019affectation au GP": "assigned_to_gp_date",
        "Nom du GP": "gp_name",
        "DATE VISITE CLIENT": "visit_date",
        "STATUT/ETAT DEMANDE": "status",
        "DATE DECAISSEMENT / DATE REJET": "outcome_date",
        "Motif du rejet": "rejection_reason",
    },
}
TEMPLATE_FIELDS: Final[Mapping[WorkbookKind, frozenset[str]]] = {
    kind: frozenset(headers.values()) for kind, headers in TEMPLATE_HEADERS.items()
}

_FRENCH_MONTHS: Final[Mapping[str, int]] = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
_GENERIC_SHEET_NAMES: Final[frozenset[str]] = frozenset(
    {"details", "detail", "data", "donnees", "feuil", "feuil1", "sheet", "sheet1"}
)
_GENERIC_HEADER_RE: Final[re.Pattern[str]] = re.compile(r"^(?:colonne|column)\s*\d+$")


@dataclass(frozen=True, slots=True)
class _DetectedHeader:
    row_number: int
    kind: WorkbookKind
    bindings: tuple[HeaderBinding, ...]
    original_headers: tuple[str | None, ...]
    effective_column_count: int


def _build_template_header_map(overrides: Mapping[str, str] | None) -> dict[str, str]:
    """Return the exact governed template headers.

    Header overrides previously let historical layouts masquerade as the
    versioned template. They are intentionally rejected.
    """

    if overrides:
        raise ParserConfigurationError(
            "Header overrides are not permitted for governed template uploads."
        )
    return {
        header: canonical
        for headers in TEMPLATE_HEADERS.values()
        for header, canonical in headers.items()
    }


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CellValueError("The cell contains a non-finite number.")
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    result = str(value).strip()
    return result or None


def coerce_decimal(value: object) -> Decimal | None:
    """Convert native or French-formatted numeric cells to an exact Decimal."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise CellValueError("Boolean cells are not valid decimal values.")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise CellValueError("Non-finite cells are not valid decimal values.")
        result = Decimal(str(value))
    else:
        text = str(value).strip().replace("\u00a0", "").replace("\u202f", "")
        negative_parentheses = text.startswith("(") and text.endswith(")")
        if negative_parentheses:
            text = text[1:-1]
        text = re.sub(r"(?i)\b(?:tnd|dt)\b", "", text)
        text = text.replace(" ", "").replace("'", "")
        text = re.sub(r"[^0-9,\.\-+]", "", text)
        if not text or text in {"+", "-", ".", ","}:
            raise CellValueError("The cell is not a decimal value.")

        comma_index = text.rfind(",")
        dot_index = text.rfind(".")
        if comma_index >= 0 and dot_index >= 0:
            decimal_separator = "," if comma_index > dot_index else "."
            thousands_separator = "." if decimal_separator == "," else ","
            text = text.replace(thousands_separator, "").replace(decimal_separator, ".")
        elif comma_index >= 0:
            text = _normalize_single_separator(text, ",")
        elif dot_index >= 0:
            text = _normalize_single_separator(text, ".")
        if negative_parentheses:
            text = f"-{text.lstrip('+')}"
        try:
            result = Decimal(text)
        except InvalidOperation as exc:
            raise CellValueError("The cell is not a decimal value.") from exc

    if not result.is_finite():
        raise CellValueError("Non-finite cells are not valid decimal values.")
    return result


def _normalize_single_separator(value: str, separator: str) -> str:
    pieces = value.split(separator)
    if len(pieces) == 2:
        integer_part, fractional_part = pieces
        if len(fractional_part) == 3 and integer_part.lstrip("+-").isdigit():
            return f"{integer_part}{fractional_part}"
        return f"{integer_part}.{fractional_part}"
    if all(piece.isdigit() for piece in pieces[1:]) and all(
        len(piece) == 3 for piece in pieces[1:]
    ):
        return pieces[0] + "".join(pieces[1:])
    return "".join(pieces[:-1]) + "." + pieces[-1]


def coerce_date(value: object, *, epoch: datetime = WINDOWS_EPOCH) -> date | None:
    """Convert native, Excel-serial, ISO, and common French date cells."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        raise CellValueError("Boolean cells are not valid date values.")
    if isinstance(value, int | float | Decimal):
        try:
            converted = from_excel(value, epoch=epoch)
        except (TypeError, ValueError, OverflowError) as exc:
            raise CellValueError("The numeric cell is not a valid Excel date.") from exc
        return converted.date() if isinstance(converted, datetime) else converted

    text = str(value).strip()
    normalized = normalize_header(text)
    month_match = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\s+(\d{2,4})", normalized)
    if month_match:
        day_text, month_text, year_text = month_match.groups()
        month = _FRENCH_MONTHS.get(month_text)
        if month is not None:
            return _safe_date(int(year_text), month, int(day_text))

    candidates = (text, text[:10], text[:19])
    formats = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y/%m/%d",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    )
    for candidate in dict.fromkeys(candidates):
        for date_format in formats:
            try:
                return datetime.strptime(candidate, date_format).date()
            except ValueError:
                continue
    raise CellValueError("The cell is not a supported date value.")


def _safe_date(year: int, month: int, day: int) -> date:
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise CellValueError("The cell is not a valid calendar date.") from exc


def _json_safe(value: object) -> JsonScalar:
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _filename_kind(source_name: str) -> WorkbookKind | None:
    normalized = normalize_header(Path(source_name).stem)
    if re.search(r"\bmicrocrd\s+tb1(?:\s+v\d+)?\b", normalized):
        return WorkbookKind.TB1
    if re.search(r"\bmicrocrd\s+tb2(?:\s+v\d+)?\b", normalized):
        return WorkbookKind.TB2
    if re.search(r"\bsuivi\s+acc\w+", normalized):
        return WorkbookKind.TB1
    if "etat des en cours" in normalized or "etat encours" in normalized:
        return WorkbookKind.TB2
    return None


def infer_reporting_period(label: str) -> date | None:
    """Infer the first day of a reporting month from a filename or sheet name."""

    normalized = normalize_header(Path(label).stem)
    numeric = re.search(r"(?<!\d)(0?[1-9]|1[0-2])\s*[-_/]\s*(\d{2,4})(?!\d)", label)
    if numeric:
        month, year = (int(part) for part in numeric.groups())
        return date(year + 2000 if year < 100 else year, month, 1)
    for month_name, month in _FRENCH_MONTHS.items():
        match = re.search(rf"\b{month_name}\s+(\d{{2,4}})\b", normalized)
        if match:
            year = int(match.group(1))
            return date(year + 2000 if year < 100 else year, month, 1)
    return None


def infer_agency_from_filename(source_name: str) -> str | None:
    """Infer the agency only from the controlled TB1 filename convention."""

    normalized = normalize_header(Path(source_name).stem)
    match = re.search(r"\bsuivi\s+acc\w*\s+(.+)$", normalized)
    if not match:
        return None
    candidate = re.split(
        r"\b(?:0?[1-9]|1[0-2])(?:\s*[-_/]\s*|\s+)(?:19|20)\d{2}\b|\b(?:19|20)\d{2}\b|\buniformise\b",
        match.group(1),
        maxsplit=1,
    )[0]
    candidate = re.sub(r"\s+", " ", candidate).strip()
    candidate = re.sub(r"^agence\s+", "", candidate).strip()
    return candidate.upper() or None


def _infer_sheet_agency(sheet_name: str, kind: WorkbookKind) -> str | None:
    normalized = normalize_header(sheet_name)
    if kind is WorkbookKind.TB1 or normalized in _GENERIC_SHEET_NAMES:
        return None
    if infer_reporting_period(sheet_name) is not None:
        return None
    return re.sub(r"\s+", " ", sheet_name).strip() or None


def _normalize_agency_identity(value: str) -> str:
    normalized = normalize_header(value)
    return re.sub(r"^(?:agence|agency|ag)\s+(?:(?:de|du|d)\s+)?", "", normalized)


def _classify_headers(fields: set[str]) -> WorkbookKind | None:
    for kind in (WorkbookKind.TB2, WorkbookKind.TB1):
        if TEMPLATE_FIELDS[kind].issubset(fields):
            return kind
    return None


def _header_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _detect_header(
    worksheet: _WorksheetReader,
    *,
    alias_map: Mapping[str, str],
    hint: WorkbookKind | None,
    limits: ParserLimits,
) -> _DetectedHeader | None:
    best: tuple[int, _DetectedHeader] | None = None
    rows = worksheet.iter_rows(
        min_row=1,
        max_row=limits.max_header_rows,
        min_col=1,
        max_col=limits.max_columns,
        values_only=True,
    )
    for row_number, values in enumerate(rows, start=1):
        original_headers = tuple(_header_text(value) for value in values)
        bindings: list[HeaderBinding] = []
        effective_column_count = 0
        for column_number, original in enumerate(original_headers, start=1):
            if original is None:
                continue
            normalized = normalize_header(original)
            canonical = alias_map.get(original)
            if canonical is not None:
                bindings.append(HeaderBinding(column_number, original, normalized, canonical))
            if canonical is not None:
                effective_column_count = column_number

        fields = {binding.canonical_field for binding in bindings}
        kind = _classify_headers(fields)
        if kind is None:
            continue
        score = len(fields) * 10 + len(bindings)
        if kind is hint:
            score += 3
        detected = _DetectedHeader(
            row_number=row_number,
            kind=kind,
            bindings=tuple(bindings),
            original_headers=original_headers[:effective_column_count],
            effective_column_count=effective_column_count,
        )
        if best is None or score > best[0]:
            best = (score, detected)
    return None if best is None else best[1]


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _convert_value(value: object, canonical: str, *, epoch: datetime) -> NormalizedValue:
    if canonical in DATE_FIELDS:
        return coerce_date(value, epoch=epoch)
    if canonical in DECIMAL_FIELDS:
        converted = coerce_decimal(value)
        if converted is None:
            return None
        max_digits, decimal_places = DECIMAL_STORAGE[canonical]
        maximum = Decimal(10) ** (max_digits - decimal_places) - Decimal(10) ** (-decimal_places)
        if abs(converted) > maximum:
            raise CellValueError("The decimal value exceeds the supported range.")
        return converted
    return _text_or_none(value)


def _row_issue(
    code: str,
    message: str,
    severity: IssueSeverity,
    *,
    sheet_name: str,
    row_number: int,
    field: str | None = None,
    column_number: int | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        message=message,
        severity=severity,
        field=field,
        sheet_name=sheet_name,
        row_number=row_number,
        column_number=column_number,
    )


def _parse_row(
    values: Sequence[object],
    *,
    detected: _DetectedHeader,
    sheet_name: str,
    row_number: int,
    sheet_agency: str | None,
    sheet_agency_source: AgencySource,
    sheet_period: date | None,
    epoch: datetime,
    reference_is_text: bool,
) -> ParsedRow:
    raw_data = {
        binding.original_header: _json_safe(values[binding.column_number - 1])
        for binding in detected.bindings
    }
    data: dict[str, NormalizedValue] = {}
    issues: list[ValidationIssue] = []

    for binding in detected.bindings:
        value = values[binding.column_number - 1]
        try:
            converted = _convert_value(value, binding.canonical_field, epoch=epoch)
        except CellValueError:
            issue_code = (
                "invalid_date"
                if binding.canonical_field in DATE_FIELDS
                else "invalid_decimal"
                if binding.canonical_field in DECIMAL_FIELDS
                else "invalid_value"
            )
            issues.append(
                _row_issue(
                    issue_code,
                    f"The {binding.canonical_field} cell could not be normalized.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field=binding.canonical_field,
                    column_number=binding.column_number,
                )
            )
            converted = None

        previous = data.get(binding.canonical_field)
        if previous is not None and converted is not None and previous != converted:
            issues.append(
                _row_issue(
                    "conflicting_duplicate_column",
                    f"Multiple columns contain different values for {binding.canonical_field}.",
                    IssueSeverity.WARNING,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field=binding.canonical_field,
                    column_number=binding.column_number,
                )
            )
        if converted is not None or binding.canonical_field not in data:
            data[binding.canonical_field] = converted

    agency_value = data.get("agency")
    cell_agency_name = agency_value if isinstance(agency_value, str) else None
    cell_agency = cell_agency_name
    agency = sheet_agency or cell_agency
    agency_source = (
        sheet_agency_source
        if sheet_agency is not None
        else AgencySource.CELL
        if cell_agency is not None
        else AgencySource.NONE
    )
    if (
        sheet_agency is not None
        and cell_agency is not None
        and _normalize_agency_identity(sheet_agency) != _normalize_agency_identity(cell_agency)
    ):
        issues.append(
            _row_issue(
                "agency_cell_conflicts_with_source",
                "The agency cell differs from the controlled workbook or worksheet identity.",
                IssueSeverity.ERROR,
                sheet_name=sheet_name,
                row_number=row_number,
                field="agency",
            )
        )
    if agency is not None:
        data["agency"] = agency

    request_date = data.get("request_date")
    reference = data.get("reference")
    if reference is not None:
        if not reference_is_text:
            issues.append(
                _row_issue(
                    "reference_must_be_text",
                    "La référence doit être saisie dans une cellule Excel au format Texte.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="reference",
                )
            )
        try:
            canonical_reference = parse_canonical_reference(reference)
        except CellValueError:
            issues.append(
                _row_issue(
                    "invalid_reference_format",
                    "La référence doit respecter le format CCCC/NNN/T/JJMMAAAA.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="reference",
                )
            )
        else:
            if isinstance(request_date, date) and canonical_reference.request_date != request_date:
                issues.append(
                    _row_issue(
                        "reference_date_mismatch",
                        "La date de la référence doit être identique à la Date de la demande.",
                        IssueSeverity.ERROR,
                        sheet_name=sheet_name,
                        row_number=row_number,
                        field="reference",
                    )
                )
    period = sheet_period
    if period is None and isinstance(request_date, date):
        period = request_date.replace(day=1)

    if detected.kind is WorkbookKind.TB2:
        terminal_date = data.get("outcome_date")
        status = data.get("status")
        normalized_status = normalize_header(status) if isinstance(status, str) else ""
        is_rejected = normalized_status.startswith("rejet")
        is_disbursed = normalized_status.startswith("decaisse")
        if (is_rejected or is_disbursed) and not isinstance(terminal_date, date):
            issues.append(
                _row_issue(
                    "terminal_status_requires_terminal_date",
                    "A funded, disbursed, or rejected request status requires a terminal date.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="outcome_date",
                )
            )
        rejection_reason = data.get("rejection_reason")
        if is_rejected and not (isinstance(rejection_reason, str) and rejection_reason.strip()):
            issues.append(
                _row_issue(
                    "rejected_status_requires_rejection_reason",
                    "A rejected request status requires a rejection reason.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="rejection_reason",
                )
            )
        if isinstance(terminal_date, date):
            if is_rejected:
                data["rejection_date"] = terminal_date
            elif is_disbursed:
                data["disbursement_date"] = terminal_date
            else:
                issues.append(
                    _row_issue(
                        "terminal_date_requires_terminal_status",
                        "A terminal date requires a funded or rejected request status.",
                        IssueSeverity.ERROR,
                        sheet_name=sheet_name,
                        row_number=row_number,
                        field="outcome_date",
                    )
                )

    issues.extend(
        _row_issue(
            "missing_required_value",
            f"The required field {required_field} is blank.",
            IssueSeverity.ERROR,
            sheet_name=sheet_name,
            row_number=row_number,
            field=required_field,
        )
        for required_field in REQUIRED_FIELDS[detected.kind]
        if data.get(required_field) is None
    )

    amount = data.get("amount")
    if isinstance(amount, Decimal) and amount < 0:
        issues.append(
            _row_issue(
                "negative_amount",
                "The requested amount cannot be negative.",
                IssueSeverity.ERROR,
                sheet_name=sheet_name,
                row_number=row_number,
                field="amount",
            )
        )

    if isinstance(request_date, date):
        for later_field in (
            "received_at_agency_date",
            "assigned_to_gp_date",
            "visit_date",
            "outcome_date",
            "decision_date",
            "disbursement_date",
            "rejection_date",
        ):
            later_date = data.get(later_field)
            if isinstance(later_date, date) and later_date < request_date:
                issues.append(
                    _row_issue(
                        "date_precedes_request",
                        f"The {later_field} value precedes the request date.",
                        IssueSeverity.WARNING,
                        sheet_name=sheet_name,
                        row_number=row_number,
                        field=later_field,
                    )
                )

    if detected.kind is WorkbookKind.TB2:
        reception = data.get("received_at_agency_date")
        counsellor_name = data.get("counsellor_name")
        if isinstance(reception, date) and not counsellor_name:
            issues.append(
                _row_issue(
                    "missing_counsellor_name",
                    "A reception date requires a CA/CAA name.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="counsellor_name",
                )
            )
        gp_assignment = data.get("assigned_to_gp_date")
        gp_name = data.get("gp_name")
        if isinstance(gp_assignment, date) and not gp_name:
            issues.append(
                _row_issue(
                    "missing_gp_name",
                    "A GP assignment date requires a GP name.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="gp_name",
                )
            )
        if isinstance(gp_assignment, date) and not isinstance(reception, date):
            issues.append(
                _row_issue(
                    "assignment_requires_reception",
                    "A GP assignment date requires a reception date.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="assigned_to_gp_date",
                )
            )
        visit = data.get("visit_date")
        if isinstance(visit, date) and not isinstance(gp_assignment, date):
            issues.append(
                _row_issue(
                    "visit_requires_gp_assignment",
                    "A client visit date requires a GP assignment date.",
                    IssueSeverity.ERROR,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field="visit_date",
                )
            )
        ordered_milestones = [
            ("request_date", data.get("request_date")),
            ("received_at_agency_date", data.get("received_at_agency_date")),
            ("assigned_to_gp_date", data.get("assigned_to_gp_date")),
            ("visit_date", data.get("visit_date")),
        ]
        previous_field: str | None = None
        previous_date: date | None = None
        for field_name, milestone in ordered_milestones:
            if not isinstance(milestone, date):
                continue
            if previous_date is not None and milestone < previous_date:
                issues.append(
                    _row_issue(
                        "invalid_lifecycle_sequence",
                        f"The {field_name} value precedes {previous_field}.",
                        IssueSeverity.ERROR,
                        sheet_name=sheet_name,
                        row_number=row_number,
                        field=field_name,
                    )
                )
            previous_field = field_name
            previous_date = milestone

    return ParsedRow(
        sheet_name=sheet_name,
        source_row=row_number,
        agency=agency,
        agency_source=agency_source,
        reporting_period=period,
        data=data,
        raw_data=raw_data,
        issues=tuple(issues),
    )


def _parse_sheet(
    worksheet: _WorksheetReader,
    *,
    detected: _DetectedHeader,
    workbook_agency: str | None,
    workbook_period: date | None,
    limits: ParserLimits,
    current_total_rows: int,
    epoch: datetime,
) -> ParsedSheet:
    sheet_name = str(worksheet.title)
    inferred_sheet_agency = _infer_sheet_agency(sheet_name, detected.kind)
    sheet_agency = workbook_agency or inferred_sheet_agency
    sheet_agency_source = (
        AgencySource.FILENAME
        if workbook_agency is not None
        else AgencySource.SHEET
        if inferred_sheet_agency is not None
        else AgencySource.NONE
    )
    sheet_period = infer_reporting_period(sheet_name) or workbook_period
    binding_indexes = tuple(binding.column_number - 1 for binding in detected.bindings)
    rows: list[ParsedRow] = []
    sheet_issues: list[ValidationIssue] = []
    duplicate_fields = [
        field
        for field, count in Counter(
            binding.canonical_field for binding in detected.bindings
        ).items()
        if count > 1
    ]
    sheet_issues = [
        ValidationIssue(
            code="duplicate_header_mapping",
            message=f"Multiple columns map to the canonical field {field}.",
            severity=IssueSeverity.WARNING,
            field=field,
            sheet_name=sheet_name,
            row_number=detected.row_number,
        )
        for field in duplicate_fields
    ]

    blank_run = 0
    scanned_rows = 0
    blank_terminated = False
    last_scanned_row = detected.row_number
    max_scan_rows = limits.max_rows_per_sheet + limits.consecutive_blank_rows
    max_data_row = detected.row_number + max_scan_rows
    source_rows = worksheet.iter_rows(
        min_row=detected.row_number + 1,
        max_row=max_data_row,
        min_col=1,
        max_col=detected.effective_column_count,
        values_only=True,
    )
    for row_number, values in enumerate(source_rows, start=detected.row_number + 1):
        scanned_rows += 1
        last_scanned_row = row_number
        mapped_blank = all(_is_blank(values[index]) for index in binding_indexes)
        if mapped_blank:
            blank_run += 1
            if blank_run >= limits.consecutive_blank_rows:
                blank_terminated = True
                break
            continue
        blank_run = 0
        if len(rows) >= limits.max_rows_per_sheet:
            raise WorkbookLimitError("A worksheet reached the bounded row-scan limit.")
        if current_total_rows + len(rows) >= limits.max_total_rows:
            raise WorkbookLimitError("The workbook exceeds the total parsed-row limit.")
        reference_binding = next(
            (binding for binding in detected.bindings if binding.canonical_field == "reference"),
            None,
        )
        reference_cell = (
            worksheet.cell(row=row_number, column=reference_binding.column_number)
            if reference_binding is not None
            else None
        )
        rows.append(
            _parse_row(
                values,
                detected=detected,
                sheet_name=sheet_name,
                row_number=row_number,
                sheet_agency=sheet_agency,
                sheet_agency_source=sheet_agency_source,
                sheet_period=sheet_period,
                epoch=epoch,
                reference_is_text=(
                    reference_cell is not None
                    and getattr(reference_cell, "data_type", None) in {"s", "inlineStr"}
                ),
            )
        )

    if scanned_rows == max_scan_rows and not blank_terminated:
        raise WorkbookLimitError("A worksheet reached the bounded row-scan limit.")

    metadata = SheetMetadata(
        name=sheet_name,
        kind=detected.kind,
        header_row=detected.row_number,
        last_scanned_row=last_scanned_row,
        columns_scanned=detected.effective_column_count,
        agency=sheet_agency,
        agency_source=sheet_agency_source,
        reporting_period=sheet_period,
        bindings=detected.bindings,
        blank_terminated=blank_terminated,
        row_count=len(rows),
    )
    return ParsedSheet(metadata=metadata, rows=tuple(rows), issues=tuple(sheet_issues))


def _resolve_source_name(source: WorkbookSource, source_name: str | None) -> str:
    if source_name:
        return Path(source_name).name
    if isinstance(source, str | Path):
        return Path(source).name
    stream_name = getattr(source, "name", None)
    if isinstance(stream_name, str) and stream_name:
        return Path(stream_name).name
    return "uploaded-workbook.xlsx"


def _select_workbook_kind(
    sheets: Sequence[ParsedSheet], hint: WorkbookKind | None
) -> tuple[WorkbookKind, bool]:
    kinds = Counter(sheet.metadata.kind for sheet in sheets)
    if len(kinds) == 1:
        return next(iter(kinds)), False
    if hint is not None and hint in kinds:
        return hint, True
    return kinds.most_common(1)[0][0], True


def _single_or_none(values: Iterable[str | date | None]) -> str | date | None:
    unique = {value for value in values if value is not None}
    return next(iter(unique)) if len(unique) == 1 else None


def _profile_rows(
    rows: Sequence[ParsedRow], kind: WorkbookKind
) -> tuple[BatchProfile, tuple[ValidationIssue, ...]]:
    required = tuple(sorted(REQUIRED_FIELDS[kind]))
    if not rows:
        return (
            BatchProfile(
                row_count=0,
                valid_row_count=0,
                invalid_row_count=0,
                warning_count=0,
                agency_count=0,
                period_count=0,
                missing_required_counts=dict.fromkeys(required, 0),
                schema_valid=True,
            ),
            (),
        )

    frame = pd.DataFrame(
        {
            "source_sheet": pd.Series((row.sheet_name for row in rows), dtype="string"),
            "source_row": pd.Series((row.source_row for row in rows), dtype="int64"),
            "reference": pd.Series((row.data.get("reference") for row in rows), dtype="object"),
            "amount": pd.Series((row.data.get("amount") for row in rows), dtype="object"),
            "request_date": pd.Series(
                (row.data.get("request_date") for row in rows), dtype="object"
            ),
            "agency": pd.Series((row.agency for row in rows), dtype="object"),
            "reporting_period": pd.Series((row.reporting_period for row in rows), dtype="object"),
        }
    )
    schema = pa.DataFrameSchema(
        {
            "source_sheet": pa.Column(pa.String, nullable=False),
            "source_row": pa.Column(pa.Int64, checks=pa.Check.ge(2), nullable=False),
            "reference": pa.Column(pa.Object, nullable=True),
            "amount": pa.Column(
                pa.Object,
                checks=pa.Check(
                    lambda value: isinstance(value, Decimal),
                    element_wise=True,
                    ignore_na=True,
                ),
                nullable=True,
            ),
            "request_date": pa.Column(
                pa.Object,
                checks=pa.Check(
                    lambda value: isinstance(value, date),
                    element_wise=True,
                    ignore_na=True,
                ),
                nullable=True,
            ),
            "agency": pa.Column(pa.Object, nullable=True),
            "reporting_period": pa.Column(
                pa.Object,
                checks=pa.Check(
                    lambda value: isinstance(value, date),
                    element_wise=True,
                    ignore_na=True,
                ),
                nullable=True,
            ),
        },
        strict=True,
        coerce=False,
    )
    schema_valid = True
    profile_issues: tuple[ValidationIssue, ...] = ()
    try:
        schema.validate(frame, lazy=True)
    except SchemaErrors as exc:
        schema_valid = False
        failure_count = len(exc.failure_cases)
        profile_issues = (
            ValidationIssue(
                code="batch_schema_validation_failed",
                message=f"Pandera found {failure_count} normalized batch schema failure(s).",
                severity=IssueSeverity.ERROR,
            ),
        )

    valid_row_count = sum(row.is_valid for row in rows)
    warning_count = sum(
        issue.severity is IssueSeverity.WARNING for row in rows for issue in row.issues
    )
    missing_counts = {field: sum(row.data.get(field) is None for row in rows) for field in required}
    profile = BatchProfile(
        row_count=len(frame.index),
        valid_row_count=valid_row_count,
        invalid_row_count=len(frame.index) - valid_row_count,
        warning_count=warning_count,
        agency_count=int(frame["agency"].dropna().nunique()),
        period_count=int(frame["reporting_period"].dropna().nunique()),
        missing_required_counts=missing_counts,
        schema_valid=schema_valid,
    )
    return profile, profile_issues


def parse_workbook(
    source: WorkbookSource,
    *,
    source_name: str | None = None,
    header_overrides: Mapping[str, str] | None = None,
    kind_hint: WorkbookKind | None = None,
    limits: ParserLimits | None = None,
) -> ParsedWorkbook:
    """Parse one XLSX stream or path without accessing any Django models.

    Governed headers must exactly match the versioned TB1 or TB2 template,
    although their column order may vary. ``header_overrides`` is retained only
    for API compatibility and is rejected when supplied.
    """

    if kind_hint is not None and not isinstance(kind_hint, WorkbookKind):
        raise ParserConfigurationError("The workbook kind hint is invalid.")
    active_limits = limits or ParserLimits()
    alias_map = _build_template_header_map(header_overrides)
    resolved_name = _resolve_source_name(source, source_name)
    hint = kind_hint or _filename_kind(resolved_name)
    workbook_input: WorkbookSource = source

    try:
        workbook = load_workbook(
            filename=workbook_input,
            read_only=True,
            data_only=True,
            keep_links=False,
        )
    except Exception as exc:
        raise InvalidWorkbookError("The supplied file is not a readable XLSX workbook.") from exc

    try:
        source_sheet_count = len(workbook.sheetnames)
        if source_sheet_count > active_limits.max_sheets:
            raise WorkbookLimitError("The workbook exceeds the configured sheet limit.")

        workbook_agency = infer_agency_from_filename(resolved_name)
        workbook_period = infer_reporting_period(resolved_name)
        parsed_sheets: list[ParsedSheet] = []
        workbook_issues: list[ValidationIssue] = []
        total_rows = 0

        for worksheet in workbook.worksheets:
            sheet_name = str(worksheet.title)
            detected = _detect_header(
                worksheet,
                alias_map=alias_map,
                hint=hint,
                limits=active_limits,
            )
            if detected is None:
                workbook_issues.append(
                    ValidationIssue(
                        code="sheet_header_not_detected",
                        message="No supported TB1 or TB2 header was found within the bounded scan.",
                        severity=IssueSeverity.WARNING,
                        sheet_name=sheet_name,
                    )
                )
                continue
            parsed_sheet = _parse_sheet(
                worksheet,
                detected=detected,
                workbook_agency=workbook_agency,
                workbook_period=workbook_period,
                limits=active_limits,
                current_total_rows=total_rows,
                epoch=workbook.epoch,
            )
            parsed_sheets.append(parsed_sheet)
            total_rows += len(parsed_sheet.rows)

        if not parsed_sheets:
            raise UnsupportedWorkbookError("No supported TB1 or TB2 worksheet was detected.")

        workbook_kind, mixed = _select_workbook_kind(parsed_sheets, hint)
        if mixed:
            workbook_issues.append(
                ValidationIssue(
                    code="mixed_workbook_schemas",
                    message="The workbook contains both TB1 and TB2 worksheet schemas.",
                    severity=IssueSeverity.WARNING,
                )
            )

        all_rows = tuple(row for sheet in parsed_sheets for row in sheet.rows)
        inferred_agency = workbook_agency or _single_or_none(row.agency for row in all_rows)
        inferred_period = workbook_period or _single_or_none(
            row.reporting_period for row in all_rows
        )
        agency = inferred_agency if isinstance(inferred_agency, str) else None
        reporting_period = inferred_period if isinstance(inferred_period, date) else None
        profile, profile_issues = _profile_rows(all_rows, workbook_kind)
        workbook_issues.extend(profile_issues)
        metadata = WorkbookMetadata(
            source_name=resolved_name,
            kind=workbook_kind,
            agency=agency,
            reporting_period=reporting_period,
            source_sheet_count=source_sheet_count,
            parsed_sheet_count=len(parsed_sheets),
        )
        return ParsedWorkbook(
            metadata=metadata,
            sheets=tuple(parsed_sheets),
            profile=profile,
            issues=tuple(workbook_issues),
        )
    except WorkbookParserError:
        raise
    except Exception as exc:
        raise InvalidWorkbookError("The XLSX workbook could not be parsed safely.") from exc
    finally:
        workbook.close()
