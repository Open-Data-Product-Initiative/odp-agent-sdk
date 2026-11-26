# Data product idea: one-pager

Use this short, plain-language template to describe a data product idea. Write a
few sentences for each question. You do not need to know technical terms, data
formats, schemas, contracts or service levels. If something is unknown, say so.

Copy the template into a new text or Markdown document and fill in what you know.

```text
DATA PRODUCT IDEA

Working name:
[A short name for the information or capability.]

1. What problem are we trying to solve?
Describe the current difficulty and what should improve.

2. Who needs this, and what will they do with it?
Describe the people or teams and give one example of a decision
or task they want to support.

3. What information do they need?
Describe the important information in everyday language.
You can mention example questions they want to answer.

4. What would a useful result look like?
Describe what people should be able to do or understand
when this is working.

IF YOU KNOW

- Where might the information come from?
- How current or reliable does it need to be?
- Are there sensitive uses, restrictions or things to exclude?
- Who can help answer questions about this idea?
```

## What is needed and what can wait?

The working name and four numbered answers are the minimum useful starting
point. They give the assistant a business problem, users and a use case, the
information needed, and an initial way to discuss success. An answer can be
short or state what is still unknown.

Sources, freshness, reliability, restrictions and a contact are helpful when
known. They can remain open initially. If an important restriction or service
expectation is unknown, record the gap instead of guessing it.

## Using the one-pager with the SDK

The one-pager is source material for a draft, not an approved specification or
an implementation plan. The assistant should distinguish what the document says
from catalog evidence and its own proposals, and record missing decisions.

The guided handover workflow can generate an ODPS draft from the one-pager and
then prepare the package. It shows the source content before provider calls and
requires review. The lower-level handoff interface also accepts an existing ODPS
draft. See the [handoff guide](../integrations/handoff.md) for configuration,
package generation and delivery. A short brief does not
establish source mappings, contract terms or implementation readiness.
