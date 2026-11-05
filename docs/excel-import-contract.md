# Excel import contract

The [TB1](tb1-workbook.md) and [TB2](tb2-workbook.md) guides list the exact Excel headers and row requirements. The blank files in [`templates/`](../templates/) are the authoritative layouts. French header text is part of the file format and must not be translated. Column order may vary; aliases and missing governed columns are rejected.

## Identity and validation

Only `.xlsx` files are accepted. The upload check rejects corrupt, encrypted, oversized, or unsafe archives. A SHA-256 match returns the existing import batch instead of processing identical bytes again.

`Référence de la demande` must be an Excel text cell matching `CCCC/NNN/T/DDMMAAAA`, where the sequence has three to five digits and the type has one or two uppercase letters. For example: `1234/001/P/20032026`. The agency code must be the active four-digit code of the resolved agency, and the embedded date must equal `Date de la demande`.

TB1 gets its agency from the filename and its reporting month from each worksheet name. TB2 gets its reporting month from the filename and its agency from each worksheet name. A populated TB2 `AGENCE` cell must match the sheet. Dates must be valid, amounts nonnegative, and controlled values must resolve to exactly one active reference record. Employee names must resolve to one active CA/CAA or GP in that agency when the corresponding milestone requires them.

The parser validates the whole workbook before staging. Any blocking header or row error fails the batch and imports no rows. The report retains safe correction details by sheet, row, and governed field. Client names, identifiers, phone numbers, addresses, and comments are neither stored nor shown in correction reports.

## Publication

A clean TB1 row supplies the initial request; a clean TB2 row supplies lifecycle evidence. Each is stored in its typed staging table. A warehouse request is created only when TB1 and TB2 share the same resolved agency and exact canonical reference. Unmatched rows remain staged; client names, amounts, and dates are never fallback matching keys.

A later valid TB2 month updates the current lifecycle evidence without replacing older staging rows. A corrected upload supersedes earlier rows only for the same workbook type, agency, and reporting month. Older snapshots received out of order cannot regress the current request state.

Status is derived from lifecycle dates: registered, received, awaiting GP assignment, awaiting visit, awaiting decision, funded, or rejected. `Décaissé` and `Rejeté` require an outcome date; rejection also requires a reason. When a published request is absent from a newer, fully accepted TB2 month, it receives a completeness flag. That flag does not change its lifecycle status.

The worker deletes the source workbook after processing. PostgreSQL retains batches, safe issues, typed staging rows, facts, and status history. See the [schema](database-schema.md) and [import report](import-error-experience.md).
