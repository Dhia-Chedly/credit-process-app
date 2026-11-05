from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from django.core.files.uploadedfile import UploadedFile

XLSX_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
REQUIRED_XLSX_MEMBERS = frozenset({"[Content_Types].xml", "xl/workbook.xml"})


class UploadRejectedError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class UploadInspection:
    original_filename: str
    sha256: str
    size: int
    archive_entries: int
    uncompressed_size: int


def inspect_xlsx_upload(
    upload: UploadedFile,
    *,
    max_upload_bytes: int,
    max_uncompressed_bytes: int = 512 * 1024 * 1024,
    max_compression_ratio: int = 500,
    max_archive_entries: int = 20_000,
) -> UploadInspection:
    """Validate an uploaded XLSX container and leave its stream rewound."""

    original_filename = Path(upload.name or "").name
    if not original_filename or Path(original_filename).suffix.lower() != ".xlsx":
        raise UploadRejectedError("unsupported_extension", "Only .xlsx workbooks are accepted.")

    digest = hashlib.sha256()
    size = 0
    for chunk in upload.chunks():
        size += len(chunk)
        if size > max_upload_bytes:
            upload.seek(0)
            raise UploadRejectedError(
                "file_too_large",
                f"Workbook exceeds the {max_upload_bytes}-byte upload limit.",
            )
        digest.update(chunk)

    upload.seek(0)
    if size == 0:
        raise UploadRejectedError("empty_file", "The uploaded workbook is empty.")

    signature = upload.read(4)
    upload.seek(0)
    if signature not in XLSX_SIGNATURES:
        raise UploadRejectedError("invalid_container", "The upload is not a valid XLSX container.")

    try:
        with zipfile.ZipFile(upload) as archive:
            members = archive.infolist()
            if len(members) > max_archive_entries:
                raise UploadRejectedError(
                    "too_many_archive_entries",
                    "The workbook archive contains too many entries.",
                )

            member_names = {member.filename for member in members}
            if not REQUIRED_XLSX_MEMBERS.issubset(member_names):
                raise UploadRejectedError(
                    "invalid_workbook",
                    "The archive does not contain the required XLSX workbook files.",
                )

            uncompressed_size = 0
            for member in members:
                member_path = PurePosixPath(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise UploadRejectedError(
                        "unsafe_archive_path",
                        "The workbook archive contains an unsafe path.",
                    )
                if member.flag_bits & 0x1:
                    raise UploadRejectedError(
                        "encrypted_workbook",
                        "Encrypted workbooks are not supported.",
                    )
                uncompressed_size += member.file_size
                if uncompressed_size > max_uncompressed_bytes:
                    raise UploadRejectedError(
                        "archive_too_large",
                        "The expanded workbook exceeds the processing limit.",
                    )
                if member.file_size > 0 and member.file_size / max(member.compress_size, 1) > (
                    max_compression_ratio
                ):
                    raise UploadRejectedError(
                        "suspicious_compression",
                        "The workbook contains a suspiciously compressed archive entry.",
                    )
    except zipfile.BadZipFile as exc:
        raise UploadRejectedError("invalid_container", "The XLSX archive is corrupt.") from exc
    finally:
        upload.seek(0)

    return UploadInspection(
        original_filename=original_filename,
        sha256=digest.hexdigest(),
        size=size,
        archive_entries=len(members),
        uncompressed_size=uncompressed_size,
    )
