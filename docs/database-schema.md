# Database schema

Django migrations define the schema. These are the main persisted records:

| Table | One row represents |
| --- | --- |
| `ingestion.import_batch` | An uploaded workbook and its processing result |
| `ingestion.stg_tb1_request_row` | A validated TB1 source row |
| `ingestion.stg_tb2_snapshot_row` | A validated TB2 source row |
| `ingestion.stg_data_quality_issue` | A sanitized validation or matching issue |
| `warehouse.dim_agency`, `dim_ca`, `dim_gp` | Governed agencies and employees |
| Other `warehouse.dim_*` tables | Dates, credit types, activities, request types, statuses, and rejection reasons |
| `warehouse.fact_credit_request` | One published agency/reference pair |
| `warehouse.credit_request_status_history` | One derived status transition |
| `auth.users` | One operator account |

TB1 supplies the request date, amount, credit type, request type, and activity. TB2 supplies lifecycle milestones, employee assignments, and outcome. The fact points to its controlling staging rows. Its agency/reference pair is unique; status history links each change to one source row.

Staging and facts keep the canonical reference for matching and lookup. They do not keep client identity, phone number, address, comments, or raw workbook payloads. Correction issues may retain bounded values only for approved non-client fields. The worker removes the uploaded file after processing.

Reference data is deactivated rather than deleted, preserving historical facts. A request missing from the latest accepted TB2 month receives `missing_from_latest_tb2_period`; this is a completeness flag, not a status change. Analytics read published facts and dimensions, so unmatched staging rows do not affect dashboard totals.
