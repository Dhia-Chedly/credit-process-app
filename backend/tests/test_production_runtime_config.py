from pathlib import Path
from runpy import run_path


def test_gunicorn_access_log_uses_request_path_without_query_strings() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    settings = run_path(str(backend_root / "gunicorn.conf.py"))
    access_format = str(settings["access_log_format"])

    assert "%(m)s" in access_format
    assert "%(U)s" in access_format
    assert "%(q)s" not in access_format
    assert "%(r)s" not in access_format
    assert "%(f)s" not in access_format

    dockerfile = (backend_root / "Dockerfile").read_text()
    assert '"--config", "/app/gunicorn.conf.py"' in dockerfile
