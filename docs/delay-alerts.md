# Delay alerts

Alerts use the latest clean, published TB2 snapshot for each agency. The snapshot month is the observation date; the system cannot infer changes between uploads. Unmatched requests and rejected imports do not produce alerts.

| Alert | Condition at month end | Responsible role |
| --- | --- | --- |
| Receipt stalled | Receipt is in an earlier month and no GP assignment is recorded. | CA/CAA |
| Visit stalled | GP assignment is in an earlier month and no visit is recorded. | GP |

A qualifying snapshot creates a **New** alert. The same condition in a later month escalates it; a corrected upload for the same month does not. A later snapshot resolves the alert only when it records the missing milestone. An absent request does not resolve it. Funded and rejected requests cannot retain open delay alerts.

Operators can mark an alert as viewed and add a note. They cannot resolve it manually. The **Alerts** page links each alert to its request history.

Email is disabled by default. When enabled, each recipient with a work email receives one summary of new alerts per accepted import. Escalations send no email. Set these values in `.env` or deployment secrets, then restart the backend and worker:

```dotenv
ALERT_EMAIL_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_APP_PASSWORD=<app-password>
SMTP_FROM_EMAIL=alerts@example.com
SMTP_USE_TLS=true
```

Email contains request references and alert details, but no client names or contact details.
