# Guide 6: Generate One Artifact with an Online Provider

This guide shows how to use an online LLM provider through a config file. The
same pattern works for OpenAI-compatible providers and Claude when configured.

## 1. Create a lesson folder

```bash
mkdir -p odp-course/06-online-provider/source_docs
mkdir -p odp-course/06-online-provider/fragments
cd odp-course/06-online-provider
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
  --kind product \
  --json
```

## What You Learned

- Provider settings belong in `generation.config.yaml`.
- Secrets stay in environment variables.
- `--kind product` generates one product reference fragment.
