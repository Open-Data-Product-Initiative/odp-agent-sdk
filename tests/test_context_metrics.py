from open_data_products._context_metrics import (
    count_tokens,
    measure_context_formats,
)


def test_count_tokens_uses_injected_tokenizer():
    def tokenizer(text: str) -> int:
        return len(text.split("|"))

    assert count_tokens("a|b|c", tokenizer=tokenizer) == 3


def test_measure_context_formats_compares_bytes_and_tokens():
    def tokenizer(text: str) -> int:
        return len(text.split())

    metrics = measure_context_formats(
        "ODPG sample",
        {
            "yaml": "from customer to product dependsOn high",
            "toon": "customer product dependsOn high",
            "gcf": "@0<@1 dependsOn high",
        },
        tokenizer=tokenizer,
    )

    assert metrics.label == "ODPG sample"
    assert [item.format for item in metrics.formats] == ["yaml", "toon", "gcf"]
    assert metrics.formats[0].tokens == 6
    assert metrics.formats[1].tokens == 4
    assert metrics.formats[2].tokens == 3
    assert metrics.formats[1].token_reduction_vs_baseline == 33.3
    assert metrics.formats[2].token_reduction_vs_baseline == 50.0
