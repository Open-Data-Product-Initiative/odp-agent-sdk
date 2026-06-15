# NVIDIA NIM Generation

This guide shows how to use the SDK with a locally running NVIDIA NIM LLM
container. The SDK talks to NIM through its OpenAI-compatible Chat Completions
endpoint at `http://localhost:8000/v1/chat/completions`.

Use this mode when you want generation backed by a NIM container that you run
and manage outside the SDK.

## Why NVIDIA NIM

NVIDIA NIM is broader than a generic LLM endpoint. The NVIDIA catalog includes
language models, vision models, embedding and retrieval models, speech models,
safety models, and domain-specialist models for scientific and technical
workflows such as biology and chemistry.

For SDK generation, the relevant NIM capability is the OpenAI-compatible chat
endpoint exposed by a running LLM container. That lets the SDK use models such
as Llama, Nemotron, Mistral, Qwen, and other NIM-served language models through
the same `openai-chat` request path used for local OpenAI-compatible runtimes.

NIM is useful when you want:

- local inference on your own NVIDIA GPU machine or server;
- NVIDIA-optimized model serving through a production-oriented container;
- access to NVIDIA's Nemotron model family;
- a path to domain-specific NVIDIA model families beyond general chat models;
- an OpenAI-compatible API surface for SDK generation.

Keep the deployment boundary clear. The `nvidia-nim` SDK preset targets a local
NIM LLM container at `http://localhost:8000/v1`. Hosted NVIDIA endpoints and
catalog free-tier endpoints are separate services with their own base URLs,
authentication, model availability, and rate limits.

## 1. Prepare NVIDIA NIM

Install the NVIDIA container runtime, Docker, and a supported NVIDIA GPU driver
first. NVIDIA publishes the current prerequisites, image tags, and support
matrix in the NIM LLM documentation:

