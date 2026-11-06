# Decisions

## Repository folder

The product is HRIS. The git folder stays `hirs-system` (the existing remote). The plan's `hris/` tree is the contents of this folder.

## Router

React Router's data router (`createBrowserRouter`) in the Vite app.

## Identifiers

MongoDB `_id` is an ObjectId. Foreign keys and `company_id` are the string form of that id. API responses include `id` as a string.

## Money

Python `Decimal`, quantized half-up to the centavo, stored as BSON `Decimal128` through a PyMongo type codec. Float inputs raise. Payroll and the pure engines do not use float.

## De minimis and tax

The plan lists de minimis excess in a step after withholding tax. The engine moves the excess into the taxable base before tax so the excess is actually withheld. Contribution and tax tables are documents, effective-dated. The seeded SSS, PhilHealth, Pag-IBIG, and TRAIN brackets match the 2026 public schedules used in development and must be checked against the current circulars before go-live.

## Tax brackets

Annual TRAIN brackets are stored on `tax_tables`. Monthly and semi-monthly runs use a table whose thresholds are the annual thresholds divided by the number of periods, with base tax divided the same way. Annualization uses the annual table.

## Approval when no flow exists

If a company has no active flow for a module, `start_request` marks the request approved and runs the handler immediately. Seed data creates a flow per module so demo approvals are explicit.

## Local Mongo

Docker is not required on this machine. Development uses a single-node replica set at `127.0.0.1:27020` (`hirs-system/mongodb/mongod.conf`), leaving the school system on 27018 and clinic records on 27019. Redis database index 2 avoids other apps on the same Redis. The API listens on 8010 because 8000 is Elite ERP. Docker Compose publishes 8010 on the host and keeps 8000 inside the API container.

## PDF

WeasyPrint renders HTML. On macOS it needs pango (`brew install pango`). The API still boots if the library cannot load; document generation then returns `pdf_unavailable`.

## Leave year-end

Unused days split into cash conversion, then carry up to `carry_over_max`, then expiry. Conversion is taken first. A carry cap of zero keeps nothing. The source year records a negative `carry_over` for the days that move, so that year no longer holds them. The next year records the matching positive `carry_over`. Cash conversion writes a taxable `leave_conversion` payroll adjustment when a draft January period of the next year exists. Without that period the ledger still records the conversion and payroll does not. Carried days with `carry_over_expiry_months` from 1 to 11 expire on the first monthly job after that month, once per year.

## OpenAPI client

`openapi-typescript` 7 expects TypeScript 5. This app uses TypeScript 7, and that generator crashes on `ts.factory`. `backend/scripts/export_openapi.py` writes `frontend/openapi.json`. `frontend/scripts/generate-api-types.mjs` turns that file into `src/api/schema.d.ts` with no extra compiler. The React app still calls the API through the cookie client in `src/api/client.ts`.

## Email

SMTP points at Mailpit in Docker. If SMTP is down, the message is logged as "not sent" without the body.

## Users and companies

`users.company_id` is the tenant for login. It is null only for the super admin, who selects a company with `X-Company-Id`. This field is not in the plan's user list; roles and employees already carry `company_id`, and login needs a direct tenant.

## Contribution brackets

PhilHealth and Pag-IBIG are formulas in `app/domain/contributions.py`. Stored `contribution_tables` can mirror those amounts. SSS MPF above MSC 20,000 is reported on `mpf` / `mpf_er` and is already inside the employee and employer shares.

## Datetimes

Mongo reads use `tz_aware=True` with UTC. Comparing a stored timestamp to `utcnow()` stays valid. Writes use timezone-aware UTC.

## Demo super admin

The seeded super admin belongs to the demo company so the admin shell has a tenant. A super admin with a null `company_id` must send `X-Company-Id`.
