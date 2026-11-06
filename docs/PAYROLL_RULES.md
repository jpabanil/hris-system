# Payroll rules

These rules match `app/domain/payroll_engine.py`. Rates, brackets, multipliers, ceilings, and deduction order are data (`settings`, `tax_tables`, `contribution_tables`), not constants in the routers.

## Pay bases

- Monthly: period basic = monthly salary × 12 / periods per year. A partial period (hire, separation, or a salary slice) scales that amount by days employed / working days, or by the salary slices when a rate changes inside the period.
- Daily: basic = daily rate × days worked. Unpaid absences are already out of days worked. Late and undertime are still deducted at the hourly rate.
- Hourly: basic = hourly rate × hours worked.
- Daily rate for a monthly employee = monthly × 12 / factor days (default 261, from payroll settings). Hourly = daily / 8.

## Premiums

Each premium row is `hourly rate × hours × multiplier`. The multiplier is the factor to apply, taken from payroll settings `ot_multipliers`. Seeded Labor Code factors:

| Code | Factor |
|---|---|
| regular_ot | 1.25 |
| rest_day | 1.30 |
| rest_day_ot | 1.69 |
| special_non_working | 1.30 |
| special_non_working_ot | 1.69 |
| regular_holiday | 2.00 |
| regular_holiday_ot | 2.60 |
| regular_holiday_rest | 2.60 |
| double_regular | 3.00 |
| night_diff | 0.10 |

Night differential is an extra 10% (factor 0.10), not a replacement of the hour. Overtime hours are not already inside basic, so they use the full statutory factor.

Monthly-paid unworked regular holidays are inside the monthly basic when `monthly_includes_unworked_holiday` is true (the default). Daily-paid unworked regular holiday pay is a separate premium the attendance service adds when the employee was present or on paid leave the workday before.

## Order

1. Basic pay, prorated for hire, separation, and in-period salary changes.
2. Subtract absences, leave without pay, and suspension for monthly employees, plus late and undertime for every basis.
3. Add overtime, holiday, rest day, and night differential.
4. Add allowances. A de minimis amount stays non-taxable until its annual ceiling; the excess becomes taxable before tax is computed.
5. Subtract the employee share of SSS, PhilHealth, and Pag-IBIG. A monthly amount is split, taken on the first cutoff, or taken on the second cutoff, from settings `contribution_timing`. One period in the month always takes the full amount.
6. Withholding tax on the taxable result, using the frequency's tax table. Minimum wage earners are taxed only on non-statutory taxable allowances and adjustments. Basic pay, overtime, holiday pay, and night differential are exempt for them.
7. Non-taxable allowances stay in gross and outside the tax base.
8. Loans, recurring deductions, cash-advance recovery, and other deductions, in `deduction_order`.
9. Net pay. If deductions do not fit, the lowest priority items are deferred and the payslip is flagged. Net is never negative.

## Statutory lookup (seed, verify before go-live)

- SSS 2026 shape: 15% of monthly salary credit, employee 5%, employer 10%, MSC 5,000–35,000 in 500 steps. MSC below 5,250 is 5,000. MSC at 34,750 and above is 35,000. EC is 10 below MSC 15,000 and 30 from 15,000. The portion of MSC above 20,000 is the mandatory provident fund, included in the 5% / 10% shares.
- PhilHealth: 5% of monthly basic, floor 10,000, ceiling 100,000, split equally.
- Pag-IBIG: employee 1% at 1,500 or below, otherwise 2%, employer 2%, fund salary capped at 10,000 (200 + 200).

## Controls

- The user who computed a run cannot approve it.
- Payroll actions are refused while a super admin is impersonating.
- Approved, released, and locked periods are not recomputed. Corrections are adjustments on a later period.
- Release publishes payslips, writes loan payments, and updates loan balances in one MongoDB transaction.
- Payslips store the snapshot and year-to-date totals used for that run.
- 13th month is basic salary actually earned in the year, divided by 12. The non-taxable ceiling for 13th month and other benefits defaults to 90,000 and is editable.
- Annualization compares the annual table to tax already withheld, including previous-employer income. A negative result is a refund.
