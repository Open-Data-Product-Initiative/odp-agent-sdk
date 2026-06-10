# Lecture 11: Working with Online LLM Providers

The SDK supports multiple online providers through config. API keys stay in
environment variables, and the selected provider can change without rewriting
the whole workflow.

## 1. Create a lesson folder

```bash
mkdir -p odps-sdk-guides/11-online-provider/source_docs
mkdir -p odps-sdk-guides/11-online-provider/fragments
cd odps-sdk-guides/11-online-provider
```

## 2. Create a generation config

```bash
cat > generation.config.yaml <<'YAML'
provider: openai
model: gpt-4.1-mini
input: source_docs/
output: fragments/

providers:
  openai:
    type: openai
    model: gpt-4.1-mini
    baseUrl: https://api.openai.com/v1
    apiKeyEnv: OPENAI_API_KEY

  claude:
    type: anthropic
    model: claude-sonnet-4-5
    baseUrl: https://api.anthropic.com/v1
    apiKeyEnv: ANTHROPIC_API_KEY
    version: "2023-06-01"
    maxTokens: 4096
YAML
```

## 3. Export the selected provider API key

For OpenAI:

```bash
export OPENAI_API_KEY="your-api-key"
```

For Claude, change `provider: claude` in the config and export:

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

Do not store API keys in YAML files.

## 4. Add a source file

```bash
cat > source_docs/passenger-flow-product.md <<'MD'
# Passenger Flow Data Product

Airport teams need a reusable data product that combines security queue wait
time, passenger volume, boarding gate allocation, and baggage belt assignment.
The product helps terminal operations teams identify congestion before it
affects departure reliability.
MD
```

## 5. Generate one product fragment

```bash
open-data-products generate \
  --config generation.config.yaml \
  --kind product-reference
```

The default output is meant for humans. Add `--json` when a script or agent
needs a structured generation report.

## What You Learned

- Provider settings belong in `generation.config.yaml`.
- Secrets stay in environment variables.
- Provider defaults can be changed without rewriting the commands.
- You can add more vendor options to the config when they use a supported
  provider type.
- `--kind product-reference` generates one ODPC product reference fragment.
- `--kind odps-product` generates one full ODPS product YAML document.
- `--profile complete-draft` and `--include-components` can draft optional
  ODPS product components for review.

## Next Lesson

Continue to
[Lecture 12: Generating ODPS data products from business requirements](../12-generating-odps-data-products/).
