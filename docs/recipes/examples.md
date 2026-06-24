# ODPR Recipe Examples

Examples are separate from packaged starter templates. Starters are copied into
your project by `recipe init`; examples are documentation and test fixtures that
show complete workspace shapes.

Example workspaces live under:

```text
examples/recipes/workspaces/
```

## Included Workspaces

| Workspace | Demonstrates |
| --- | --- |
| `basic-portfolio-build` | Build a portfolio workspace from product inputs. |
| `source-documents-to-fragments` | Generate structured fragments from source documents. |
| `online-llm-fragment-generation` | Hosted provider fragment generation. |
| `local-llm-fragment-generation` | Local provider fragment generation. |
| `catalog-from-existing-fragments` | Assemble an ODPC catalog from fragments. |
| `graph-from-existing-fragments` | Build an ODPG graph from existing fragments. |
| `graph-to-agent-context` | Render graph context for agent use. |

Each example contains:

```text
README.md
AGENTS.md
recipe.yaml
inputs/
outputs-example/
```

## Try an Example

Validate an example recipe:

```bash
open-data-products recipe validate examples/recipes/workspaces/basic-portfolio-build/recipe.yaml --json
```

Plan it without writes or provider calls:

```bash
open-data-products recipe plan examples/recipes/workspaces/basic-portfolio-build/recipe.yaml --json
```

For initialized starter workspaces, you can `cd` into the workspace and omit
the recipe path:

```bash
cd recipes/build-data-product-portfolio
open-data-products recipe plan --json
```

## Outputs

Example `outputs-example/` folders describe expected output shape without
requiring large generated artifacts in the repository. Runtime outputs from
your own recipe runs should go to the workspace output folders declared by the
recipe and runner config.
