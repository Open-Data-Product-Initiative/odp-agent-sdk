# Guide 4: Convert GraphML to ODPG and Open an Explorer

This guide converts a small external GraphML graph into ODPG YAML, validates
the result, and creates a standalone HTML graph explorer.

## 1. Create a lesson folder

```bash
mkdir -p odp-course/04-graph
cd odp-course/04-graph
```

## 2. Create `graph.graphml`

```bash
cat > graph.graphml <<'XML'
<graphml>
  <key id="nodeType" for="node" attr.name="type"/>
  <key id="edgeType" for="edge" attr.name="type"/>
  <graph edgedefault="directed">
    <node id="airport-operations">
      <data key="nodeType">DataProduct</data>
    </node>
    <node id="delay-risk-monitoring">
      <data key="nodeType">UseCase</data>
    </node>
    <edge source="delay-risk-monitoring" target="airport-operations">
      <data key="edgeType">uses</data>
    </edge>
  </graph>
</graphml>
XML
```

## 3. Convert GraphML to ODPG YAML

```bash
open-data-products odpg-convert \
  --input graph.graphml \
  --output graph.yaml \
  --json
```

## 4. Validate the converted graph

```bash
open-data-products validate graph.yaml --json
```

## 5. Generate a graph explorer

```bash
open-data-products odpg-generate graph.yaml --output graph-explorer.html --json
```

Open `graph-explorer.html` in a browser.

## What You Learned

- `odpg-convert` turns external graph formats into ODPG YAML.
- The converted graph can be validated like any other ODPG document.
- The same graph can be rendered as a standalone HTML explorer.
