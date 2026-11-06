# HRIS — Human Resource Information System
## Build Plan v3 (Python FastAPI + MongoDB + React)

> **Instructions for the AI coding agent (Claude Code / Grok Build):**
> - Work **one phase at a time**, in order. Do not start a phase until the previous phase's acceptance criteria pass.
> - At the end of each phase: run index/migration setup and seeders against a fresh database, run `pytest`, `ruff` and `mypy` on the backend, run the frontend type-check, lint and Playwright smoke tests, then summarize what was built and what's next.
> - Ask before changing the stack, adding paid services, or deviating from the data model below. Small, justified field additions are fine — note them in `docs/DECISIONS.md`.
> - Keep business rules (rates, tables, leave entitlements, approval chains, multipliers) in the database or config, **never hardcoded** in routers, services or components.
> - **Money is always `Decimal` in Python and `Decimal128` in MongoDB. Never `float`.** Add a test that fails if any payroll model field is a float.
> - Any operation that writes to more than one document and must stay consistent (payroll release, leave approval + ledger, loan payment + payslip, final pay) runs inside a **MongoDB multi-document transaction**.
> - Write tests for every endpoint that touches money, leave balances, approvals, or permissions.
> - Build the shared engines (approval workflow, notifications, document templates, settings, audit) in Phase 1–2 and reuse them everywhere. Do not build one-off approval logic per module.

---

## 1. Goal

A multi-company HRIS for Philippine SMEs (configurable for other countries later) covering the full employee lifecycle:

**Hire → Onboard → Work → Get paid → Grow → Separate → Final pay → Year-end compliance**

Modules:

1. Organization structure and org chart
2. Employee records (201 file), assets, documents
3. Manpower requisition, recruitment, onboarding
4. Time & attendance, shifts and rosters
5. Leave management
6. Payroll, loans, claims/reimbursements
7. Year-end tax and government compliance
8. Benefits (HMO, insurance)
9. Performance, training and certifications
10. Employee relations (discipline, grievances, policy acknowledgments)
11. Offboarding, clearance, final pay, exit interviews
12. Employee self-service portal (PWA) and HR helpdesk
13. Reports, analytics and audit
14. Data privacy tooling (RA 10173)
15. Integrations (SSO, accounting export, webhooks)

---

## 2. Tech Stack

### Backend
| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| Web framework | FastAPI (async), served by Uvicorn (Gunicorn + Uvicorn workers in prod) |
| Validation / schemas | Pydantic v2 |
| Database | MongoDB 7+ **running as a replica set** (single-node replica set in dev) — required for transactions and change streams |
| ODM | Beanie (on top of PyMongo async / Motor) |
| Settings | `pydantic-settings` (`.env`) |
| Auth | JWT access token (short-lived) + rotating refresh token, both in **httpOnly, Secure, SameSite cookies**; CSRF double-submit token for cookie auth |
| Password hashing | Argon2 (`pwdlib[argon2]` or `argon2-cffi`) |
| 2FA | TOTP via `pyotp`, QR via `qrcode` |
| SSO (optional) | `authlib` — Google Workspace and Microsoft 365 (OIDC) |
| RBAC | Custom permission model (roles → permissions) enforced by FastAPI dependencies |
| Background jobs | Celery + Redis broker (Celery Beat for schedules, Flower for monitoring) |
| Cache / rate limiting | Redis; `slowapi` or custom Redis limiter |
| File storage | Local in dev, S3-compatible in prod (`boto3` / `aioboto3`), signed URLs |
| Field encryption | App-level AES-GCM via `cryptography` with key versioning (MongoDB Queryable Encryption optional if on Atlas) |
| PDF | Jinja2 templates → WeasyPrint; password-protected PDFs via `pikepdf` |
| Excel / CSV | `openpyxl` (and `pandas` for heavy imports/reports) |
| Email | `fastapi-mail` or SMTP via `aiosmtplib`, queued in Celery |
| QR codes | `qrcode` |
| Money | `decimal.Decimal` with a project-wide context and explicit `ROUND_HALF_UP` rules |
| Dates | `zoneinfo`, `Asia/Manila` default, per-company timezone; `python-dateutil` |
| Migrations | Versioned migration scripts (Beanie migrations or a small custom runner) + index definitions in each Document's `Settings` |
| API docs | FastAPI built-in OpenAPI (`/docs`, `/redoc`) |
| Tests | `pytest`, `pytest-asyncio`, `httpx.AsyncClient`, `testcontainers` (real MongoDB replica set — **no mongomock**, transactions must be tested), `polyfactory` for factories, `freezegun`/`time-machine` |
| Quality | `ruff` (lint + format), `mypy` (strict on `domain/`), `pre-commit` |
| Error monitoring | Sentry (optional) |
| Package manager | `uv` |

### Frontend
| Concern | Choice |
|---|---|
| Build | Vite + React (latest stable) + TypeScript |
| Routing | React Router (data router) or TanStack Router — pick one in Phase 0 and record it in `DECISIONS.md` |
| UI | Tailwind CSS + shadcn/ui |
| API client | **Generated from FastAPI's OpenAPI** with `orval` or `openapi-typescript` + `openapi-fetch`; regenerate on every backend schema change |
| Server state | TanStack Query |
| Forms | React Hook Form + Zod |
| Tables | TanStack Table |
| Charts | Recharts |
| Org chart | `reactflow` |
| Calendars | FullCalendar (React) |
| Rich text (templates) | TipTap |
| i18n | `react-i18next` (English default, Filipino ready) |
| PWA | `vite-plugin-pwa` |
| E2E tests | Playwright |
| Unit tests | Vitest + Testing Library |

### Infra
| Concern | Choice |
|---|---|
| Dev env | Docker Compose: `api`, `worker`, `beat`, `flower`, `mongo` (replica set `rs0`), `redis`, `mailpit`, `web` (Vite dev), `nginx` |
| Prod | nginx serving the React build + reverse proxy to Gunicorn/Uvicorn; Celery worker + beat under systemd/Supervisor; MongoDB Atlas or self-hosted 3-node replica set |
| CI | GitHub Actions: ruff, mypy, pytest (with Mongo service as replica set), frontend lint/typecheck/vitest, Playwright smoke |

---

## 3. Repository Structure

