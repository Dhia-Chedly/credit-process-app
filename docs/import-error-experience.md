# Import reports

The import page shows whether a batch is processing, completed, partially published, or failed. It reports accepted and rejected row counts and links duplicate uploads to the original batch.

A blocking error rejects the workbook before staging. The correction report identifies the sheet, row, field, submitted value when safe, and expected format. Only governed non-client values may appear; client identity, contact details, addresses, and comments are excluded. The original workbook is deleted after processing.

The interface highlights cells with issues and leaves other safe fields visible for row context. Operators correct the source workbook and upload it again. An exact repeat of previously uploaded bytes returns the existing batch.
