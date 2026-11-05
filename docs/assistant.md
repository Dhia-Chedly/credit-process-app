# Assistant

The optional assistant answers questions about published requests, dashboard metrics, delay alerts, and sanitized import reports. It uses approved read-only Django tools; it cannot run SQL or change records.

Enable it with server-side environment variables:

```dotenv
ASSISTANT_ENABLED=true
OPENAI_API_KEY=<server-side-key>
OPENAI_MODEL=<model-id>
ASSISTANT_MAX_OUTPUT_TOKENS=900
```

Restart the backend after changing these values. Never place the API key in a `NEXT_PUBLIC_*` variable. When disabled or incompletely configured, `POST /api/assistant/messages/` returns `503`.

The authenticated endpoint accepts a question and up to six recent messages. The response separates its answer, sources, application links, and suggested follow-ups. Conversations are not stored by the application.

Tool responses exclude client identity, contact details, comments, raw workbook content, and filenames. A request reference may be sent to the configured provider for an explicit lookup. Do not enter credentials or client data in questions. Generated explanations are advisory; linked application records are authoritative. Provider processing and retention follow the organization's provider agreement.