```
hris/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                 # FastAPI app factory, middleware, routers
│   │   ├── core/                   # config, security, db init, encryption, money, tenancy, errors, pagination
│   │   ├── shared/                 # approvals, notifications, document_templates, settings, sequences, audit, imports, files
│   │   ├── modules/
│   │   │   ├── organization/
│   │   │   ├── employees/
│   │   │   ├── assets/
│   │   │   ├── recruitment/
│   │   │   ├── onboarding/
│   │   │   ├── attendance/
│   │   │   ├── leave/
│   │   │   ├── payroll/
│   │   │   ├── compliance/
│   │   │   ├── claims/
│   │   │   ├── benefits/
│   │   │   ├── performance/
│   │   │   ├── training/
│   │   │   ├── employee_relations/
│   │   │   ├── offboarding/
│   │   │   ├── helpdesk/
│   │   │   ├── privacy/
│   │   │   ├── reports/
│   │   │   └── integrations/
│   │   │       # each module contains:
│   │   │       #   models.py    (Beanie Documents)
│   │   │       #   schemas.py   (Pydantic request/response models)
│   │   │       #   service.py   (business logic / use cases — no FastAPI imports)
│   │   │       #   router.py    (thin FastAPI routes)
│   │   │       #   policies.py  (permission + scoping checks)
│   │   │       #   tasks.py     (Celery tasks)
│   │   ├── worker.py               # Celery app + beat schedule
│   │   └── templates/              # Jinja2 PDF/email templates
│   ├── migrations/
│   ├── seeds/
│   └── tests/
│       ├── unit/
│       ├── api/
│       └── fixtures/payroll/       # golden payroll cases (YAML/JSON)
├── frontend/
│   ├── src/
│   │   ├── app/                    # router, providers, layouts
│   │   ├── routes/
│   │   │   ├── auth/
│   │   │   ├── admin/
│   │   │   ├── portal/
│   │   │   └── public/careers/
│   │   ├── features/<module>/      # components, hooks, zod schemas per module
│   │   ├── api/generated/          # OpenAPI-generated client (do not edit by hand)
│   │   ├── components/ui/          # shadcn
│   │   ├── lib/
│   │   └── locales/
│   └── vite.config.ts
├── e2e/                            # Playwright
├── docs/ DECISIONS.md, API.md, DEPLOY.md, USER_GUIDE.md, PAYROLL_RULES.md, DATA_MODEL.md
├── .github/workflows/
└── docker-compose.yml
```

**Backend conventions**
- Routers are thin: parse request (Pydantic) → check permission dependency → call a service function → return a response schema. Services never import FastAPI.
- One service function per business operation (`approve_leave_request`, `compute_payroll_run`, `compute_final_pay`).
- **Tenancy:** every tenant document has `company_id`. All reads/writes go through a `TenantRepository` base that injects `company_id` from the authenticated context; direct collection access outside repositories is not allowed (enforce with a ruff/grep check in CI).
- **Money:** Pydantic fields typed as `Decimal`; Beanie/BSON encoders map to `Decimal128`; a shared `Money` helper does rounding. Never use `float` for money or hours-based pay.
- **IDs:** MongoDB `ObjectId`, serialized to strings in the API.
- **Timestamps:** every document has `created_at`, `updated_at`, `created_by`, `updated_by`; soft-deletable documents have `deleted_at` (repositories exclude soft-deleted by default).
- **Optimistic concurrency:** documents edited by humans carry a `revision` integer; updates use `{_id, revision}` filters and return 409 on conflict.
- **Lists:** cursor or page pagination, search, sort, filters via a shared query-param parser that only allows whitelisted fields per resource.
- API versioned under `/api/v1`.
- Document numbers from a `counters` collection using atomic `find_one_and_update` with `$inc`, configurable prefixes per company.
- Idempotency keys (`idempotency_keys` collection with TTL index) on clock-in and payroll actions.
- Errors returned in one consistent JSON shape (`code`, `message`, `details`).

**Frontend conventions**
- Route groups: `admin`, `portal`, `public`. Route guards check permissions from `/auth/me`.
- API calls only through the generated client wrapped in TanStack Query hooks per feature.
- All user-facing strings through `react-i18next`.
- The public careers page is a lightweight route; add prerendering only if SEO becomes a requirement.

---

## 4. MongoDB Modeling Rules

- **Embed** small, bounded data that is always read with its parent: emergency contacts, dependents, education, work history, skills, addresses, approval flow steps, review template criteria, onboarding template tasks, payslip lines.
- **Reference** (separate collection) anything that grows without bound or is queried on its own: attendance logs, attendance days, leave ledger, payslips, loans, loan payments, documents, audit logs, notifications, applicants.
- **History is append-only:** compensation history, employee movements, leave ledger, loan payments and approval actions are never updated in place — new documents only.
- **Snapshots over joins:** payslips, attendance days and generated documents store a snapshot of the inputs used (rates, schedule, tables), so they're reproducible even if master data changes later.
- **Sensitive data in its own collection** (`employee_sensitive`) with encrypted fields, so normal employee queries never load it.
- **Indexes are declared in code** (Beanie `Settings.indexes`) and created on startup/migration. Every collection with `company_id` has it as the leading key of its compound indexes. Unique indexes: `(company_id, employee_no)`, `(company_id, code)` on catalogs, `(employee_id, date)` on attendance days, `(employee_id, leave_type_id, year)` on leave balances, `(payroll_run_id, employee_id)` on payslips.
- **TTL indexes** for idempotency keys, password reset tokens, refresh-token blacklist, and expiring export files.
- **Aggregation pipelines** power reports and dashboards; heavy ones run in Celery and may read from a secondary (`readPreference=secondaryPreferred`).
- **Transactions** for multi-document consistency (see agent instructions). Keep transactions short; never call external services inside one.
- **Schema validation:** Pydantic is the source of truth; optionally add `$jsonSchema` validators on money-critical collections (payslips, leave_ledger, loans) as a second guard.
- Document the final model in `docs/DATA_MODEL.md` (collection, embed/reference decision, indexes).

---

## 5. Shared Engines (build once, use everywhere)

### 5.1 Approval Workflow Engine
- `approval_flows` — company_id, module (leave, overtime, attendance_correction, claim, requisition, payroll, profile_update, loan, offboarding, …), name, conditions (e.g. leave days > 5, amount > 10,000, department), is_active, **steps embedded**: [{order, approver_type (direct_manager, department_head, specific_role, specific_user, hr_admin), approver_value, mode (any/all)}]
- `approval_requests` — subject_type, subject_id, flow_id, current_step, status, **actions embedded** (append-only): [{step, actor_id, action (approve/reject/return), remarks, acted_at}]
- `approval_delegations` — approver_id, delegate_id, from/to (auto-route when approver is on leave)
- Escalation: Celery Beat reminders after N hours, escalate after M hours (configurable)
- One "My Approvals" inbox across all modules, with bulk approve.