- [NIM prerequisites](https://docs.nvidia.com/nim/large-language-models/latest/get-started/prerequisites.html)
- [NIM installation](https://docs.nvidia.com/nim/large-language-models/latest/get-started/installation.html)
- [NIM quickstart](https://docs.nvidia.com/nim/large-language-models/latest/get-started/quickstart.html)

Create an NVIDIA NGC API key, accept the governing terms for the selected NIM
container in the NVIDIA catalog, and log in to the NVIDIA container registry:

```bash
export NGC_API_KEY="..."
echo "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin
```

## 2. Start A NIM Container

Pull the NIM image for the model you want to serve. This example uses the image
tag shown in NVIDIA's NIM documentation for Llama 3.1 8B Instruct:

```bash
docker pull nvcr.io/nim/meta/llama-3.1-8b-instruct:2.0.6
```

Create a local cache so model files are not downloaded again on every restart:

```bash
export LOCAL_NIM_CACHE="$HOME/.cache/nim"
mkdir -p "$LOCAL_NIM_CACHE"
```

Run the container on port `8000`:

```bash
docker run --gpus=all \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/meta/llama-3.1-8b-instruct:2.0.6
```

The SDK does not start, stop, pull, or configure NIM containers. Keep this
container running while SDK generation commands execute.

## 3. Tune NIM Startup

NIM startup settings control how the container uses GPUs and backend runtime
features. Configure them when starting the container, not in
`my-generation.config.yaml`. The SDK generation config only tells the SDK which
running endpoint and model ID to call.

Use `NIM_MODEL_PROFILE` when you want NIM to select a known profile:

```bash
docker run --gpus=all \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -e NIM_MODEL_PROFILE=vllm-bf16-tp2-pp1 \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/meta/llama-3.1-8b-instruct:2.0.6
```

Use NIM environment variables for common backend settings:

```bash
docker run --gpus=all \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -e NIM_TENSOR_PARALLEL_SIZE=2 \
  -e NIM_PIPELINE_PARALLEL_SIZE=1 \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/meta/llama-3.1-8b-instruct:2.0.6
```

Use backend CLI arguments when you need direct control over the NIM backend.
For vLLM-backed NIM images, common examples include:

```bash
docker run --gpus=all \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/meta/llama-3.1-8b-instruct:2.0.6 \
  nim-serve --tensor-parallel-size 2 --pipeline-parallel-size 1
```

Use `NIM_PASSTHROUGH_ARGS` when direct backend CLI arguments are inconvenient,
for example in container orchestration:

```bash
docker run --gpus=all \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -e NIM_PASSTHROUGH_ARGS="--tensor-parallel-size 2 --enable-lora" \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/meta/llama-3.1-8b-instruct:2.0.6
```

These startup settings are applied before the SDK connects:

- `--tensor-parallel-size` controls how many GPUs split tensor parallel work.
- `--pipeline-parallel-size` controls pipeline-parallel stages.
- `--enable-lora` enables LoRA adapter support when the selected backend and
  model profile support it.
- `NIM_MODEL_PROFILE` selects a NIM model profile such as
  `vllm-bf16-tp2-pp1`.
- `NIM_PASSTHROUGH_ARGS` passes backend-specific CLI flags through an
  environment variable.

Restart the NIM container after changing any startup setting. Then rerun the
health and model discovery checks before calling the SDK.

## 4. Verify The NIM Endpoint

Check that the container is live:

```bash
curl http://localhost:8000/v1/health/live
```

Check that the model is loaded and ready:

```bash
curl http://localhost:8000/v1/health/ready
```

Get the served model name:

```bash
curl -s http://localhost:8000/v1/models
```

Use the returned model `id` in SDK commands. For model-specific NIM containers,
the model name is often a value such as `meta/llama-3.1-8b-instruct`.

## 5. Run SDK Generation

The bundled SDK provider preset is `nvidia-nim`. It uses:

```yaml
providers:
  nvidia-nim:
    type: openai-chat
    model: local-model
    baseUrl: http://localhost:8000/v1
```

Run generation and override the model with the value returned by
`/v1/models`:

```bash
open-data-products generate \
  --provider nvidia-nim \
  --model meta/llama-3.1-8b-instruct \
  --input source_docs/products/ \
  --kind product-reference \
  --output generated/ \
  --json
```

For a smaller test, generate one signal fragment:

```bash
mkdir -p source_docs/signals generated
cat > source_docs/signals/turnaround-delay-signal.txt <<'EOF'
Airport operations team needs an operational signal for turnaround delay risk.
The signal should help detect when aircraft turnaround is likely to exceed the
planned gate departure time.
EOF

open-data-products generate \
  --provider nvidia-nim \
  --model meta/llama-3.1-8b-instruct \
  --input source_docs/signals/ \
  --kind signal \
  --output generated/ \
  --json
```

Then validate the generated YAML:

```bash
open-data-products validate generated/*.yaml
```

## 6. Use A Project Config

Copy the bundled generation config when you want the provider choice to live in
a project-owned YAML file:

```bash
open-data-products config generation --copy-to my-generation.config.yaml
```

Edit the `nvidia-nim` provider if your NIM endpoint or model name differs:

```yaml
providers:
  nvidia-nim:
    type: openai-chat
    model: meta/llama-3.1-8b-instruct
    baseUrl: http://localhost:8000/v1
```

Validate the config shape:

```bash
open-data-products config generation \
  --config my-generation.config.yaml \
  --check
```

Run generation with the copied config:

```bash
open-data-products generate \
  --config my-generation.config.yaml \
  --provider nvidia-nim \
  --input source_docs/signals/ \
  --kind signal \
  --output generated/ \
  --json
```


## Troubleshooting

If Docker cannot see the GPU, verify the NVIDIA driver, NVIDIA container
runtime, and Docker GPU setup before changing SDK settings.

If `curl http://localhost:8000/v1/health/ready` is not ready, wait for the model
to finish loading or check the container logs.

If SDK generation fails with a connection error, confirm the NIM container is
still running and that port `8000` is mapped to the host.

If NIM returns a model error, rerun:

```bash
curl -s http://localhost:8000/v1/models
```

Then pass the returned model `id` with `--model`, or update the `model` value in
`my-generation.config.yaml`.

If output YAML is invalid, try a stronger NIM model, reduce the input size, or
validate and repair the generated file before using it downstream.
