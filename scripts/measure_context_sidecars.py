#!/usr/bin/env python3
"""Measure YAML, TOON, and GCF context sidecars with a model tokenizer."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Callable, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from open_data_products._context_metrics import (  # noqa: E402
    ContextMeasurement,
    measure_context_formats,
)
from open_data_products.odpc import (  # noqa: E402
    build_catalog,
    render_catalog_gcf,
    render_catalog_toon,
    write_catalog,
)
from open_data_products.odpg import (  # noqa: E402
    build_graph,
    render_graph_gcf,
    render_graph_toon,
    write_graph,
)

TokenCounter = Callable[[str], int]


def main() -> int:
    """Run tokenizer-based sidecar measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--encoding",
        default="o200k_base",
        help="tiktoken encoding name to use. Defaults to o200k_base.",
    )
    args = parser.parse_args()
    try:
        tokenizer = _tiktoken_counter(args.encoding)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(render_measurement_table(build_measurements(tokenizer)))
    return 0


def build_measurements(tokenizer: TokenCounter) -> List[ContextMeasurement]:
    """Build repository fixture measurements."""
    measurements: List[ContextMeasurement] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp = Path(temp_dir)
        for label, folder in [
            ("ODPC tiny example fragments", ROOT / "examples/odpc_catalog_fragments"),
            (
                "ODPC guide catalog fragments",
                ROOT / "examples/guides/15-working-with-odpc-catalogs/fragments",
            ),
            (
                "ODPC portfolio workspace catalog",
                ROOT / "examples/portfolio/workspace/odpc/fragments",
            ),
        ]:
            document = build_catalog(folder)
            output = tmp / f"{label.replace(' ', '_')}.yaml"
            write_catalog(output, document)
            measurements.append(
                measure_context_formats(
                    label,
                    {
                        "yaml": output.read_text(encoding="utf-8"),
                        "toon": render_catalog_toon(document),
                        "gcf": render_catalog_gcf(document),
                    },
                    tokenizer=tokenizer,
                )
            )

        guide_graph = build_graph(
            ROOT / "examples/guides/14-working-with-odpg-graphs/fragments",
            graph_id="customer-retention-graph",
            name="Customer Retention Graph",
            client=_deterministic_graph_client,
            model="deterministic-test-client",
        )
        guide_output = tmp / "guide_graph.yaml"
        write_graph(guide_output, guide_graph)
        measurements.append(
            measure_context_formats(
                "ODPG guide graph with deterministic test edges",
                {
                    "yaml": guide_output.read_text(encoding="utf-8"),
                    "toon": render_graph_toon(guide_graph),
                    "gcf": render_graph_gcf(guide_graph),
                },
                tokenizer=tokenizer,
            )
        )

    portfolio_graph_path = ROOT / "examples/portfolio/workspace/odpg/graph.yaml"
    portfolio_graph_text = portfolio_graph_path.read_text(encoding="utf-8")
    portfolio_graph = yaml.safe_load(portfolio_graph_text)
    measurements.append(
        measure_context_formats(
            "ODPG portfolio workspace graph",
            {
                "yaml": portfolio_graph_text,
                "toon": render_graph_toon(portfolio_graph),
                "gcf": render_graph_gcf(portfolio_graph),
            },
            tokenizer=tokenizer,
        )
    )
    return measurements


def render_measurement_table(measurements: List[ContextMeasurement]) -> str:
    """Render measurements as a Markdown table."""
    lines = [
        "| Measurement | YAML bytes | YAML tokens | TOON bytes | TOON tokens | "
        "TOON token reduction | GCF bytes | GCF tokens | GCF token reduction |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for measurement in measurements:
        by_format = {item.format: item for item in measurement.formats}
        yaml_metric = by_format["yaml"]
        toon_metric = by_format.get("toon")
        gcf_metric = by_format.get("gcf")
        lines.append(
            "| "
            + " | ".join(
                [
                    measurement.label,
                    _number(yaml_metric.bytes),
                    _number(yaml_metric.tokens),
                    _number(toon_metric.bytes) if toon_metric else "-",
                    _number(toon_metric.tokens) if toon_metric else "-",
                    (
                        _percent(toon_metric.token_reduction_vs_baseline)
                        if toon_metric
                        else "-"
                    ),
                    _number(gcf_metric.bytes) if gcf_metric else "-",
                    _number(gcf_metric.tokens) if gcf_metric else "-",
                    (
                        _percent(gcf_metric.token_reduction_vs_baseline)
                        if gcf_metric
                        else "-"
                    ),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _deterministic_graph_client(prompt: str, model: str) -> str:
    return """
edges:
  - from: UC-RETENTION-RISK-WORKFLOW
    to: PR-CUSTOMER-HEALTH-SIGNALS
    type: dependsOn
    confidence: high
  - from: UC-RETENTION-RISK-WORKFLOW
    to: OBJ-REDUCE-CHURN
    type: supports
    confidence: high
  - from: SIG-CHURN-DEMAND
    to: UC-RETENTION-RISK-WORKFLOW
    type: informs
    confidence: medium
"""


def _tiktoken_counter(encoding_name: str) -> TokenCounter:
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError(
            "Tokenizer measurement requires optional package tiktoken. "
            "Install it with: python3 -m pip install '.[measurements]'"
        ) from exc
    encoding = tiktoken.get_encoding(encoding_name)
    return lambda text: len(encoding.encode(text))


def _number(value: int) -> str:
    return f"{value:,}"


def _percent(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