### 5.2 Notifications
- In-app (`notifications` collection) + email (Celery) + optional SMS adapter interface (Semaphore or similar later)
- `notification_templates` — event key, channel, subject, Jinja2 body with merge fields, editable by HR (render in a sandboxed Jinja environment)
- User preferences per event
- Real-time badge counts via Server-Sent Events (or polling fallback)
- Scheduled reminders: birthdays, anniversaries, probation end, contract expiry, document/license expiry, pending approvals, unsubmitted timesheets

### 5.3 Document Templates & Generation
- `document_templates` — type (COE, employment contract, job offer, NTE, notice of decision, memo, clearance form, quitclaim, regularization notice), body with merge fields (`{{ employee.full_name }}`, `{{ employment.date_hired }}`), edited with TipTap in the UI, rendered with sandboxed Jinja2 → WeasyPrint
- Company letterhead, sequence number, QR code linking to a public verification endpoint
- `generated_documents` — template_id, employee_id, file_key, generated_by, verification_code
- COE requests from the portal go through the approval engine, then auto-generate.

### 5.4 Settings
- `settings` — one document per company per module with a typed Pydantic schema (payroll cutoffs, contribution timing, OT multipliers, night diff window, grace period, rounding rules, leave filing deadlines, probation length, clock-in rules)
- Settings UI grouped by module; every change audited.

### 5.5 Imports
- Upload → map columns → validate (row-level error preview) → commit as a Celery task in batches → downloadable error report
- Used for employees, opening leave balances, YTD payroll, attendance logs, holidays, loans.

### 5.6 Audit Log
- `audit_logs` — company_id, actor_id, action, entity_type, entity_id, before, after (diff), ip, user_agent, at
- Written by repository hooks on sensitive collections (employees, compensation, payroll, leave balances, roles, settings). Sensitive fields are redacted in the diff.
- Append-only; no update/delete endpoints.

---

## 6. Roles & Permissions

| Role | Scope |
|---|---|
| Super Admin | Everything, all companies, system settings |
| HR Admin | All HR modules within their company |
| HR Staff | HR modules except payroll and settings |
| Payroll Officer | Payroll, tables, loans, payslips, compliance reports |
| Payroll Approver | Approve/release payroll only (separation of duties — cannot compute) |
| Finance | View payroll register, claims approval, accounting exports |
| Department Manager | Team view; approvals for direct reports per approval flows |
| Recruiter | Requisitions, openings, applicants, onboarding |
| Employee | Own data and self-service |
| Auditor (read-only) | Read-only access to all modules and audit logs |

- Collections: `permissions` (seeded catalog, e.g. `employees.view`, `employees.view_sensitive`, `payroll.compute`, `payroll.approve`), `roles` (company_id, name, permission keys embedded), `users.role_ids`.
- Enforcement: `Depends(require("payroll.approve"))` on routes + object-level checks in `policies.py`. Effective permissions cached in Redis per user, invalidated on role change.
- **Separation of duties:** the user who computes a payroll run cannot approve it (enforced in the service + tested).
- **Data scoping:** company scoping in repositories; managers scoped to their reporting chain (precompute `manager_chain` array on employees for fast `$in` queries); optional branch-level HR scoping (`users.branch_access`).
- **Impersonation** for Super Admin (logged, banner shown, payroll actions blocked while impersonating).

---

## 7. Data Model (collections)

`[E]` = embedded in the parent document. Everything else is its own collection.

### 7.1 Organization
- `companies` — name, trade_name, tin, rdo_code, sss_employer_no, philhealth_employer_no, pagibig_employer_no, address, zip, timezone, currency, logo_key, is_active
- `branches` — company_id, name, address, city, region, geofence {lat, lng, radius_m}
- `departments` — company_id, name, code, parent_id, ancestors[] (for tree queries), head_employee_id, cost_center_id
- `positions` — company_id, title, department_id, job_level, salary_grade_id, is_supervisory, headcount_budget
- `salary_grades` — company_id, code, min, mid, max
- `cost_centers` — company_id, code, name
- Org chart endpoint built from `reports_to` and the department `ancestors` arrays.

### 7.2 Users & Employees
- `users` — email, password_hash, is_active, last_login_at, totp_secret (encrypted), locale, failed_login_count, locked_until, role_ids, branch_access, employee_id
- `employees` — company_id, user_id, employee_no, name {first, middle, last, suffix, nickname}, birth_date, birth_place, gender, civil_status, nationality, blood_type, contact {mobile, personal_email, work_email}, present_address, permanent_address, branch_id, department_id, position_id, cost_center_id, reports_to, manager_chain[], pay_group_id, employment_type, employment_status, date_hired, probation_end_date, regularization_date, contract_end_date, separation {date, reason}, is_minimum_wage_earner, photo_key, signature_key, revision
  - `[E]` emergency_contacts[], dependents[] (with hmo_eligible), education[], work_history[], skills[], licenses[] (with expiry)
  - **Denormalized current snapshot** for list views: current_compensation {basic_salary, pay_basis, daily_rate} — updated whenever a new compensation record takes effect
- `employee_sensitive` — employee_id, company_id, tin, sss_no, philhealth_no, pagibig_no, bank_accounts[] {bank_name, account_name, account_no, is_primary} — **all encrypted**, readable only with `employees.view_sensitive`; API returns masked values otherwise
- `compensation_history` — employee_id, basic_salary, pay_basis (monthly/daily/hourly), daily_rate, hourly_rate, factor_days_per_year (261/313/365 configurable), effective_date, reason, approval_request_id (append-only)
- `employee_allowances` — employee_id, allowance_type_id, amount, taxability (taxable/de_minimis/non_taxable), frequency, prorate_on_absence, effective_from/to
- `allowance_types` — company_id, code, name, default_taxability, de_minimis_category, annual_ceiling
- `employee_documents` — employee_id, document_type, file_key, expires_at, is_confidential
- `employee_movements` — employee_id, type (promotion/transfer/salary_adjustment/status_change/regularization/demotion), from, to, effective_date, approval_request_id (append-only)
- `profile_update_requests` — employee_id, changes, status (approval engine)
- Employee timeline built by an aggregation (`$unionWith`) across movements, leaves, cases, trainings and reviews.

### 7.3 Assets
- `asset_categories`, `assets` — company_id, tag, name, serial_no, category_id, purchase_date, cost, status (available/issued/repair/retired)
- `asset_assignments` — asset_id, employee_id, issued_at, returned_at, condition_out, condition_in, acknowledgment_key
- Unreturned assets block clearance.

