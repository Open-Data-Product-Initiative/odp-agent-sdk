# Z.ai GLM Generation

This guide shows how to use the SDK with Z.ai GLM models through the general
Z.ai OpenAI-compatible API. The bundled provider preset is `zai`.

Use this mode when you want hosted GLM inference for SDK generation without
writing a custom provider profile.

## Provider Shape

The `zai` preset uses the SDK's existing OpenAI-compatible Chat Completions
client:

```yaml
providers:
  zai:
    type: openai-chat
    model: glm-5.2
    baseUrl: https://api.z.ai/api/paas/v4
    apiKeyEnv: ZAI_API_KEY
```

Z.ai's OpenAI-compatible API documentation uses the same general base URL and
shows `ZAI_API_KEY` as the environment variable for API-key based access:

- [Z.ai OpenAI Python SDK guide](https://docs.z.ai/guides/develop/openai/python)

The SDK calls `baseUrl + /chat/completions`, so this preset targets:

```text
https://api.z.ai/api/paas/v4/chat/completions
```

## Coding Plan Boundary

Z.ai also documents a separate GLM Coding Plan endpoint:

```text
https://api.z.ai/api/coding/paas/v4
```

That endpoint is for Coding Plan subscription usage and supported coding tools.
The bundled SDK preset intentionally uses the general API endpoint instead. If
you need to test the Coding Plan endpoint, copy the generation config and add a
project-owned provider entry rather than changing the bundled `zai` preset.

## 1. Set The API Key

Create a Z.ai API key in the Z.ai console, then export it before running SDK
generation:

```bash
export ZAI_API_KEY="..."
```

Do not store API key values in `generation.config.yaml`. The config should only
name the environment variable.

## 2. Run Generation With The Bundled Preset

Generate one signal fragment:

```bash
open-data-products generate \
  --provider zai \
  --model glm-5.2 \
  --input source_docs/signals/ \
  --kind signal \
  --output generated/ \
  --json
```

Generate ODPS product reference artifacts from product notes:

```bash
open-data-products generate \
  --provider zai \
  --model glm-5.2 \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/ \
  --json
```

Then validate the generated YAML:

```bash
open-data-products validate generated/*.yaml
```

## 3. Use A Project Config

Copy the bundled generation config when you want provider choice, model, input,
and output paths to live in project-owned YAML:

```bash
open-data-products config generation --copy-to my-generation.config.yaml
```

Check the copied config:

```bash
open-data-products config generation \
  --config my-generation.config.yaml \
  --check
```

Run generation with the copied config:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --provider zai \
  --kind signal \
  --json
```

## 4. Override The Model

The bundled default is `glm-5.2`. To use another GLM model available to your
Z.ai account, override the model for one run:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --provider zai \
  --model <glm-model-id> \
  --kind signal \
  --json
```

Check Z.ai's current model catalog before relying on a model ID in production.

## Troubleshooting

- `ZAI_API_KEY` must be set in the shell that runs the SDK command.
- The provider `type` must stay `openai-chat`; `zai` uses Chat Completions, not
  the SDK's Responses API request path.
- Use the general endpoint `https://api.z.ai/api/paas/v4` for the bundled
  preset. Use a copied config entry if you intentionally test another endpoint.
- Run the config check before generation when editing a project-owned config:

  ```bash
  open-data-products config generation \
    --config my-generation.config.yaml \
    --check
  ```
