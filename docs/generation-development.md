# Generation Development Notes

This page explains how LLM generation is wired inside the SDK. It is intended
for contributors who change prompts, provider handling, normalization, or
validation behavior. User-facing setup and command examples stay in
[`docs/generation.md`](generation.md).

Generation is intentionally conservative: LLM output is treated as a draft that
must pass local parsing, normalization, and validation before the CLI reports it
as valid.

## Entry Points

The public Python entry points live in `open_data_products.generation`:

- `generate_local_artifact(kind, source, output_dir, ...)` generates one
  selected artifact from one file or folder.
- `generate_local_artifacts_for_kind(kind, source, output_dir, ...)` processes
  each `.md` or `.txt` source file separately for the selected kind.
- `generate_local_artifacts(source_dir, output_dir, ...)` is the older holistic
  ODPC/ODPG flow that generates several fragment kinds and then a graph.

The CLI command `open-data-products generate` resolves config and provider
settings in `open_data_products.cli`, then calls
`generate_local_artifacts_for_kind()`.

## Provider Flow

Generation settings are resolved before prompts run:

1. Load the generation config, if provided.
2. Merge CLI overrides for provider, model, input, output, and prompt folder.
3. Resolve the provider profile.
4. Create a model client for Ollama, OpenAI-compatible completion,
   OpenAI-compatible chat, or Anthropic.
5. Fail early if required provider settings or secret environment variables are
   missing.

Prompt templates are loaded from bundled package data unless `--prompts` or
`prompt_dir` points to a project-owned prompt folder.

## Artifact Kinds

The selected `--kind` controls the generation task:

- `product-reference`
- `odps-product`
- `use-case`
- `objective`
- `signal`
- `graph`

Most selected kinds use one prompt and then validate the generated YAML as an
ODPC fragment or ODPG graph. `odps-product` is different: it uses a multi-call
pipeline because full ODPS product YAML has more structure and higher
hallucination risk.

## ODPS Product Pipeline

For `--kind odps-product`, each source file becomes one ODPS product candidate.
Folder input is processed file by file.

The pipeline is:

1. Load source text with source-file boundaries.
2. Extract product facts with `odps_product_facts.md`.
3. If `--max-source-chars` is set and the source is longer than the limit,
   split the source, extract facts per chunk, then merge them with
   `odps_product_merge_facts.md`.
4. Generate minimal ODPS YAML with `odps_product_minimal_yaml.md`.
5. If components are requested, draft only those components with
   `odps_product_component_draft.md`.
6. Assemble the minimal document and drafted components with
   `odps_product_assemble_yaml.md`.
7. Normalize known LLM output mistakes.
8. Validate the generated document.
9. If validation fails, run one repair prompt with
   `odps_product_repair_yaml.md`, normalize again, and validate again.
10. Write the artifact and include validation errors, review notes, drafted
    components, and evidence gaps in the `--json` response.

Only one repair pass is run. If the repaired document still fails validation,
the artifact is written with `valid_yaml: false` and the validation errors are
returned.

## Profiles And Components

The ODPS product profile controls which optional components are requested:

- `minimal` is the default. It asks for evidence-backed product details only.
- `complete-draft` requests `SLA`, `dataQuality`, and `pricingPlans`.

`--include-components` adds explicit components on top of the selected profile.
Supported component names are normalized through
`ODPS_PRODUCT_COMPONENT_ALIASES`. Unknown names fail before any LLM call.

Current ODPS component names are:

- `contract`
- `SLA`
- `dataQuality`
- `pricingPlans`
- `license`
- `dataAccess`
- `dataHolder`
- `paymentGateways`
- `productStrategy`

## Prompt Responsibilities

Each ODPS prompt has one job:

- `odps_product_facts.md`: extract facts, evidence gaps, and conservative
  source-backed product information.
- `odps_product_merge_facts.md`: merge chunk-level fact YAML without inventing
  missing details.
- `odps_product_minimal_yaml.md`: create the minimal schema-facing ODPS
  document.
- `odps_product_component_draft.md`: draft only requested optional components
  and return `reviewNotes`, `evidenceGaps`, and `draftedComponents`.
- `odps_product_assemble_yaml.md`: combine minimal YAML and component YAML into
  one final ODPS document.
- `odps_product_repair_yaml.md`: fix validation errors while preserving
  supported content.

Prompt examples must be schema-facing, not SDK-internal. For example,
`SLA` and `dataQuality` must use `declarative` arrays with `dimension` keys;
they must not use the SDK model's internal `profiles` shape.

## Normalization Layer

Normalization lives in `_normalize_generated_output()` and the ODPS-specific
helpers below it. The goal is to correct common model mistakes without
inventing business facts.