### 7.4 Manpower, Recruitment, Onboarding
- `manpower_requisitions` — department_id, position_id, headcount, reason (new/replacement), replaced_employee_id, budget, target_start, status (approval engine)
- `job_openings` — requisition_id, title, description, requirements, employment_type, location, salary_range, salary_visible, is_public, status, closes_at
- `applicants` — job_opening_id, name, email, mobile, resume_key, source, referred_by_employee_id, stage, rating, consent_given_at
  - `[E]` activities[] (stage changes, interviews, comments), scorecards[] {interviewer_id, criteria, recommendation}
- `job_offers` — applicant_id, salary, start_date, generated_document_id, status
- Public careers page with application form, rate-limited, honeypot/captcha.
- `onboarding_templates` — name, `[E]` tasks[] {task, owner_role, due_offset_days}
- `onboarding_checklists` — employee_id, `[E]` tasks[] {task, assignee_id, due_date, status, completed_at}
- "Hire" converts applicant → employee (in a transaction) and starts the onboarding checklist.

### 7.5 Time & Attendance
- `work_schedules` — name, time_in, time_out, break_minutes, grace_minutes, rest_days[], is_flexible, core_hours, is_night_shift, required_hours
- `shifts` — company_id, code, start, end, break_minutes, crosses_midnight
- `roster_entries` — employee_id, date, shift_id (overrides default schedule)
- `shift_swap_requests` — requester_id, counterpart_id, dates, status (approval engine)
- `employee_schedules` — employee_id, work_schedule_id, effective_from/to
- `holidays` — company_id, date, name, type (regular/special_non_working/special_working/local), scope {nationwide | branch_ids[] | cities[]}
- `attendance_logs` — employee_id, logged_at, type (in/out), source (web/pwa/biometric_import/manual/kiosk), ip, location {lat, lng}, selfie_key, device_info, within_geofence — index `(employee_id, logged_at)`; consider a **time-series collection** if volume is high
- `attendance_days` — employee_id, date, schedule_snapshot, first_in, last_out, hours_worked, late_minutes, undertime_minutes, overtime_minutes, night_diff_minutes, is_rest_day, holiday_type, status, is_locked
- `overtime_requests`, `attendance_corrections`, `official_business`, `wfh_requests` — all via the approval engine
- Clock-in rules in settings: allowed sources, geofence per branch, selfie required, IP allowlist.

### 7.6 Leave
- `leave_types` — code, name, is_paid, annual_entitlement, accrual_method (upfront/monthly/per_service_year), eligibility_after_months, carry_over_max, carry_over_expiry_months, convertible_to_cash, max_conversion_days, attachment_required_after_days, gender_restriction, civil_status_restriction, min_notice_days, allow_negative_balance, counts_weekends, `[E]` tenure_tiers[]
  - Seed PH defaults (editable): Service Incentive Leave, Vacation, Sick, Maternity, Paternity, Solo Parent, VAWC, Special Leave for Women, Leave Without Pay, Bereavement (company policy)
- `leave_balances` — employee_id, leave_type_id, year, entitled, accrued, used, carried_over, adjusted (a cached projection — always rebuildable from the ledger)
- `leave_ledger` — employee_id, leave_type_id, year, entry_type (accrual/usage/adjustment/reversal/carry_over/expiry/conversion), days, ref, at (append-only; written in the same transaction as the balance update)
- `leave_requests` — dates, half_day, hourly (optional), days, reason, attachment_key, status (approval engine)
- `leave_blackouts` — department/branch, date range, reason

### 7.7 Payroll
- `pay_groups` — company_id, name, frequency (weekly/semi_monthly/monthly), cutoff rules, pay day rules (adjust for holidays/weekends)
- `payroll_periods` — pay_group_id, start/end, attendance_cutoff, pay_date, type (regular/special/13th_month/final_pay/bonus), status (draft/computed/for_approval/approved/released/locked)
- `payroll_runs` — period_id, version, computed_by, computed_at, approved_by, approved_at, progress {done, total}, notes
- `payslips` — run_id, employee_id, basic_pay, gross, taxable_income, non_taxable_income, withholding_tax, total_deductions, net_pay, `[E]` lines[] {type, code, label, quantity, rate, amount, is_taxable, cost_center_id}, ytd, snapshot, is_published, emailed_at, viewed_at
- `contribution_tables` — agency (sss/philhealth/pagibig), effective_from/to, brackets[] {from, to, ee, er, ec, mpf}
- `tax_tables` — effective_from, frequency, brackets[]; annual table for annualization
- `loans` — type (sss_salary/sss_calamity/pagibig_mpl/pagibig_calamity/company/cash_advance), reference_no, principal, amortization, start_period_id, end_period_id, balance, status, can_pause
- `loan_payments` — loan_id, payslip_id, amount (append-only; written in the release transaction)
- `recurring_deductions` — employee_id, type (HMO dependents, uniform, coop, union dues), amount, frequency, until
- `adjustments` — employee_id, period_id, type, label, amount, is_taxable, approval_request_id
- `retro_adjustments` — auto-computed differences for back-dated salary changes
- `ytd_openings` — employee_id, year, gross, taxable, non_taxable, contributions, tax_withheld, thirteenth_and_other_benefits (mid-year go-live)
- `previous_employer_income` — employee_id, year, data from the prior employer's 2316
- Payroll journal export built by aggregation over payslip lines by account and cost center.

### 7.8 Year-End & Compliance
- `tax_annualizations` — employee_id, year, annual_taxable, annual_tax_due, total_withheld, refund_or_payable, applied_in_period_id
- `bir_2316` — employee_id, year, data, file_key
- `alphalist_exports` — year, type, file_key
- `remittances` — agency, month, ee_total, er_total, reference_no, paid_at, proof_key
- Remittance report exports with configurable column layouts (formats change)
- `thirteenth_month_runs` — year, prorated per employee; non-taxable ceiling for 13th month + other benefits kept in settings (verify the current amount)

### 7.9 Claims & Reimbursements
- `claim_types` — name, requires_receipt, monthly_limit, taxability, gl_account
- `claims` — employee_id, claim_type_id, date, amount, description, receipt_keys[], status (approval engine), paid_via (payroll/separate), period_id
- `cash_advances` — amount, purpose, liquidations[] `[E]`, balance, status; unliquidated balance recoverable via payroll

