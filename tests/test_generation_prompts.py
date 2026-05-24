"""Tests for local generation prompt assets and helpers."""

from pathlib import Path

import yaml

from open_data_products.generation import (
    ensure_ollama_model,
    generate_local_artifact,
    generate_local_artifacts,
    list_generation_prompts,
    load_generation_prompt,
    list_ollama_models,
    render_generation_prompt,
)
from open_data_products import (
    ensure_ollama_model as ensure_public_ollama_model,
    generate_local_artifact as generate_public_local_artifact,
    generate_local_artifacts as generate_public_local_artifacts,
    list_generation_prompts as list_public_generation_prompts,
    load_generation_prompt as load_public_generation_prompt,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATION_SOURCE_DOCS = (
    REPO_ROOT
    / "open_data_products"
    / "generation"
    / "source_docs"
)


def test_generation_prompts_are_listed_and_loadable():
    """Test that editable local generation prompts are bundled."""
    prompt_names = list_generation_prompts()

    assert prompt_names == [
        "odpc_objective_fragment.md",
        "odpc_signal_fragment.md",
        "odpc_use_case_fragment.md",
        "odpg_graph_yaml.md",
        "odps_data_product_fragment.md",
        "system.md",
    ]
    for name in prompt_names:
        prompt = load_generation_prompt(name)
        assert "{source_documents}" in prompt
        assert "valid YAML" in prompt
    assert "top-level `productReferences` list" in load_generation_prompt(
        "odps_data_product_fragment.md"
    )
    assert "Do not start the YAML with `- productReferences:`" in load_generation_prompt(
        "odps_data_product_fragment.md"
    )
    assert "Never create `productReferences` for use cases" in load_generation_prompt(
        "odps_data_product_fragment.md"
    )
    assert "dataNeeds:" in load_generation_prompt("odpc_use_case_fragment.md")
    assert "summary:" in load_generation_prompt("odpc_use_case_fragment.md")
    assert "startDate:" in load_generation_prompt("odpc_objective_fragment.md")
    assert "Do not use `linkedUseCases`" in load_generation_prompt(
        "odpc_objective_fragment.md"
    )
    assert "The `id` must describe the same signal as `name.en`" in load_generation_prompt(
        "odpc_signal_fragment.md"
    )
    assert "Do not use `moderate`" in load_generation_prompt("odpc_signal_fragment.md")
    assert "`from`, `to`, `type`, and `confidence`" in load_generation_prompt(
        "odpg_graph_yaml.md"
    )
    assert "product_reference_<id>.yaml" in load_generation_prompt(
        "odpg_graph_yaml.md"
    )
    assert "every edge `from` and `to` value appears in `graph.nodes`" in load_generation_prompt(
        "odpg_graph_yaml.md"
    )
    assert "Do not use YAML document separators" in load_generation_prompt(
        "odpc_signal_fragment.md"
    )


def test_generation_prompt_rejects_unknown_name():
    """Test that prompt lookup fails clearly for unknown prompt names."""
    try:
        load_generation_prompt("missing.md")
    except KeyError as exc:
        assert "Unknown generation prompt" in str(exc)
    else:
        raise AssertionError("unknown prompt name did not raise KeyError")


def test_generation_prompt_helpers_are_public_api():
    """Test that prompt helpers are available from the package root."""
    assert "system.md" in list_public_generation_prompts()
    assert load_public_generation_prompt("system.md").startswith(
        "# Local ODP Generation System Prompt"
    )
    assert ensure_public_ollama_model is ensure_ollama_model
    assert generate_public_local_artifact is generate_local_artifact
    assert generate_public_local_artifacts is generate_local_artifacts


def test_render_generation_prompt_inlines_source_documents():
    """Test that generation prompts are rendered with source document text."""
    prompt = render_generation_prompt("odpc_signal_fragment.md", GENERATION_SOURCE_DOCS)

    assert "{source_documents}" not in prompt
    assert "Source file: turnaround-delay-signal.txt" in prompt
    assert "Turnaround Delay Spike Signal" in prompt


def test_render_generation_prompt_accepts_one_source_file():
    """Test that one source file can drive single-artifact generation."""
    source_file = GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt"

    prompt = render_generation_prompt("odpc_signal_fragment.md", source_file)

    assert "Source file: turnaround-delay-signal.txt" in prompt
    assert "Turnaround Delay Spike Signal" in prompt
    assert "Passenger Flow and Queue Data Product" not in prompt


def test_list_ollama_models_reads_local_tags(monkeypatch):
    """Test that Ollama model discovery reads /api/tags."""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"models":[{"name":"qwen2.5:latest"},{"model":"llama3.2"}]}'

    def fake_urlopen(req, timeout):
        assert req.full_url == "http://localhost:11434/api/tags"
        assert timeout == 10
        return FakeResponse()

    monkeypatch.setattr("open_data_products.generation.request.urlopen", fake_urlopen)

    assert list_ollama_models() == ["qwen2.5:latest", "llama3.2"]


