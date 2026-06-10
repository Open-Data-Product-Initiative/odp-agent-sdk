# Lecture 10: Working with Local LLMs

Local LLMs are useful for cost control, development, testing, privacy, data
sovereignty, and restricted environments. This lesson uses Ollama and a local
config file to generate one ODPC signal fragment.

## 1. Prepare Ollama

```bash
ollama pull qwen2.5
ollama list
```

Keep Ollama running locally.

## 2. Create a lesson folder

```bash
mkdir -p odps-sdk-guides/10-local-llm/source_docs
mkdir -p odps-sdk-guides/10-local-llm/fragments
cd odps-sdk-guides/10-local-llm
```

## 3. Create A Local Generation Config

```bash
cat > generation.config.yaml <<'YAML'
provider: ollama
model: qwen2.5
input: source_docs/
output: fragments/

providers:
  ollama:
    type: ollama
    model: qwen2.5
    baseUrl: http://localhost:11434
YAML
```

The top-level `provider`, `model`, `input`, and `output` values are defaults
for generation commands that use this config.

## 4. Add One Source File

```bash
cat > source_docs/turnaround-delay-signal.txt <<'TXT'
Airport operations teams need an early signal when aircraft turnaround is at
risk of exceeding the planned ground time. The signal should consider late
inbound arrival, missing cleaning crew assignment, delayed baggage unloading,
and gate conflict status. The signal is used by the operations control center
to trigger recovery actions before departure delay becomes unavoidable.
TXT
```

## 5. Generate One Signal Fragment

```bash
open-data-products generate \
  --config generation.config.yaml \
  --input source_docs/turnaround-delay-signal.txt \
  --kind signal
```

The command prints a short human-readable generation summary. Add `--json`
when you want machine-readable output for automation.

## 6. Inspect The Result

```bash
ls fragments/
```

You should see a generated file with a name similar to:

```text
signal_<generated-id>.yaml
```

## What You Learned

- `--kind signal` selects the signal prompt.
- The source file can be plain `.txt`.
- The output is a separate ODPC fragment YAML file.
- Local defaults can live in `generation.config.yaml`.

## Next Lesson

Continue to
[Lecture 11: Working with online LLM providers](../11-working-with-online-llm-providers/).