### 7.10 Benefits
- `benefit_plans` — type (HMO/life/other), provider, plan_name, coverage, employer_share, employee_share, dependent_cost
- `benefit_enrollments` — employee_id, plan_id, covered_dependents[], effective_from/to, card_no, status
- Dependent add-on costs generate `recurring_deductions` automatically.

### 7.11 Performance & Training
- `review_cycles`, `review_templates` (`[E]` criteria[] with weights, rating scale), `performance_reviews` (self, manager, optional peer ratings embedded; final_score; calibration notes)
- `goals` — employee_id, cycle_id, title, weight, target, actual, progress
- `probation_evaluations` — triggered before probation end; outcome creates a regularization movement
- `one_on_ones` — manager_id, employee_id, date, notes, action_items[]
- `trainings` — title, provider, type, date, hours, cost
- `training_attendees` — training_id, employee_id, status, certificate_key
- `training_bonds` — employee_id, training_id, amount, bond_until (unserved portion flagged at offboarding)

### 7.12 Employee Relations
- `offenses` — code of conduct catalog: offense, category, sanctions_by_count[]
- `incident_reports` — reported_by, employee_id, date, description, attachment_keys[]
- `disciplinary_cases` — employee_id, incident_report_id, offense_id, case_no, status (nte_issued → explanation_received → hearing → decided → closed), `[E]` events[] (NTE with response deadline — default 5 days, configurable; explanation; hearing; decision), sanction {type, suspension_days}, details (encrypted)
- **Twin-notice due process** enforced as a state machine in the service
- Suspension days are pushed to attendance as unpaid
- `grievances` — submitted_by (nullable for anonymous), category, assigned_to, status, resolution
- `policies` — title, version, file_key, requires_acknowledgment, effective_date
- `policy_acknowledgments` — policy_id, version, employee_id, acknowledged_at, ip
- Only `employee_relations.view` sees case details; managers see outcomes only.

### 7.13 Offboarding
- `resignations` — employee_id, filed_at, last_working_day, reason, status (approval engine); default 30-day notice in settings
- `clearances` — employee_id, `[E]` items[] {department (IT/Finance/Admin/Manager/HR), item, cleared_by, cleared_at, remarks}; auto-includes unreturned assets, unliquidated cash advances, outstanding loans, unserved training bonds, pending claims
- `exit_interviews` — employee_id, answers[] (confidential)
- `final_pay` — employee_id, components (unpaid salary, prorated 13th month, leave conversion, annualization refund/payable, accountabilities), net, status, target_release_date (default within 30 days of separation, configurable)
- Generated documents: clearance form, COE, quitclaim, BIR 2316
- Celery Beat deactivates the user on the last working day; read-only portal access to payslips/2316 kept for a configurable period.

### 7.14 Helpdesk & Announcements
- `hr_tickets` — employee_id, category, subject, body, attachment_keys[], assigned_to, priority, status, sla_due, `[E]` comments[]
- `announcements` — audience (all/branch/department/role), pinned, publish_at, expire_at; `announcement_reads` — announcement_id, user_id, read_at

### 7.15 Privacy & System
- `privacy_consents` — subject_type (employee/applicant), subject_id, purpose, version, given_at, withdrawn_at
- `data_subject_requests` — type (access/correction/erasure/portability), requester, status, completed_at, export_key
- `retention_policies` — record_type, retain_years, action (anonymize/delete); Celery Beat applies them
- `counters`, `settings`, `audit_logs`, `notifications`, `login_history`, `refresh_tokens` (hashed, TTL), `idempotency_keys` (TTL), `files` (metadata for uploaded objects)
- `webhooks` — event, url, secret, is_active; `webhook_deliveries` — status, attempts, response
- Webhooks and live notification badges can be driven by **MongoDB change streams** consumed in a worker.

---

## 8. Business Rules (configurable, documented in `docs/PAYROLL_RULES.md`)

**Attendance**
- Late = first_in − (schedule start + grace), floored at 0; option for "late beyond grace counts from scheduled start"
- Undertime, OT, night diff (default 10PM–6AM, +10%), rounding (e.g. OT in 15/30-minute blocks)
- Shifts crossing midnight attribute hours to the shift's start date
- Night-shift holiday split: hours on each calendar day use that day's holiday type
- OT only paid with an approved request (pre- or post-approval per setting); optional daily OT cap
- Attendance for a period locks when payroll is computed; later corrections become adjustments in the next period

**Holiday pay**
- Regular holiday unworked: paid if present or on paid leave on the workday before (rule configurable)
- Daily-paid vs monthly-paid handling via `factor_days_per_year`
- Premium multipliers matrix (rest day, special, regular, double holiday, each with OT and night diff) seeded with Labor Code defaults and editable

**Leave**
- No overlap with other leaves, OB, or conflicting WFH
- Days exclude rest days/holidays per employee schedule (unless `counts_weekends`)
- Min notice, blackout dates, attachment rules, eligibility after N months
- Balance deducted on approval, restored on cancellation, via ledger entries in a transaction
- Year-end: carry over, expiry of carried days, cash conversion → payroll adjustment

**Payroll computation order**
1. Basic pay (monthly ÷ periods, or rate × days/hours); prorate for mid-period hires, separations and salary changes
2. − Absences, LWOP, suspension days, late, undertime
3. + OT, holiday, rest day, night diff premiums
4. + Taxable allowances, adjustments, retro pay, taxable claims
5. − Employee contributions (SSS, PhilHealth, Pag-IBIG); deduction timing per setting (1st cutoff, 2nd cutoff, split)
6. = Taxable compensation → withholding tax; minimum wage earners exempt on statutory pay per rules
7. + Non-taxable allowances, de minimis (excess over ceilings becomes taxable), non-taxable claims
8. − Loans, recurring deductions, cash advance recovery, other deductions
9. = Net pay; **never negative** — if deductions exceed pay, defer the lowest-priority deductions to the next period and flag (priority order in settings)

**Engine design**
- The payroll engine is a **pure Python module** (`modules/payroll/engine/`): input dataclasses in, payslip result out, no database access. The Celery task loads inputs, calls the engine per employee, and writes results. This keeps it fast to unit-test against golden fixtures.
- Computation runs as a Celery task with progress written to `payroll_runs.progress`; the UI polls or listens via SSE.

**Controls**
- Every payslip stores its snapshot and YTD totals
- Variance report vs the previous period (flag employees whose net changed > X%) shown before approval
- Approved/locked periods cannot be recomputed; corrections go through adjustments in a later period
- Release (publish payslips + write loan payments + update balances) is one transaction
- Payslips published to the portal only on release; emailed as password-protected PDF (password pattern configurable, e.g. employee no. + birth date)

