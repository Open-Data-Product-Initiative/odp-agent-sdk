"""Add verbatim source context to SDK-generated banking PoC descriptions."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def section(text, name):
    """Read the first paragraph of a named Markdown section."""
    return text.split("## " + name + "\n", 1)[1].split("\n\n", 1)[0].strip()


def main():
    """Add business need and purpose from the original brief to each draft."""
    for source in sorted((ROOT / "sources").glob("*.md")):
        text = source.read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---", 2)[1])
        product_id = front["product_id"]
        target = ROOT / "products" / ("odps_product_" + product_id + ".yaml")
        document = yaml.safe_load(target.read_text(encoding="utf-8"))
        details = document["product"]["details"]["en"]
        if (
            details["productID"] != product_id
            or details["name"] != front["product_name"]
        ):
            raise ValueError("Generated identity differs from " + source.name)
        details["description"] = "\n\n".join(
            [
                section(text, "Overview"),
                "Fictional proposed proof of concept; not a production contract.",
                section(text, "Business need"),
                section(text, "Product purpose"),
            ]
        )
        target.write_text(
            yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