Current ODPS normalization includes:

- moving flat product detail fields into `product.details.en`;
- mapping unsupported product type aliases such as `API` to valid ODPS product
  types;
- converting `SLA` to schema-facing `declarative` arrays;
- converting `dataQuality` to schema-facing `declarative` arrays;
- normalizing SLA and data quality dimension aliases;
- converting legacy `pricingPlans.plans` into
  `pricingPlans.declarative.en`;
- removing unsupported pricing fields such as `planID`, `currency`,
  `billingCycle`, `conditions`, and nested condition objects;
- preserving supported pricing notes;
- preserving pricing references to named packages only;
- normalizing `dataAccess.outputPorttype` to `outputPortType`.

Normalization must stay conservative. It can reshape known fields, map known
aliases, and drop unsupported keys. It should not fabricate service levels,
prices, contacts, license rights, or data quality objectives.

## Pricing References

Pricing plans can contain reference objects under these ODPS pricing fields:

- `paymentGateway`
- `dataQuality`
- `SLA`
- `access`

The generator preserves reference objects only when the `$ref` ends in a named
package or profile such as `default`, `premium`, or `API`.

Valid pattern:

```yaml
pricingPlans:
  declarative:
    en:
      - name: Internal Starter
        priceCurrency: USD
        price: "0"
        unit: On-request
        dataQuality:
          $ref: "#/product/dataQuality/default"
        SLA:
          $ref: "#/product/SLA/default"
        access:
          $ref: "#/product/dataAccess/API"
```

Invalid pattern:

```yaml
pricingPlans:
  declarative:
    en:
      - name: Internal Starter
        SLA:
          $ref: "#/product/SLA/0"
```

Do not teach numeric endings such as `/0` in prompts or examples.

## Validation And Repair

Generation validation is stricter than checking whether YAML parses.

For ODPS products, validation runs through `validate_document()` so generated
documents are checked against the v4.1 raw shape and SDK model rules. Validation
errors feed the repair prompt.

Known compatibility note: the bundled ODPS schema and SDK parser currently
disagree about `dataAccess` object versus array shape. Generation keeps the
SDK-compatible shape and filters only that contradictory schema error. Do not
use this exception as a pattern for new components.

For ODPC fragments, generated output is wrapped in a temporary catalog and
validated with `validate_catalog()`. Signal generation also has extra quality
checks for generated ids.

For ODPG graphs, generated output is validated with `validate_graph()` and
checked for coverage of generated ODPC fragment nodes.

## JSON Result Fields

`GeneratedArtifact.to_dict()` includes:

- `name`
- `prompt`
- `output`
- `valid_yaml`
- `errors`
- `review_notes`
- `drafted_components`
- `evidence_gaps`

For `odps-product`, the top-level CLI JSON response also includes:

- `profile`
- `include_components`
- `max_source_chars`

The field name `valid_yaml` is historical. For ODPS products, it now means the
document parsed and passed the generation validation path, except for the
documented `dataAccess` compatibility filter.

## Long Sources

`--max-source-chars` applies only to `odps-product`.

When set, source text longer than the limit is split before fact extraction.
Each chunk is sent through the facts prompt. The chunk facts are then merged and
used as the input for minimal YAML generation and optional component drafting.

Chunking should preserve paragraph boundaries where possible and hard-wrap only
when a single paragraph exceeds the limit.

## Test Expectations

Add or update tests when changing any generation behavior:

- Prompt inventory and rendering: `tests/test_generation_prompts.py`.
- ODPS product pipeline behavior: `tests/test_generation_prompts.py`.
- CLI JSON and provider behavior: `tests/test_functional_cli.py`.
- SDK parser compatibility for generated schema-facing ODPS shapes:
  `tests/test_core.py`.
- Cross-spec validation behavior: `tests/test_agent_api.py`.

Use fake model clients in tests. Do not call live providers from unit tests.

For behavior changes, add the failing regression first. Examples:

- A new hallucinated field should have a test showing it is dropped or
  normalized.
- A new valid ODPS shape should have a test showing it survives normalization
  and validates.
- A prompt pipeline change should assert the expected prompt order.
- A CLI output change should assert the JSON payload.

## Contributor Checklist

Before marking a generation change complete:

1. Confirm prompt examples are schema-facing and do not use SDK-internal shapes.
2. Confirm normalization does not invent business facts.
3. Confirm validation errors still trigger one repair pass.
4. Confirm generated pricing references end in named packages, never numeric
   indexes.
5. Run focused tests for the changed area.
6. Run the repository checklist from `AGENTS.md`.