**Year-end**
- Last period of the year runs annualization: annual tax due vs withheld → refund or additional withholding
- Separated employees annualized in final pay
- Include previous-employer income for mid-year hires
- 2316 generated for all employees; alphalist export

**Final pay**
- Unpaid salary + prorated 13th month + convertible leave − accountabilities ± annualization; release target within the configured days of separation

---

## 9. API Outline (`/api/v1`)

```
Auth        POST /auth/login /auth/logout /auth/refresh /auth/2fa/verify   GET /auth/me
            GET  /auth/sso/{provider}/login | /callback
            POST /auth/password/forgot /auth/password/reset
Dashboard   GET  /dashboard/{admin|manager|employee}
Approvals   GET  /approvals/inbox   POST /approvals/{id}/approve|reject|return   POST /approvals/bulk
            CRUD /approval-flows /approval-delegations
Org         CRUD /companies /branches /departments /positions /salary-grades /cost-centers
            GET  /org-chart
Employees   CRUD /employees   GET /employees/{id}/timeline|compensation|movements|documents|assets
            GET/PUT /employees/{id}/sensitive   (permission-gated)
            CRUD /profile-update-requests
Files       POST /files (upload, returns file key)   GET /files/{key}/url (signed URL)
Imports     POST /imports/{type}   GET /imports/{id}   POST /imports/{id}/commit
Assets      CRUD /assets /asset-assignments
Recruitment CRUD /manpower-requisitions /job-openings /applicants /job-offers
            POST /applicants/{id}/move-stage|scorecards|hire
Public      GET  /public/{company_slug}/jobs   POST /public/{company_slug}/jobs/{id}/apply
            GET  /public/documents/verify/{code}
Onboarding  CRUD /onboarding-templates   GET /onboarding/{employee_id}   PATCH /onboarding/{employee_id}/tasks/{task_id}
Attendance  CRUD /work-schedules /shifts /roster-entries /holidays
            POST /attendance/clock   POST /attendance/import   GET /attendance/days
            CRUD /overtime-requests /attendance-corrections /official-business /wfh-requests /shift-swaps
Leave       CRUD /leave-types /leave-requests /leave-blackouts
            GET  /leave-balances   POST /leave-balances/adjust
Payroll     CRUD /pay-groups /payroll-periods /loans /recurring-deductions /adjustments
            POST /payroll-periods/{id}/compute|submit|approve|release|lock
            GET  /payroll-periods/{id}/payslips|variance|register|bank-file|journal|progress
            GET  /payslips/{id}/pdf
            CRUD /contribution-tables /tax-tables
Compliance  POST /year-end/{year}/annualize   GET /year-end/{year}/2316|alphalist
            CRUD /remittances   GET /remittances/reports/{agency}?month=
            POST /thirteenth-month/{year}/compute
Claims      CRUD /claim-types /claims /cash-advances
Benefits    CRUD /benefit-plans /benefit-enrollments
Performance CRUD /review-cycles /review-templates /performance-reviews /goals /probation-evaluations /one-on-ones
Training    CRUD /trainings /training-attendees /training-bonds
Relations   CRUD /incident-reports /disciplinary-cases /offenses /grievances /policies
            POST /disciplinary-cases/{id}/issue-nte|record-explanation|schedule-hearing|decide
            POST /policies/{id}/acknowledge
Offboarding CRUD /resignations /exit-interviews
            GET  /clearances/{employee_id}   PATCH /clearances/{employee_id}/items/{item_id}
            POST /final-pay/{employee_id}/compute|approve|release
Documents   CRUD /document-templates   POST /documents/generate
Helpdesk    CRUD /hr-tickets   POST /hr-tickets/{id}/comments
Comms       CRUD /announcements   GET /notifications   PATCH /notifications/read   GET /notifications/stream (SSE)
Reports     GET  /reports/{report}?filters   POST /reports/{report}/export (async)   GET /exports/{id}
Privacy     CRUD /data-subject-requests /retention-policies   GET /privacy/consents
Admin       CRUD /roles /users /settings /notification-templates /webhooks
            GET  /permissions /audit-logs /login-history
Self        GET  /me/profile|attendance|leave|payslips|documents|2316|assets|trainings|reviews|tickets
Health      GET  /health   (mongo, redis, celery, storage)
```

---

## 10. Frontend Screens

**Auth:** login, SSO buttons, 2FA, forgot/reset, first-login password change and privacy consent.

**Admin (`/admin`)**
- Dashboards: HR (headcount, turnover, attendance today, pending approvals, expiring docs/contracts, probation ending), Payroll (next pay date, period status, remittance due dates), Manager (team attendance, team leave calendar, approvals)
- My Approvals inbox (all modules, bulk actions, delegation settings)
- Org chart (interactive, search, export PNG)
- Employees: list, create wizard, profile tabs (Overview, Employment, Compensation, Attendance, Leave, Payroll, Documents, Assets, Benefits, Performance, Training, Relations, Timeline, Audit)
- Imports center with column mapping and error preview
- Assets
- Recruitment: requisitions, openings, applicant kanban, interview scheduling, scorecards, offers
- Onboarding board
- Attendance: daily board, timesheet grid, roster planner (drag-and-drop shifts), schedules, holidays calendar (nationwide + local), imports, approvals, geofence map per branch
- Leave: requests, team calendar, balances, types, blackout dates
- Payroll: pay groups, periods, compute (with live progress) → variance review → submit → approve → release, payslip viewer, loans, recurring deductions, adjustments, tables, 13th month, journal export
- Compliance: remittances tracker, year-end annualization, 2316, alphalist
- Claims & cash advances
- Benefits
- Performance, goals, probation evaluations, 1-on-1s
- Training & certifications
- Employee relations: cases (stepper following the twin-notice process), offense catalog, grievances, policies with acknowledgment tracking
- Offboarding: resignations, clearance board, exit interviews, final pay
- Document templates editor (TipTap with merge-field picker and live PDF preview)
- Helpdesk
- Announcements
- Reports
- Privacy: consents, data subject requests, retention policies
- Settings: company, pay groups, payroll rules, multipliers, attendance rules, leave rules, approval flows, notification templates, sequences, roles & permissions, users, SSO, webhooks, audit log, login history

