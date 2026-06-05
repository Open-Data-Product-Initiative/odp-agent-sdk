# SDK Guides

These short guides are designed for learners who want to install the SDK from
PyPI and try practical Open Data Products workflows.

```bash
pip install open-data-products
```

Start with the setup guide if you have never worked with Python, `pip`, PyPI,
or virtual environments before.

The first four workflow guides do not use an LLM. They cover validation,
explanation, vocabulary lookup, and graph conversion.

The last six guides use the SDK generation command. They require Ollama with
Qwen 2.5 or a configured online provider.

## Non-LLM Guides

0. [Set up Python, pip, PyPI, and the SDK](00-setup-python.md)
1. [Validate an ODPS product](01-validate-product.md)
2. [Explain and summarize a product](02-explain-and-summarize.md)
3. [Use the ODPV vocabulary helpers](03-use-vocabulary-helpers.md)
4. [Convert GraphML to ODPG and open an explorer](04-convert-graph-to-odpg.md)

## LLM Generation Guides

1. [Generate one signal fragment with Ollama](05-llm-generate-one-signal.md)
2. [Generate one artifact with an online provider](06-llm-use-online-provider.md)
3. [Generate a full fragment set from source documents](07-llm-generate-fragment-set.md)
4. [Full cycle: source docs to catalog HTML and graph explorer](08-llm-full-cycle-catalog-and-graph.md)
5. [Build catalog and graph from the same fragments](09-build-catalog-and-graph-from-fragments.md)
6. [Generate ODPS products from transcripts and email](10-generate-odps-products-from-transcripts.md)
