# Lecture 18: Build the First Portfolio in Colab

This is the main hands-on portfolio lesson. It loads source material, runs the
portfolio builder, inspects generated folders, opens HTML output, and reviews
catalog and graph files.

## 1. Prepare Colab

In a new Colab notebook, install the SDK:

```python
!python -m pip install --upgrade open-data-products
```

If you use Claude, store the API key in the notebook environment:

```python
import os
os.environ["ANTHROPIC_API_KEY"] = "your-api-key"
```

Do not commit or share notebooks that contain real API keys.

## 2. Create Source Lanes

Create source folders in the notebook runtime:

```python
!mkdir -p source_docs/objectives source_docs/use-cases source_docs/signals source_docs/products
```

Add one source file to each lane:

```bash
cat > source_docs/objectives/reduce-churn-objective.md <<'MD'
# Reduce Preventable Churn

Customer success leaders want to reduce preventable churn by identifying
accounts with declining product usage, unresolved support friction, and renewal
risk before the next business review.
MD

cat > source_docs/use-cases/retention-risk-workflow.md <<'MD'
# Retention Risk Workflow

Customer success managers need a weekly workflow that ranks accounts by churn
risk, explains the main risk drivers, and suggests which accounts should be
contacted before renewal.
MD

cat > source_docs/signals/churn-risk-signal.txt <<'TXT'
Daily customer health note from April 18, 2026 at 09:30.

Product usage is down for several priority accounts, unresolved support tickets
are increasing, and renewal conversations have slowed. The signal should help
retention teams detect preventable churn earlier.
TXT

cat > source_docs/products/customer-health-product.md <<'MD'
# Customer Health Signals Product

The product combines customer profile, subscription status, product usage,
support ticket volume, renewal date, campaign engagement, and churn-risk
signals. It is used by customer success and lifecycle marketing teams for
retention planning.
MD
```

These four files match the input map from Lecture 17: objectives, use cases,
signals, and products.

## 3. Run Portfolio Build

```python
!open-data-products portfolio build \
  --objectives source_docs/objectives/ \
  --use-cases source_docs/use-cases/ \
  --signals source_docs/signals/ \
  --products source_docs/products/ \
  --title "Customer Intelligence Portfolio" \
  --output portfolio/ \
  --provider claude \
  --model claude-sonnet-4-5
```

## 4. Inspect Generated Folders

```python
!find portfolio -maxdepth 3 -type f | sort
```

Look for:

- `portfolio/index.html`
- `portfolio/portfolio.yaml`
- `portfolio/odpc/catalog.yaml`
- `portfolio/odpc/fragments/`
- `portfolio/odpg/graph.yaml`
- `portfolio/odps/products/`

## 5. Open The HTML Output

Download `portfolio/index.html` from Colab and open it in a browser. The page
contains tabs for overview, artifact types, products, graph, and about content.

## 6. Review Catalog And Graph Files

```python
!open-data-products portfolio explain portfolio/
!open-data-products validate portfolio/odpc/catalog.yaml
!open-data-products validate portfolio/odpg/graph.yaml
```

## What You Learned

- Portfolio build combines source lanes into one workspace.
- The workspace includes ODPC, ODPS, ODPG, HTML, and report artifacts.
- The browser view is for review, while YAML files remain agent-ready.

## Next Lesson

Continue to
[Lecture 19: Update the portfolio and review version history](../19-update-portfolio-and-review-version-history/).
