import hashlib
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from apps.imports.uploads import UploadRejectedError, inspect_xlsx_upload


def synthetic_workbook() -> bytes:
    stream = BytesIO()
    workbook = Workbook()
    worksheet = workbook.active
    assert isinstance(worksheet, Worksheet)
    worksheet.append(["Reference", "Amount"])
    worksheet.append(["SYNTHETIC-001", 1250])
    workbook.save(stream)
    return stream.getvalue()


def test_inspect_xlsx_upload_returns_hash_and_rewinds_stream() -> None:
    content = synthetic_workbook()
    upload = SimpleUploadedFile("synthetic.xlsx", content)

    inspection = inspect_xlsx_upload(upload, max_upload_bytes=1_000_000)

    assert inspection.original_filename == "synthetic.xlsx"
    assert inspection.sha256 == hashlib.sha256(content).hexdigest()
    assert inspection.size == len(content)
    assert inspection.archive_entries > 0
    assert inspection.uncompressed_size > inspection.size
    assert upload.tell() == 0


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("synthetic.xls", b"not-an-xlsx", "unsupported_extension"),
        ("synthetic.xlsx", b"", "empty_file"),
        ("synthetic.xlsx", b"not-an-xlsx", "invalid_container"),
    ],
)
def test_inspect_xlsx_upload_rejects_invalid_files(
    filename: str,
    content: bytes,
    code: str,
) -> None:
    upload = SimpleUploadedFile(filename, content)

    with pytest.raises(UploadRejectedError) as exc_info:
        inspect_xlsx_upload(upload, max_upload_bytes=1_000_000)

    assert exc_info.value.code == code


def test_inspect_xlsx_upload_enforces_size_limit() -> None:
    upload = SimpleUploadedFile("synthetic.xlsx", synthetic_workbook())

    with pytest.raises(UploadRejectedError) as exc_info:
        inspect_xlsx_upload(upload, max_upload_bytes=10)

    assert exc_info.value.code == "file_too_large"
    assert upload.tell() == 0
