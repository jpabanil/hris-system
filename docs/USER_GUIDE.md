# User guide

Sign in at `/login`. The demo company is Demo Trading Co. Every account uses the password `ChangeMe123!`.

| Email | Role | What you can do |
| --- | --- | --- |
| super@demo.example.com | Super Admin | Everything, including creating companies |
| hr.admin@demo.example.com | HR Admin | Organization, people, payroll, and settings except creating companies |
| hr.staff@demo.example.com | HR Staff | HR work except payroll and settings changes |
| payroll@demo.example.com | Payroll Officer | Compute payroll and edit contribution and tax tables |
| approver@demo.example.com | Payroll Approver | Approve and release a run computed by someone else |
| finance@demo.example.com | Finance | Read payroll, approve claims, export reports |
| manager@demo.example.com | Department Manager | Team attendance and leave, approvals, performance |
| recruiter@demo.example.com | Recruiter | Requisitions, applicants, and onboarding |
| employee@demo.example.com | Employee | Own portal: profile, leave, payslips |
| auditor@demo.example.com | Auditor | Read-only access, including the audit log |

The public careers page is `/careers/demo`. A document verification link looks like `/verify/{code}`.

Payroll officers confirm the seeded SSS, PhilHealth, Pag-IBIG, tax, and 2026 holiday rows against the current circulars before a live payroll. Eid dates are not seeded; Proclamation No. 1006 left those for a later issuance. The 16 October 2026 Cebu row is sample data for a city holiday.
