# Source Documents For Local Generation

This folder is a generic input area for local LLM generation. Put plain source
documents here, such as Markdown notes, text briefs, copied requirements, or
other business material. The files are intentionally not ODPS, ODPC, or ODPG
YAML fragments yet.

## How Filenames Are Used

The generator reads every `.md` and `.txt` file in this folder and includes the
filename in the prompt as a source boundary:

```text
--- Source file: turnaround-delay-signal.txt ---
...
```

That filename helps the local model understand what each document is about. The
current SDK does not route files by filename. For selected-kind generation,
such as `--kind product`, each source document is processed separately with the
selected prompt so multiple product source files can produce multiple product
reference fragments.

The words in filenames still matter because the model sees them. Including
terms such as `product`, `use-case`, `objective`, or `signal` makes it more
likely that the model extracts the right kind of artifact from that source
document, but this is prompt guidance, not deterministic file routing.

Final fragment filenames are not copied from source filenames. They are derived
from the generated YAML object ids:

- `productReference.id` -> `product_reference_<id>.yaml`
- `useCase.id` -> `use_case_<id>.yaml`
- `businessObjective.id` -> `business_objective_<id>.yaml`
- `signal.id` -> `signal_<id>.yaml`

Use descriptive lowercase filenames with hyphens when possible. Recommended
patterns are `*-product.md`, `*-signal.txt`, `*-use-case.md`, and
`*-objective.txt`. Good source filenames make the model more likely to infer
the intended artifact type and name, for example:

- `customer-churn-risk-signal.txt`
- `subscription-retention-use-case.md`
- `customer-analytics-product.md`
- `reduce-support-resolution-time-objective.txt`

Avoid vague names such as `notes.md`, `doc1.txt`, or `draft-final.md` because
they give the model less context. If several source files describe one domain,
keep their names specific to the concept each file covers.

The set mixes Markdown and text documents so a local model can practice turning
business prose into:

- ODPC productReference fragments for data products
- ODPC useCase, businessObjective, and signal fragments
- ODPG graph YAML that connects the generated objects

The bundled sample documents happen to use an airport and flight-operations
topic so the generated outputs are easy to inspect, but the tooling is not
topic-specific. Replace these files with any source documents for your domain.