def test_ensure_ollama_model_accepts_qwen_latest(monkeypatch):
    """Test that qwen2.5 is accepted when Ollama has qwen2.5:latest."""
    monkeypatch.setattr(
        "open_data_products.generation.list_ollama_models",
        lambda base_url="http://localhost:11434": ["qwen2.5:latest"],
    )

    ensure_ollama_model("qwen2.5")


def test_ensure_ollama_model_rejects_missing_qwen(monkeypatch):
    """Test that missing qwen2.5 fails before generation."""
    monkeypatch.setattr(
        "open_data_products.generation.list_ollama_models",
        lambda base_url="http://localhost:11434": ["llama3.2:latest"],
    )

    try:
        ensure_ollama_model("qwen2.5")
    except RuntimeError as exc:
        assert "Required Ollama model qwen2.5 is not available" in str(exc)
    else:
        raise AssertionError("missing qwen2.5 did not raise RuntimeError")


def test_generate_local_artifacts_writes_yaml_outputs(tmp_path):
    """Test local generation with a fake model client."""
    prompts_seen = []

    def fake_client(prompt: str, model: str) -> str:
        prompts_seen.append((prompt, model))
        if prompt.startswith("# Generate ODPG Graph YAML"):
            return """```yaml
schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: '1.0'
kind: Graph
graph:
  metadata:
    id: GRAPH-AIRPORTS-001
    name:
      en: Airports and Flights Graph
    description:
      en: Airports and flights graph.
  nodes:
    - id: test-signal
      type: StrategicOpportunity
      $ref: odpc_signals.yaml#/signals/0
  edges: []
```"""
        if prompt.startswith("# Generate ODPS"):
            return """productReferences:
- id: test-product
  productID: test-product
  productVersion: "1.0.0"
  name:
    en: Test Product
  description:
    en: Test product.
  productModel:
    standard: ODPS
    version: "4.1"
    format: yaml
    $ref: products/test-product.yaml
"""
        if prompt.startswith("# Generate ODPC Use Case"):
            return "useCases: []\n"
        if prompt.startswith("# Generate ODPC Business Objective"):
            return "businessObjectives: []\n"
        return """signals:
- id: test-signal
  name:
    en: Test Signal
  description:
    en: Test signal.
  type: operational
  source:
    origin: internal
    method: test
  observedAt: "2026-05-20T00:00:00Z"
"""

    artifacts = generate_local_artifacts(
        GENERATION_SOURCE_DOCS,
        tmp_path,
        model="qwen2.5",
        client=fake_client,
    )

    assert [artifact.name for artifact in artifacts] == [
        "productReference:test-product",
        "signal:test-signal",
        "odpg_graph",
    ]
    assert all(artifact.valid_yaml for artifact in artifacts)
    assert all(model == "qwen2.5" for _, model in prompts_seen)
    assert "{source_documents}" not in prompts_seen[0][0]
    graph_prompt = prompts_seen[-1][0]
    assert "Source file: product_reference_test-product.yaml" in graph_prompt
    assert "Source file: signal_test-signal.yaml" in graph_prompt
    graph = yaml.safe_load((tmp_path / "odpg_graph.yaml").read_text(encoding="utf-8"))
    assert graph["graph"]["nodes"] == [
        {
            "id": "test-signal",
            "type": "Signal",
            "$ref": "signal_test-signal.yaml",
        },
        {
            "id": "test-product",
            "type": "DataProduct",
            "$ref": "product_reference_test-product.yaml",
        },
    ]
    assert yaml.safe_load(
        (tmp_path / "product_reference_test-product.yaml").read_text(encoding="utf-8")
    ) == {
        "productReference": {
            "id": "test-product",
            "productID": "test-product",
            "productVersion": "1.0.0",
            "name": {"en": "Test Product"},
            "description": {"en": "Test product."},
            "productModel": {
                "standard": "ODPS",
                "version": "4.1",
                "format": "yaml",
                "$ref": "products/test-product.yaml",
            },
        }
    }
    assert yaml.safe_load(
        (tmp_path / "signal_test-signal.yaml").read_text(encoding="utf-8")
    ) == {
        "signal": {
            "id": "test-signal",
            "name": {"en": "Test Signal"},
            "description": {"en": "Test signal."},
            "type": "operational",
            "source": {"origin": "internal", "method": "test"},
            "observedAt": "2026-05-20T00:00:00Z",
        }
    }
    assert (tmp_path / "odpg_graph.yaml").is_file()


