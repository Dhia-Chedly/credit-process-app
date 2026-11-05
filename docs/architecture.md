# Architecture

Docker Compose runs five services: PostgreSQL, RabbitMQ, Django, Celery, and Next.js. The browser calls the Django API through the Next.js interface. Django and Celery share an upload volume so the worker can process queued workbooks.

```text
Browser -> Next.js -> Django API -> PostgreSQL
                         |
                         +-> RabbitMQ -> Celery worker
                                           |
                                           +-> shared upload volume
```

An upload passes archive checks, receives a batch and checksum, then enters the Celery queue. The worker parses bounded TB1 or TB2 sheets, validates the entire workbook, stores accepted rows in typed staging tables, and publishes warehouse facts only for exact agency/reference pairs. It deletes the source file after processing. Failed validation retains only a safe correction report.

| Django app | Responsibility |
| --- | --- |
| `accounts` | Operators and JWT authentication |
| `imports`, `data_quality` | Uploads, parsing, staging, and correction issues |
| `warehouse` | Reference data, request facts, and status history |
| `applications`, `analytics` | Request and dashboard APIs |
| `alerts` | Monthly delay detection and optional email |
| `assistant` | Optional read-only questions through approved tools |

Dashboard totals come from published warehouse requests. An unmatched workbook row does not create a request. The frontend has no direct access to the database, queue, or upload volume.

The assistant, when enabled, calls approved Django services. It cannot run arbitrary SQL or modify records. See [assistant configuration](assistant.md).
