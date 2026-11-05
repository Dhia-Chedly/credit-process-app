# Credit Operations Platform

Credit Operations Platform imports TB1 and TB2 credit-request workbooks into PostgreSQL and serves an authenticated Django API and Next.js dashboard. RabbitMQ and Celery process imports in the background.

## Run locally

Requires Docker with Compose. No host Python or Node installation is needed.

```bash
docker compose up -d --build --wait
docker compose exec backend python manage.py createsuperuser
```

Open the dashboard at <http://localhost:3000>. The API is at <http://localhost:8000/api/> and its documentation is at <http://localhost:8000/api/docs/>.

Compose supplies development defaults. Copy `.env.example` to `.env` to override them. Keep real workbooks and credentials out of Git.

For a local demonstration, populate the database with generated sample records:

```bash
docker compose exec backend python manage.py seed_showcase_data
```

## Operate and check

```bash
docker compose ps
docker compose logs -f backend worker frontend
docker compose exec backend python manage.py check
docker compose run --rm --no-deps backend pytest
docker compose run --rm --no-deps frontend pnpm test
docker compose down
```

Start the stack before running the test commands; the backend tests require PostgreSQL. `docker compose down` preserves the database and upload volumes.

## Workbook format

The two empty files in `templates/` define the TB1 and TB2 layouts. Uploaded workbooks stay in a Docker volume. The parser ignores client names, contact details, addresses, and comments.

See the [import contract](docs/excel-import-contract.md), [architecture](docs/architecture.md), [database schema](docs/database-schema.md), [reference data](docs/reference-data-guide.md), [delay alerts](docs/delay-alerts.md), and [assistant](docs/assistant.md) guides.
