# Email thread: Support Operations Performance Product

From: Elena, VP Customer Support
To: Data Products Team
Subject: Support operations data product request

We need a product that gives support leaders a consistent view of ticket
backlog, first response time, escalation pressure, support sentiment, and team
capacity. Today every support manager builds their own spreadsheet from Zendesk,
workforce planning, and customer-health exports.

The intended product should be called Support Operations Performance. It should
serve support leads, escalation managers, and service operations analysts. The
main decisions are daily queue prioritization, staffing adjustments, and
identifying accounts where slow response could create renewal risk.

Data sources mentioned in the intake call:
- Zendesk ticket events and ticket status history
- Workforce planning schedule
- Customer account tier and renewal date
- Survey sentiment after support case closure
- Escalation queue events

Expected quality:
- Ticket data should refresh every hour during business days.
- Account and renewal metadata can refresh daily.
- Missing ticket owner or missing severity should be treated as a quality issue.
- Duplicate ticket events should be monitored.

Access:
- Internal only for the first release.
- Support leads can see team-level and account-level metrics.
- Sensitive free-text ticket comments should not be exposed in the first version.

Commercial notes:
- No external price is defined.
- If a pricing section is drafted, mark it for review and keep it as internal
  allocation or zero-price starter language.
