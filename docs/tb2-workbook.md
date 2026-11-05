# TB2 workbook

Use the [blank TB2 template](../templates/Etat%20des%20en%20cours%20agences%20%3CMM-YY%3E.xlsx). Name the completed file `Etat des en cours agences <MM-YY>.xlsx`, for example `Etat des en cours agences 04-26.xlsx`. The filename determines the reporting month. Each worksheet is named for its agency; the worksheet name is the authoritative agency identity.

The header row must appear within the first 15 rows. Column order may vary, but these 13 headers must match the template exactly.

| Exact Excel header | Meaning |
| --- | --- |
| `AGENCE` | Agency; if filled, must match the sheet name |
| `Référence de la demande` | Request reference |
| `Date de la demande` | Request date |
| `Type de demande` | Request type |
| `Montant demandé` | Requested amount |
| `Date réception Chef d’agence` | Agency receipt date |
| `Nom du conseiller CA/CAA` | CA/CAA name |
| `Date d’affectation au GP` | GP assignment date |
| `Nom du GP` | GP name |
| `DATE VISITE CLIENT` | Client visit date |
| `STATUT/ETAT DEMANDE` | Current status |
| `DATE DECAISSEMENT / DATE REJET` | Disbursement or rejection date |
| `Motif du rejet` | Rejection reason |

Every row needs a reference, request date, request type, amount, and status. Store the reference as Excel text in the form `1234/001/P/20032026`; its agency code and embedded date must match the agency and request date. An agency receipt date requires a CA/CAA; a GP assignment date requires a GP. Milestones must follow receipt, GP assignment, visit, then outcome. CA/CAA and GP names must identify one active employee in the sheet's agency. `Décaissé` and `Rejeté` require an outcome date; `Rejeté` also requires a rejection reason.

Client identifiers, names, contact details, addresses, and comments are ignored. TB2 matches TB1 only by agency and exact reference. See the [full import contract](excel-import-contract.md).