**Employee portal (`/portal`, installable PWA)**
- Home: clock in/out (geofence + optional selfie via camera), today's shift, leave balances, pending requests, announcements, upcoming holidays
- My Attendance, OT, OB, WFH, shift swap, corrections
- My Leave
- My Payslips, YTD summary, 2316
- My Claims and cash advances (receipt photo upload)
- My Documents (request COE, download generated docs)
- My Assets
- My Benefits (HMO card, dependents)
- My Goals and reviews, self-evaluation
- My Trainings
- Policies to acknowledge
- Helpdesk tickets
- Resignation filing and clearance status
- My Profile + update requests
- Team view for managers

**Public:** careers page and application form per company; document verification page.

**UX requirements:** responsive (portal mobile-first, tested at 375px), dark mode, Filipino-ready i18n, confirmation dialogs for financial/destructive actions, sidebar badge counts, empty states, skeleton loaders, keyboard-accessible (WCAG AA basics), print-friendly payslip and report views.

---

## 11. Reports & Analytics

All built as MongoDB aggregation pipelines in `modules/reports/`, each with a Pydantic filter schema and a matching index review.

**Workforce:** masterlist, headcount by dept/branch/type/gender/age band, new hires & separations, turnover and attrition rate, tenure distribution, probation due, contract expiry, birthdays/anniversaries, requisition vs actual headcount.

**Attendance:** attendance summary, tardiness ranking, absences, OT by department and cost, night diff, roster coverage.

**Leave:** utilization, balances, liability (unused convertible leave valued in pesos).

**Payroll:** payroll register, summary by cost center, variance report, bank file (configurable layouts per bank), payroll journal, loan balances, 13th month summary, labor cost per department.

**Compliance:** SSS, PhilHealth, Pag-IBIG contribution and loan remittance reports, remittance status tracker, BIR monthly withholding summary, 2316, alphalist schedules.

**Talent:** recruitment funnel and time-to-hire, source effectiveness, performance distribution, training hours and cost, certification expiries.

**Relations:** disciplinary cases by type/status, grievance resolution time, policy acknowledgment completion.

All reports: on-screen table + Excel + PDF; heavy ones run in Celery with notification when ready; saved filters; optional scheduled email delivery.

---

## 12. Security, Privacy & Reliability

- RA 10173 (Data Privacy Act): consent capture, purpose notices, data subject requests, retention/anonymization jobs, DPO contact in settings
- Encrypted at rest (app-level AES-GCM, versioned keys from env/secret manager): government IDs, bank accounts, TOTP secrets, disciplinary case details; masked in the API without `view_sensitive`. Also enable MongoDB encryption at rest / Atlas encryption in prod.
- MongoDB: authentication on, least-privilege DB user for the app, TLS in prod, not exposed publicly
- **NoSQL injection guard:** never pass raw request dicts into queries; filters are built only from whitelisted, typed Pydantic fields; reject keys starting with `$` or containing `.`
- JWT: short access TTL, refresh rotation with reuse detection, server-side revocation list; cookies httpOnly/Secure/SameSite; CSRF token on state-changing requests
- Rate limiting, account lockout, optional enforced 2FA for HR/Payroll/Admin roles, idle session timeout
- CORS limited to the frontend origin; security headers (CSP, HSTS, X-Frame-Options) set at nginx
- File uploads: MIME sniffing + size limits, private bucket, signed short-lived URLs, optional ClamAV scan task
- Soft deletes on core records; no hard deletes from UI
- Backups: Atlas continuous backup, or `mongodump` daily (encrypted, off-site) with a documented, tested restore
- Health check endpoint; Flower for Celery; failed-task alerts; Sentry
- Feature flags per company for optional modules

---

## 13. Testing Strategy

- **Unit (pytest):** payroll engine, attendance calculator, leave day counter, annualization, final pay — table-driven with golden fixtures in `tests/fixtures/payroll/`
- **Golden payroll fixtures:** hand-computed employees (monthly, daily, minimum wage, mid-period hire, separation, back-dated salary increase, holiday + rest day + OT + night diff, loans exceeding pay) must match to the centavo
- **API tests (httpx + testcontainers MongoDB replica set):** permissions per role, company isolation, approval transitions, separation of duties, transaction rollback on failure (e.g. a forced error mid-release leaves no partial payslips or loan payments)
- **Property-based tests (Hypothesis)** for leave balance consistency and money rounding
- **Frontend:** Vitest for hooks/utilities; Playwright E2E for login, clock-in, leave file/approve, payroll compute → approve → release, payslip download, resignation → clearance → final pay
- CI runs all of the above on every push; OpenAPI client regeneration is checked for drift.

---

## 14. Phases & Acceptance Criteria

### Phase 0 — Scaffolding
- Monorepo, `uv` project, Docker Compose (api, worker, beat, flower, mongo replica set, redis, mailpit, web, nginx), `.env.example` files
- FastAPI app factory, Beanie init, Celery app, logging, error handler, health check
- Vite React app with Tailwind, shadcn/ui, router, TanStack Query, i18n, PWA plugin
- OpenAPI → TypeScript client generation script
- Cookie-based JWT login/logout/refresh/me end-to-end with CSRF
- GitHub Actions CI (ruff, mypy, pytest with Mongo replica set, frontend lint/typecheck/vitest, Playwright smoke); Sentry wiring optional
- **Done when:** login → me → refresh → logout works from the React app; a test proves a multi-document transaction commits and rolls back; CI green; `/health` OK.

### Phase 1 — Platform Core
- Permissions catalog, roles, users, 2FA, lockout, login history, impersonation
- Tenant repository base with company scoping; audit log hooks
- Companies, branches, departments, positions, salary grades, cost centers, org chart
- Settings, counters, files service (upload + signed URLs)
- **Approval engine** (flows, requests, delegation, escalation via Beat) and My Approvals inbox
- **Notification engine** (templates, preferences, email via Celery, SSE badge counts)
- App shell with permission-based navigation
- **Done when:** each seeded role sees only allowed menus and gets 403 on forbidden endpoints; a test proves company A can't read company B's data through any endpoint; a dummy subject runs through a 2-step flow with delegation.

### Phase 2 — Employees, Documents, Assets, Imports
- Employee CRUD, wizard, profile tabs, `employee_sensitive` with encryption and masking, compensation history (with current snapshot sync), movements, profile update requests
- Document template engine (sandboxed Jinja2 + WeasyPrint) with QR verification; COE request flow
- Assets and assignments
- Generic import pipeline; employee import; opening leave balance and YTD payroll import scaffolds
- Policies and acknowledgments
- **Done when:** HR onboards an employee, issues an asset, generates a COE with a verifiable QR; an employee logs into the portal and sees only their own data; sensitive fields are unreadable in the raw database.

