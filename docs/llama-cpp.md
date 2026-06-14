# Embedded llama.cpp Generation

This guide shows how to use the SDK with embedded llama.cpp support. This mode
loads a local GGUF model file directly in Python through `llama-cpp-python`.
It does not require Ollama, LM Studio, vLLM, or a llama.cpp server.

Use this mode when you want local generation without running a separate local
LLM service.

## 1. Install The Optional Extra

Create and activate a project virtual environment first:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

On Windows PowerShell, activate the environment with:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
```

Then install the SDK with embedded llama.cpp support inside the active virtual
environment:

```bash
python -m pip install "open-data-products[llama-cpp]"
```

Check that both packages import:

```bash
python - <<'PY'
import open_data_products
import llama_cpp

print("open-data-products import ok")
print("llama_cpp import ok")
PY
```

On some platforms or newer Python versions, `llama-cpp-python` may compile
during installation. If installation fails because build tools are missing,
install the platform build tools first, reactivate the same virtual
environment, then run the same `python -m pip install` command again.

## 2. Get A GGUF Model File

Download or prepare a GGUF model file that fits your machine. For example:

```text
models/qwen2.5-7b-instruct-q4_k_m.gguf
```

The SDK does not download model files. Keep the model file in a project-owned
folder such as `models/`, and make sure the path you put in the config points
to the real file.

## 3. Copy The Generation Config

Create a project-owned generation config:

```bash
open-data-products config generation --copy-to my-generation.config.yaml
```

Open `my-generation.config.yaml` and find the `llamacpp-embedded` provider.
Change `modelPath` to your local GGUF file:

```yaml
providers:
  llamacpp-embedded:
    type: llama-cpp
    model: local-gguf
    modelPath: models/qwen2.5-7b-instruct-q4_k_m.gguf
    contextWindow: 8192
    gpuLayers: -1
```

Use these fields:

- `type: llama-cpp` tells the SDK to use embedded llama.cpp.
- `model` is a label kept for SDK provider consistency.
- `modelPath` must point to the local `.gguf` model file.
- `contextWindow` controls the llama.cpp context size.
- `gpuLayers` controls GPU offload. Use `0` for CPU-only. Use `-1` to let
  llama.cpp offload all possible layers when supported.

## 4. Validate The Config

Run the config check before generation:

```bash
open-data-products config generation \
  --config my-generation.config.yaml \
  --check
```

For machine-readable output:

```bash
open-data-products config generation \
  --config my-generation.config.yaml \
  --check \
  --json
```

The check validates the provider shape and confirms that `modelPath`,
`contextWindow`, and `gpuLayers` are valid config fields. It does not load the
model file or run inference.

## 5. Run A Small Generation Test

Create a small input folder:

```bash
mkdir -p source_docs/signals generated
cat > source_docs/signals/turnaround-delay-signal.txt <<'EOF'
Airport operations team needs an operational signal for turnaround delay risk.
The signal should help detect when aircraft turnaround is likely to exceed the
planned gate departure time.
EOF
```

Run generation with the embedded llama.cpp provider:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --provider llamacpp-embedded \
  --input source_docs/signals/ \
  --kind signal \
  --output generated/ \
  --json
```

Then validate the generated YAML:

```bash
open-data-products validate generated/*.yaml
```

## 6. Server Mode Versus Embedded Mode

Use embedded mode when the SDK should load the GGUF file directly:

```yaml
providers:
  llamacpp-embedded:
    type: llama-cpp
    modelPath: models/qwen2.5-7b-instruct-q4_k_m.gguf
```

Use server mode when llama.cpp is already running as an OpenAI-compatible
server:

```yaml
providers:
  llamacpp-server:
    type: openai-chat
    model: local-model
    baseUrl: http://127.0.0.1:8080/v1
```

Server mode requires the server process to be running. Embedded mode does not.

## Troubleshooting

If install fails while building `llama-cpp-python`, install local build tools
for your platform, reactivate the virtual environment, and rerun:

```bash
source .venv/bin/activate
python -m pip install "open-data-products[llama-cpp]"
```

If generation says `modelPath is required for llama-cpp generation`, check that
the selected provider has `type: llama-cpp` and a non-empty `modelPath`.

If generation fails when loading the model, check that:

- the `.gguf` file exists at `modelPath`;
- the model fits available memory;
- `contextWindow` is not too large for the model and machine;
- `gpuLayers` is compatible with the local llama.cpp build.

If output YAML is invalid, try a stronger model, lower the input size, or
validate and repair the generated file before using it downstream.