def test_generate_local_artifact_writes_one_selected_yaml_output(tmp_path):
    """Test generating only one selected artifact kind."""
    prompts_seen = []

    def fake_client(prompt: str, model: str) -> str:
        prompts_seen.append((prompt, model))
        return """signals:
- id: turnaround-delay-spike-signal
  name:
    en: Turnaround Delay Spike Signal
  description:
    en: Turnaround delay increased at Terminal 2.
  type: operational
  source:
    origin: internal
    method: ground operations event log
  observedAt: "2026-05-20T00:00:00Z"
"""

    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
        tmp_path,
        client=fake_client,
    )

    assert artifact.name == "signal:turnaround-delay-spike-signal"
    assert artifact.output_path == tmp_path / "signal_turnaround-delay-spike-signal.yaml"
    assert artifact.valid_yaml is True
    assert "Turnaround Delay Spike Signal" in prompts_seen[0][0]
    assert "Passenger Connection Protection" not in prompts_seen[0][0]
    assert yaml.safe_load(artifact.output_path.read_text(encoding="utf-8")) == {
        "signal": {
            "id": "turnaround-delay-spike-signal",
            "name": {"en": "Turnaround Delay Spike Signal"},
            "description": {"en": "Turnaround delay increased at Terminal 2."},
            "type": "operational",
            "source": {
                "origin": "internal",
                "method": "ground operations event log",
            },
            "observedAt": "2026-05-20T00:00:00Z",
        }
    }


def test_generate_local_artifact_rejects_wrong_fragment_shape(tmp_path):
    """Test that generic YAML is not accepted as a useful fragment."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
        tmp_path,
        client=lambda prompt, model: "items: []",
    )

    assert artifact.valid_yaml is False
    assert "expected root key `signals`" in artifact.errors[0]


def test_generate_local_artifact_rejects_schema_invalid_fragment(tmp_path):
    """Test that ODPC-shaped roots still need schema-valid contents."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "turnaround-delay-signal.txt",
        tmp_path,
        client=lambda prompt, model: """signals:
- id: SIG-001
  name.en: Broken
  description.en: Broken
  type: operational
  source:
    origin: free text is not valid here
    method: test
  observedAt: "2026-05-20T00:00:00Z"
""",
    )

    assert artifact.valid_yaml is False
    assert artifact.errors


def test_generate_local_artifact_normalizes_signal_id_name_mismatch(tmp_path):
    """Test that repairable signal ids are normalized from the signal name."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "security-queue-surge-signal.txt",
        tmp_path,
        client=lambda prompt, model: """signals:
- id: passenger-connection-protection-signal
  name:
    en: Security Queue Surge Signal
  description:
    en: Security queues exceeded the target threshold.
  type: operational
  source:
    origin: internal
    method: passenger flow queue measurements
  observedAt: "2026-05-21T07:10:00Z"
""",
    )

    assert artifact.valid_yaml is True
    assert yaml.safe_load(artifact.output_path.read_text(encoding="utf-8")) == {
        "signal": {
            "id": "security-queue-surge-signal",
            "name": {"en": "Security Queue Surge Signal"},
            "description": {"en": "Security queues exceeded the target threshold."},
            "type": "operational",
            "source": {
                "origin": "internal",
                "method": "passenger flow queue measurements",
            },
            "observedAt": "2026-05-21T07:10:00Z",
        }
    }


def test_generate_local_artifact_normalizes_signal_enum_aliases(tmp_path):
    """Test that common signal enum aliases are normalized before validation."""
    artifact = generate_local_artifact(
        "signal",
        GENERATION_SOURCE_DOCS / "inbound-connection-risk-signal.txt",
        tmp_path,
        client=lambda prompt, model: """signals:
- id: inbound-connection-risk-signal
  name:
    en: Inbound Connection Risk Signal
  description:
    en: Connections are at risk.
  type: operational
  source:
    origin: internal
    method: connection reliability estimates
  observedAt: "2026-05-22T00:00:00Z"
  impact:
    valuePotential: moderate
    urgency: moderate
""",
    )

    assert artifact.valid_yaml is True
    signal = yaml.safe_load(
        artifact.output_path.read_text(encoding="utf-8")
    )["signal"]
    assert signal["impact"]["valuePotential"] == "medium"
    assert signal["impact"]["urgency"] == "medium"


def test_generate_local_artifact_removes_objective_relationship_fields(tmp_path):
    """Test that objective graph relationship fields are removed from fragments."""
    artifact = generate_local_artifact(
        "objective",
        GENERATION_SOURCE_DOCS / "airport-business-objective.txt",
        tmp_path,
        client=lambda prompt, model: """businessObjectives:
