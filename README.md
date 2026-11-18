# HRIS

Philippine SME human resources system. The build plan is `plan.md`.

## Stack

- API: Python 3.12, FastAPI, and Uvicorn. Request and response models are Pydantic v2. Sign-in is a JWT in httpOnly cookies, Argon2 password hashes, and optional TOTP.
- Data: MongoDB 7 as a single-node replica set, accessed with Beanie and PyMongo. Money is `Decimal` in Python and `Decimal128` in MongoDB. Payroll and leave writes use multi-document transactions.
- Jobs: Celery, with Redis as the broker and result backend. Celery Beat runs the scheduled jobs.
- Files and mail: Jinja2 and WeasyPrint render PDFs, pikepdf locks them, openpyxl writes Excel, and aiosmtplib sends mail. Docker Compose includes Mailpit for local SMTP.
- Web: Vite, React 19, and TypeScript, styled with Tailwind CSS 4. Routing is React Router. Server data uses TanStack Query. Forms use React Hook Form and Zod. Charts use Recharts, the org chart uses React Flow, and copy uses i18next. The web app is a PWA.

## Run it locally

MongoDB is a single-node replica set on port 27020. Redis uses database 2. The school system on 27018 and clinic records on 27019 are separate.

```bash
mongod --config mongodb/mongod.conf
mongosh --port 27020 --eval 'rs.initiate({_id:"rs0", members:[{_id:0, host:"127.0.0.1:27020"}]})'

cd backend
uv sync
uv run python -m seeds run --fresh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010

cd ../frontend
npm install
npm run dev
```

The API is `http://127.0.0.1:8010`. Port 8000 is already used by another app on this machine. The web app is `http://127.0.0.1:5174` and proxies `/api` to the API. Health is `GET /health`.

Every demo user uses the password `ChangeMe123!`. Accounts are listed in `docs/USER_GUIDE.md`.

## Checks

```bash
cd backend && uv run ruff check app tests seeds && uv run mypy app/domain app/core/money && uv run pytest
cd frontend && npx tsc -b --noEmit && npm run build
```

`docker compose up` starts Mongo, Redis, Mailpit, the API, a worker, and the web app when Docker is available. Local development does not require it.
