# TB1 workbook

Use the [blank TB1 template](../templates/SUIVI%20ACCUEIL%20%3CNOM%20DE%20L%E2%80%99AGENCE%3E.xlsx). Name the completed file `SUIVI ACCUEIL <AGENCY>.xlsx`, for example `SUIVI ACCUEIL ARIANA.xlsx`. The filename identifies the agency. Name each monthly sheet in French as `<Month> <Year>`, for example `Avril 2026`; the sheet name determines the reporting month.

The header row must appear within the first 15 rows. Column order may vary, but these six headers must match the template exactly. Every data row needs a value in each column.

| Exact Excel header | Meaning |
| --- | --- |
| `Référence de la demande` | Request reference |
| `Date de la demande` | Request date |
| `Montant demandé` | Requested amount |
| `Type de demande` | Request type |
| `Type de crédit` | Credit type |
| `Catégorie d’activité` | Activity category |

Store the reference as Excel text in the form `1234/001/P/20032026`. Its four-digit agency code and embedded date must match the agency record and request date. Dates must be valid; amounts must be nonnegative. Request type, credit type, and activity must resolve to active reference values.

Client name, phone number, and address columns in the template are ignored by the import. TB1 records the initial request; lifecycle milestones come from TB2. See the [full import contract](excel-import-contract.md).
