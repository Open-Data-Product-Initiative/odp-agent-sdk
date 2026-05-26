# Guide 5: Generate One Signal Fragment with Ollama

This is the smallest LLM workflow: give the SDK one text file and ask it to
generate one ODPC signal fragment.

## 1. Prepare Ollama

```bash
ollama pull qwen2.5
ollama list
```

Keep Ollama running locally.

## 2. Create a lesson folder

```bash
mkdir -p odp-course/05-llm-signal/source_docs
mkdir -p odp-course/05-llm-signal/fragments
cd odp-course/05-llm-signal
```

## 3. Add one source file

```bash
cat > source_docs/turnaround-delay-signal.txt <<'TXT'
Airport operations teams need an early signal when aircraft turnaround is at
risk of exceeding the planned ground time. The signal should consider late
inbound arrival, missing cleaning crew assignment, delayed baggage unloading,
and gate conflict status. The signal is used by the operations control center
to trigger recovery actions before departure delay becomes unavoidable.
TXT
```

## 4. Generate one signal fragment

```bash
open-data-products generate \
  --input source_docs/turnaround-delay-signal.txt \
  --kind signal \
  --output fragments/ \
  --json
```

## 5. Inspect the result

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
