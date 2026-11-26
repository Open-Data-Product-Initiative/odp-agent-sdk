# Data product idea: Product Holdings

This is a fictional banking example for testing. The details and targets below are invented for the exercise.

**Working name:** Product Holdings

## 1. What problem are we trying to solve?

Customer service agents and relationship managers cannot see a customer's banking products in one place. Account, card and loan information sits in separate systems. Before answering a question or preparing for a meeting, employees open several applications and compare records by hand.

This takes time and creates inconsistent answers. It also leads to avoidable conversations about products a customer already holds. We want an overview that helps staff see a customer's current products and recently closed products in one place.

The first version supports employees serving individual customers. It does not make recommendations, decide whether a customer qualifies for a product, or replace the source systems.

## 2. Who needs this, and what will they do with it?

**Customer service agents** need a quick overview when a customer contacts the bank. An agent should be able to answer: “Does this customer currently have a credit card?” and see whether a loan has recently closed. The agent still uses the source system to change an account or investigate a transaction.

**Relationship managers** need the same overview before a customer meeting. They use it to understand which types of products the customer already holds and to prepare relevant questions. The overview must not be used on its own to decide that a customer is eligible for an offer.

**A customer service team lead** wants to understand whether staff are spending less time checking multiple systems and whether they trust the overview enough to use it in their daily work.

The product is for authorised internal employees. Customers do not access this first version directly.

## 3. What information do they need?

For a selected customer, show a separate entry for each account, card or loan the customer holds. The first version should include active products and products closed during the previous 90 calendar days. It should not include applications that never became active.

For each entry, the teams need:

- A customer reference that lets an authorised user find the right person.
- A reference for the individual account, card or loan, suitable for opening the related record in its source system.
- The product category: account, card or loan.
- The product name or type as it appears in the source system, for example current account or credit card.
- The holding status: active, closed or unknown. A status that cannot be interpreted should appear as unknown and be identified for follow-up.
- The date the product was opened and, for a closed product, its closing date when available.
- The name of the source system and the time that source last supplied the information.
- A clear indication when the information is delayed or when one of the source systems has not supplied its expected update.

If a customer has two cards, both should appear. A product held jointly should appear for each customer linked to that product. The customer and data teams still need to agree how joint ownership is represented and how the same customer is identified across systems.

The first version must not show account balances, transaction details, payment-card numbers, credit scores or loan repayment histories. Those details remain in their source systems.

## 4. What would a useful result look like?

An agent selects a customer and sees a single overview of that customer's accounts, cards and loans, including recently closed products. The agent can identify the source system and see when each source last supplied an update.

In an initial staff trial, we would consider the result useful if:

- A customer service agent can find the customer's products without opening all three source systems.
- The median time to prepare a product overview is at least 30% lower than the team's current manual process. The team lead will establish the baseline before the trial.
- At least 90% of trial users say the overview helps them prepare for a customer interaction.
- Known missing or delayed source updates are visible to the user rather than appearing as an empty list of products.

The team will measure these outcomes during a four-week trial. These targets are proposed for this example and need agreement before delivery.

## If you know

### Where might the information come from?

The account management system holds account records, the card management system holds card records, and the loan system holds loan records. The customer master system holds the customer reference used by service teams.

The Product Holdings catalog in OpenMetadata may describe some of these assets. The data teams should confirm which catalog entries correspond to the systems, which fields represent open and close dates, and whether the customer reference in each system maps to the customer master.

No source table, join rule or source-system connection has been confirmed yet. In particular, the teams need to establish whether a card is represented independently of the account that funds it and how joint products should be linked to customers.

### How current or reliable does it need to be?

The overview should be refreshed on each UAE business day and available to staff by 08:00 Abu Dhabi time. Each source should provide its latest available update before that deadline. A record should show the time of the latest successful update from its source.

If an expected source update has not arrived by 08:00, the overview should identify the affected source as delayed. Staff should still be able to see the last available information with its update time. The data operations team should investigate the delay during its normal support hours.

For the initial trial, the data teams should compare the overview with a sample of records from each source and investigate any discrepancies. The sample size, acceptable discrepancy rate and escalation process remain to be agreed.

### Are there sensitive uses, restrictions or things to exclude?

The overview identifies customers and must be available only to authorised customer service and relationship teams. Access should follow the bank's existing staff access controls. The team must confirm with data protection which staff roles may see each product category.

The overview is for servicing and meeting preparation. It must not be used as the sole basis for marketing eligibility or automated recommendations. Marketing consent and contact preferences are outside the first version; teams must use their existing approved process before contacting a customer about an offer.

Do not include account balances, transaction details, payment-card numbers, credit scores or loan repayment histories in the first version. Retention and audit requirements remain to be confirmed.

### Who can help answer questions about this idea?

- The customer service product owner can confirm the user needs, the 90-day window and trial measures.
- The relationship management lead can confirm meeting-preparation needs.
- Representatives from the account, card, loan and customer master data teams can identify sources and agree matching rules.
- Data operations can confirm publication timing, delay handling and support arrangements.
- The data protection team can confirm permitted uses, staff access and retention requirements.

Named contacts have not yet been assigned.
