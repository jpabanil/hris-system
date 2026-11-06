# Data model

MongoDB database `hris`. Every Beanie document under `backend/app/modules/*/models.py` and `backend/app/shared/models.py` is one collection. There are about 110 collections.

## Rules

- `_id` is an ObjectId. Foreign keys and `company_id` are the string form of that id.
- Tenant collections include `company_id`. Reads and writes go through `TenantRepo`, which filters `company_id` and `deleted_at: null`.
- `companies` has no `company_id`. A company is the tenant.
- Money fields are BSON `Decimal128`. The API accepts decimal strings. Floats are rejected.
- Day counts and hour quantities that are not money are decimal strings. Minutes are integers.
- Government IDs, bank account numbers, 2FA secrets, and disciplinary details are AES-GCM ciphertext prefixed with `v1:`.
- `deleted_at` is a soft delete. `revision` is optimistic concurrency. A stale revision returns 409.
- `created_at`, `updated_at`, `created_by`, and `updated_by` are on audited documents. Timestamps are UTC.
- Document numbers come from `counters` with an atomic increment.
- `idempotency_keys` expires after 24 hours. Clock-in and payroll compute send an idempotency key.
- `compensation_history` is append-only. `employee_sensitive` is one row per employee.
- `leave_ledger.days` is signed. A balance is the sum of its ledger rows.
- A payslip stores the lines, the year-to-date snapshot, and the employee snapshot used for that run.
- Approval requests point at a flow. The handler for `subject_type` runs when the request finishes.

## Payroll documents

`pay_groups`, `payroll_periods`, `payroll_runs`, `payslips`, `contribution_tables`, `tax_tables`, `loans`, `loan_payments`, `recurring_deductions`, `adjustments`, `retro_adjustments`, `ytd_openings`, `previous_employer_income`.

The pure computation lives in `app/domain/payroll_engine.py`. The stored tables are what the payroll officer edits. Rules are in `docs/PAYROLL_RULES.md`.
