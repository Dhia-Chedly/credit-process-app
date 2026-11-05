from typing import Any

from celery import shared_task


@shared_task(bind=True, name="imports.process_batch")  # type: ignore[untyped-decorator]
def process_import_batch(_task: Any, batch_id: str) -> dict[str, int | str]:
    from apps.imports.services import process_batch

    return process_batch(batch_id)
