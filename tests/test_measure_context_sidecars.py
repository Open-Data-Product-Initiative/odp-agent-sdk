import importlib.util
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "measure_context_sidecars.py"
)


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "measure_context_sidecars", SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_markdown_table_includes_token_reductions():
    module = _load_script_module()

    def tokenizer(text: str) -> int:
        return len(text.split())

    table = module.render_measurement_table(
        [
            module.measure_context_formats(
                "ODPG sample",
                {
                    "yaml": "from customer to product dependsOn high",
                    "toon": "customer product dependsOn high",
                    "gcf": "@0<@1 dependsOn high",
                },
                tokenizer=tokenizer,
            )
        ]
    )

    assert "| ODPG sample | 39 | 6 | 31 | 4 | 33.3% | 20 | 3 | 50.0% |" in table