- id: reduce-departure-delay-minutes
  name:
    en: Reduce Departure Delay Minutes
  description:
    en: Reduce delay minutes.
  linkedUseCases:
    - flight-delay-risk-monitoring
  dataProducts:
    - airport-operations-performance
""",
    )

    assert artifact.valid_yaml is True
    objective = yaml.safe_load(
        artifact.output_path.read_text(encoding="utf-8")
    )["businessObjective"]
    assert "linkedUseCases" not in objective
    assert "dataProducts" not in objective


def test_generate_local_artifact_rejects_schema_invalid_graph(tmp_path):
    """Test that graph-shaped YAML still needs ODPG graph fields."""
    artifact = generate_local_artifact(
        "graph",
        GENERATION_SOURCE_DOCS,
        tmp_path,
        client=lambda prompt, model: """schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  nodes:
    - id: airport-operations-performance
      label: DataProduct
  edges:
    - source: flight-delay-risk-monitoring
      target: airport-operations-performance
      label: depends_on
""",
    )

    assert artifact.valid_yaml is False
    assert any("graph.metadata" in error for error in artifact.errors)


def test_generate_local_artifacts_repairs_graph_missing_generated_nodes(tmp_path):
    """Test that holistic graph output adds nodes for generated fragment ids."""

    def fake_client(prompt: str, model: str) -> str:
        if prompt.startswith("# Generate ODPG Graph YAML"):
            return """schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata:
    id: airports-graph
    name:
      en: Airports Graph
    description:
      en: Incomplete graph.
  nodes: []
  edges: []
"""
        if prompt.startswith("# Generate ODPS"):
            return """productReferences:
- id: airport-operations-performance
  productID: airport-operations-performance
  productVersion: "1.0.0"
  name:
    en: Airport Operations Performance Data Product
  description:
    en: Airport operations data.
  productModel:
    standard: ODPS
    version: "4.1"
    format: yaml
    $ref: products/airport-operations-performance.yaml
"""
        if prompt.startswith("# Generate ODPC Use Case"):
            return "useCases: []\n"
        if prompt.startswith("# Generate ODPC Business Objective"):
            return "businessObjectives: []\n"
        return "signals: []\n"

    artifacts = generate_local_artifacts(GENERATION_SOURCE_DOCS, tmp_path, client=fake_client)

    graph_artifact = artifacts[-1]
    assert graph_artifact.name == "odpg_graph"
    assert graph_artifact.valid_yaml is True
    graph = yaml.safe_load(graph_artifact.output_path.read_text(encoding="utf-8"))
    assert graph["graph"]["nodes"] == [
        {
            "id": "airport-operations-performance",
            "type": "DataProduct",
            "$ref": "product_reference_airport-operations-performance.yaml",
        }
    ]


def test_generate_local_artifacts_repairs_graph_refs_to_fragment_files(tmp_path):
    """Test that graph nodes use generated fragment file references."""

    def fake_client(prompt: str, model: str) -> str:
        if prompt.startswith("# Generate ODPG Graph YAML"):
            return """schema: https://opendataproducts.org/odpg-v1.0/schema/odpg.yaml
version: "1.0"
kind: Graph
graph:
  metadata:
    id: airports-graph
    name:
      en: Airports Graph
    description:
      en: Graph with stale aggregate refs.
  nodes:
    - id: test-signal
      type: StrategicOpportunity
      $ref: odpc_signals.yaml#/signals/0
  edges: []
"""
        if prompt.startswith("# Generate ODPS"):
            return "productReferences: []\n"
        if prompt.startswith("# Generate ODPC Use Case"):
            return "useCases: []\n"
        if prompt.startswith("# Generate ODPC Business Objective"):
            return "businessObjectives: []\n"
        return """signals:
- id: test-signal
  name:
    en: Test Signal
  description:
    en: Test signal.
  type: operational
  source:
    origin: internal
    method: test
  observedAt: "2026-05-20T00:00:00Z"
"""

    artifacts = generate_local_artifacts(GENERATION_SOURCE_DOCS, tmp_path, client=fake_client)

    graph = yaml.safe_load(artifacts[-1].output_path.read_text(encoding="utf-8"))
    assert graph["graph"]["nodes"] == [
        {
            "id": "test-signal",
            "type": "Signal",
            "$ref": "signal_test-signal.yaml",
        }
    ]


def test_generate_local_artifact_rejects_unknown_kind(tmp_path):
    """Test that unsupported artifact kinds fail clearly."""
    try:
        generate_local_artifact(
            "catalog",
            GENERATION_SOURCE_DOCS,
            tmp_path,
            client=lambda prompt, model: "items: []",
        )
    except KeyError as exc:
        assert "Unknown generation artifact kind" in str(exc)
    else:
        raise AssertionError("unknown artifact kind did not raise KeyError")