### Phase 3 — Time & Attendance
- Schedules, shifts, roster entries, shift swaps, holidays (nationwide + local per branch)
- Clock-in via portal with geofence/selfie rules, biometric import, manual entry, OB, WFH
- Attendance computation task (nightly Beat + on demand), locking, corrections
- **Done when:** unit tests cover late/undertime/OT/night diff/midnight-crossing shifts/rest day/holiday/double holiday/branch-local holiday.

### Phase 4 — Leave
- Leave types, tenure tiers, eligibility, blackout dates, balances + ledger (transactional), accrual/carry-over/expiry/conversion tasks
- Requests through the approval engine; team calendar
- **Done when:** balances stay consistent across approve → cancel → re-file (including Hypothesis tests); a rebuild-from-ledger job reproduces every balance exactly.

### Phase 5 — Payroll Core
- Pay groups, periods, contribution/tax tables, loans, recurring deductions, adjustments, retro pay
- Pure-Python engine per §8, deduction priority and deferral, variance report
- Compute (Celery, with progress) → submit → approve → release (transaction) → lock, with separation of duties
- Payslip PDF (password-protected email), portal publishing, register, bank file, journal export
- **Done when:** all golden fixtures pass to the centavo; the computer cannot approve their own run; locked periods reject recomputation; a forced failure during release leaves no partial writes.

### Phase 6 — Compliance & Year-End
- Remittance reports and tracker
- 13th month (prorated), annualization, previous-employer income, 2316, alphalist export
- **Done when:** annualization fixtures (refund and payable cases, mid-year hire with previous employer) pass; 2316 PDFs generate for all seeded employees.

### Phase 7 — Claims, Benefits, Self-Service, Helpdesk
- Claims and cash advances with liquidation, paid via payroll
- Benefit plans, enrollments, dependent costs → recurring deductions
- All portal screens, PWA install, announcements, helpdesk
- **Done when:** a claim flows portal → approval → payroll line; all portal flows work at 375px.

### Phase 8 — Talent: Requisition, Recruitment, Onboarding, Performance, Training
- Requisitions, openings, public careers page, applicants, scorecards, offers, hire conversion (transaction)
- Onboarding templates and checklists
- Probation evaluations → regularization; review cycles, goals, 1-on-1s
- Trainings, attendees, bonds, certification expiry reminders
- **Done when:** requisition → opening → public application → offer → hire → onboarding checklist works end-to-end; probation reminder fires and regularization updates the employee.

### Phase 9 — Employee Relations & Offboarding
- Offense catalog, incident reports, disciplinary state machine with twin-notice documents, sanctions (suspension → attendance), grievances (anonymous option)
- Resignation, clearance with auto-generated accountabilities, exit interviews
- Final pay computation and release, separation documents, account deactivation task
- **Done when:** a case goes NTE → explanation → hearing → decision with generated notices; resignation → clearance (blocked by an unreturned asset until returned) → final pay with annualization releases correctly.

### Phase 10 — Reports, Analytics, Privacy, Hardening
- All §11 reports (aggregations) with exports, saved filters, scheduled delivery
- Dashboards finalized
- Privacy: consents, data subject request export, retention tasks
- Performance pass: `explain()` every report and list query, add/adjust indexes, Redis caching for dashboards, load test the payroll compute for 1,000 employees
- Security pass: NoSQL injection tests, header checks, dependency audit (`pip-audit`, `npm audit`)
- **Done when:** all reports export for seeded data; no collection scans on list/report queries (checked with `explain`); full test suites pass; a data subject access request produces a complete export.

### Phase 11 — Integrations & Deployment
- SSO (Google/Microsoft), webhooks via change streams, accounting journal export formats, SMS adapter interface
- Production guide: nginx (static React + reverse proxy + headers), Gunicorn/Uvicorn, Celery worker + beat under systemd/Supervisor, MongoDB Atlas or 3-node replica set, Redis, SSL, backups and restore test, log rotation, monitoring
- `docs/DEPLOY.md`, `docs/USER_GUIDE.md` per role, `docs/PAYROLL_RULES.md`, `docs/DATA_MODEL.md`, go-live checklist (verify contribution/tax tables, import opening balances and YTD, parallel-run one payroll against the old system)

---

## 15. Seed Data

- 1 demo company, 2 branches in different cities (to test local holidays), 6 departments, ~15 positions, salary grades, cost centers
- One user per role with documented dev-only credentials
- 50 employees: regular, probationary (some ending soon), contractual (some expiring), minimum wage earners, daily-paid, night shift, rotating shift
- 2 months of attendance with lates, absences, OT, night shifts, holidays
- Leave requests in every status; one negative-balance attempt
- Loans, recurring deductions, claims, one HMO plan with dependents
- One computed, one approved and one locked payroll period
- One open requisition with applicants in each stage
- One disciplinary case mid-process; one resignation mid-clearance
- Approval flows for every module
- Seeder is idempotent (`python -m seeds run --fresh`)

> ⚠️ **Contribution, tax and holiday tables:** seed with the latest official SSS, PhilHealth, Pag-IBIG and BIR tables and the current year's proclaimed holidays, but the payroll officer must verify them against current agency circulars before go-live. That's why they're effective-dated and editable.

---

## 16. Out of Scope (v3) — later

- Native mobile app (the API already supports it; use bearer tokens instead of cookies for mobile; the portal is a PWA meanwhile)
- Direct biometric device SDK integration (CSV import and kiosk mode cover v1)
- Direct e-filing/e-payment to government portals
- Multi-currency and multi-country payroll rules
- Full LMS (course content, quizzes)
- SaaS self-signup and subscription billing

---

## Appendix — What changed in v3

- **Stack:** Laravel → Python 3.12 + FastAPI + Pydantic v2; MySQL → MongoDB (replica set) with Beanie; Next.js → Vite + React + TypeScript; Laravel queues/Horizon → Celery + Redis + Beat + Flower; Sanctum → cookie JWT with refresh rotation and CSRF; spatie permission/activitylog → custom RBAC dependencies and audit hooks; Pest → pytest + testcontainers + Hypothesis; dompdf → Jinja2 + WeasyPrint + pikepdf.
- **New for MongoDB:** embed-vs-reference rules, `Decimal128` money, multi-document transactions for payroll/leave/final pay, tenant repository, `counters` for sequences, TTL indexes, aggregation-based reports, optional change streams, NoSQL-injection guards, `explain()`-based index review.
- **New for React:** OpenAPI-generated typed client, react-i18next, vite-plugin-pwa, TipTap template editor, SSE notifications.
- All v2 functional scope is unchanged.