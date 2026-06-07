# Portfolio Source Pack

This folder is a small from-scratch input set for testing the portfolio
workflow with an online LLM provider such as Claude.

Run from the repository root:

```bash
export ANTHROPIC_API_KEY="..."

open-data-products portfolio build \
  --objectives examples/portfolio/sources/objectives/ \
  --use-cases examples/portfolio/sources/use-cases/ \
  --signals examples/portfolio/sources/signals/ \
  --products examples/portfolio/sources/products/ \
  --title "Customer Intelligence Portfolio" \
  --output examples/portfolio/workspace/ \
  --provider claude \
  --model claude-sonnet-4-5 \
  --json
```

Then open `examples/portfolio/workspace/index.html` in a browser.
