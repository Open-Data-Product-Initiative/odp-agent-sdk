from pathlib import Path

from open_data_products._context_artifacts import select_context_artifact


def test_select_context_artifact_prefers_gcf_then_toon_then_yaml(tmp_path: Path):
    graph = tmp_path / "graph.yaml"
    graph.write_text("yaml-context", encoding="utf-8")
    graph.with_suffix(".toon").write_text("toon-context", encoding="utf-8")
    graph.with_suffix(".gcf").write_text("gcf-context", encoding="utf-8")

    artifact = select_context_artifact(graph)

    assert artifact.format == "gcf"
    assert artifact.path == graph.with_suffix(".gcf")
    assert artifact.content == "gcf-context"


def test_select_context_artifact_falls_back_to_yaml(tmp_path: Path):
    graph = tmp_path / "graph.yaml"
    graph.write_text("yaml-context", encoding="utf-8")

    artifact = select_context_artifact(graph)

    assert artifact.format == "yaml"
    assert artifact.path == graph
    assert artifact.content == "yaml-context"


def test_select_context_artifact_respects_requested_format(tmp_path: Path):
    graph = tmp_path / "graph.yaml"
    graph.write_text("yaml-context", encoding="utf-8")
    graph.with_suffix(".toon").write_text("toon-context", encoding="utf-8")
    graph.with_suffix(".gcf").write_text("gcf-context", encoding="utf-8")

    artifact = select_context_artifact(graph, preferred=("toon", "yaml"))

    assert artifact.format == "toon"
    assert artifact.path == graph.with_suffix(".toon")
    assert artifact.content == "toon-context"
