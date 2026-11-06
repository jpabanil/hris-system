# Deployment

## This machine

- API: `127.0.0.1:8010` (8000 is Elite ERP on this machine)
- Web: `127.0.0.1:5174`
- MongoDB replica set `rs0`: `127.0.0.1:27020`, data in `mongodb/data`, config `mongodb/mongod.conf`
- Redis: `redis://127.0.0.1:6379/2`
- Do not use ports 27018 or 27019. Those belong to other products.

Copy `.env.example` to `backend/.env` before production. Set `SECRET_KEY`, a 32-byte base64 `FIELD_ENCRYPTION_KEY`, `COOKIE_SECURE=true`, and real SMTP. `ENV=production` hides password-reset tokens from the API response.

## Docker Compose

`docker compose up` builds the API image and starts Mongo 7 as a replica set, Redis, Mailpit (SMTP 1025, UI 8025), the API, a Celery worker, beat, Flower, and the Vite web container. The API container reads `MONGO_URI=mongodb://mongo:27017/?replicaSet=rs0`.

## Process layout

- `uvicorn app.main:app` or Gunicorn with Uvicorn workers for the API
- `celery -A app.worker.celery_app worker` for jobs
- `celery -A app.worker.celery_app beat` for the schedule
- nginx serves `frontend/dist` and proxies `/api/` and `/health` to the API

`deploy/nginx.conf` is the site config. Put TLS certificates in front of it. Back up the MongoDB data directory, or use `mongodump` against the replica set, and test a restore before go-live.

## Go-live

1. Confirm contribution, tax, and holiday tables.
2. Import opening leave balances and year-to-date payroll.
3. Run one payroll in parallel with the old system and compare to the centavo.
4. Create one user per role and turn on 2FA for payroll and HR admin.
