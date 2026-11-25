---
product_id: product-holdings
product_name: Product Holdings
domain: optional
status: proposed
version: 0.1.0
---

# Product Holdings

## Overview

Product Holdings is a proposed banking data product for the Retail Banking Customer Growth and Risk Portfolio. It gives authorised teams and agents a consistent view of customer information so they can reason about customer growth, engagement, credit, fraud, and collections activity without rebuilding context from source systems.

For this PoC, the product is fictional and uses draft service and quality expectations. It is written as source material for Maysano product generation, not as a final production contract.

## Business need

Retail banking teams need a trusted way to connect product holdings evidence with customer decisions. Without this product, analysts and agents must infer context from fragmented operational systems, which creates inconsistent eligibility decisions, delayed risk response, and weak explanations when business users ask why a recommendation or alert was produced.

## Product purpose

The product exists to support Next best offer, Customer churn prevention, Credit risk assessment. It helps consumers identify the relevant customer, understand the current business situation, check restrictions, and decide whether the next action should be a recommendation, review, escalation, suppression, or operational follow-up.

## Primary consumers

- Portfolio Intelligence Team
- Decision Intelligence Data Team
- Customer Experience Team
- Retail Credit Risk Team
- Financial Crime Team
- AI agents retrieving portfolio memory for grounded next-action support

## Consumer needs

- Stable identifiers that can be joined to Customer Master and related products.
- Current status, trend, or score information that is recent enough for operational decisions.
- Clear data quality and freshness metadata so agents can decide whether evidence is usable.
- Governance flags that prevent unsupported marketing, credit, fraud, or collections use.
- Named ownership and support paths for data issues, stale outputs, and disputed evidence.

## Product scope

### Included

- Curated product holdings records for active and recently inactive retail banking customers.
- Attributes needed to support the named PoC use cases and dependency traversal.
- Draft quality rules, service expectations, ownership context, and operational response guidance.
- Relationship references to upstream and downstream products in this portfolio.

### Excluded

- Wholesale, corporate, treasury, and investment banking records.
- Raw event payloads that have not passed identity, timeliness, and validity checks.
- Final legal interpretation of regulatory obligations.
- Formal portfolio objectives or use-case records, which remain portfolio-level inputs in Maysano.

## Key entities

- Customer
- Product holding
- Relationship

## Important attributes and measures

- product_type
- holding_status
- open_date
- close_date
- primary_product_flag
- cross_sell_gap
- data_quality_status
- source_refresh_timestamp
- permitted_use_indicator

## Source context

- Current Accounts
- Savings Accounts
- Loan Accounts
- Card servicing platform

The PoC assumes these sources are represented by fictional Maysano Bank systems. Exact technical interfaces are intentionally omitted unless they matter to the business need.

## Update expectations

- Update frequency: Draft daily batch for curated profile fields, with intraday refresh where the source is event-driven.
- Expected freshness: Draft target of less than 24 hours for portfolio traversal and less than 2 hours for operational risk signals when applicable.
- Processing window: Draft overnight processing between 01:00 and 05:00 Gulf Standard Time, with exception handling before business opening.
- Known timing differences: Channel, payment, credit, and case-management sources may arrive at different times, so consumers must inspect source_refresh_timestamp before acting.

## Data quality expectations

- Completeness: Draft target of 98 percent for mandatory identifiers and status fields.
- Accuracy: Values must reconcile to nominated source systems within agreed tolerance before publication.
- Timeliness: Records older than the stated freshness target must be marked stale.
- Uniqueness: One current record per customer, account, case, device, or product key as appropriate.
- Referential integrity: Customer references must resolve to Customer Master unless documented as pending onboarding.
- Valid values: Status, segment, score, and indicator fields must use controlled vocabularies.

## Service expectations

- Availability: Draft target of 99.5 percent during banking business hours.
- Delivery timing: Draft daily publication by 06:00 Gulf Standard Time.
- Incident acknowledgement: Draft acknowledgement within 60 minutes for high-impact quality or availability issues.
- Recovery expectation: Draft same-business-day recovery for failed daily loads when source data is available.
- Support ownership: Decision Data Operations coordinates incidents with Decision Platform Engineering.

## Governance and sensitivity

- Classification: Confidential internal banking data.
- Personal data: Yes, customer and relationship identifiers are present.
- Financial data: Yes when balances, transactions, credit, or risk indicators are included or derived.
- Consent requirements: Marketing and engagement uses must respect Customer Consent and Customer Contact Preferences.
- Retention: Draft seven-year analytical retention unless a stricter source or regulatory rule applies.
- Access restrictions: Access is limited to approved portfolio, risk, operations, and service roles.
- Regulatory relevance: Consumer protection, privacy, credit conduct, anti-fraud, and financial crime obligations may apply depending on use.
- Permitted uses: Next best offer, Customer churn prevention, Credit risk assessment when quality, consent, and access checks pass.
- Prohibited uses: Unexplained adverse action, unsupported automated decline, unauthorised marketing, or employee browsing.

## Ownership context

- Business owner: Portfolio Intelligence Team
- Product owner: Decision Intelligence Data Team
- Data steward: Portfolio Data Stewardship
- Technical owner: Decision Platform Engineering
- Support team: Decision Data Operations

## Dependencies

### Likely upstream products

- Current Accounts
- Savings Accounts
- Loan Accounts
- Customer Master

### Likely downstream products

- Customer 360
- Customer Segmentation
- Customer Lifetime Value
- Campaign Eligibility

## Portfolio context references

- Relevant objectives: Increase profitable customer growth, Reduce customer and credit risk
- Relevant use cases: Next best offer, Customer churn prevention, Credit risk assessment
- Evidence role: Product Holdings can provide direct or supporting evidence when an agent explains affected use cases, owners, dependencies, and next actions.

## Usage examples

- A service agent checks Product Holdings before deciding whether a customer outreach action is appropriate.
- A risk analyst reviews Product Holdings alongside upstream and downstream products to explain a risk or collections decision.
- An AI agent starts from a customer situation, retrieves Product Holdings, follows its dependency links, checks ownership, and proposes an operational response grounded in graph facts.

## Known risks and limitations

- Draft PoC thresholds may not match production policy and must not be used as final controls.
- Delayed or missing upstream data can make the product appear complete while recent events are absent.
- Identity resolution issues may merge or split customer context incorrectly.
- Derived indicators can encode historic process bias if source handling was inconsistent.
- Product references are business relationships for graph creation and still need validation against generated ODPS YAML.

## Operational response expectations

- Start a data quality review when mandatory identifiers, status fields, or controlled values fail validation.
- Notify Decision Intelligence Data Team and affected downstream owners when freshness or availability targets are missed.
- Check affected consumers and use cases before allowing automated recommendations, alerts, or prioritisation to continue.
- Publish an impact summary when a defect affects customer treatment, credit assessment, fraud investigation, or collections action.
- Restrict use until the issue is resolved if consent, access, or regulatory controls cannot be verified.

## Success criteria

- Consumers can understand what Product Holdings represents, who owns it, and when it was refreshed.
- The product links coherently to at least two meaningful portfolio relationships unless it is a root reference product.
- Quality and service metadata are sufficient for an agent to decide whether evidence can be used.
- The product supports the planned PoC traversal without requiring ungrounded assumptions.
