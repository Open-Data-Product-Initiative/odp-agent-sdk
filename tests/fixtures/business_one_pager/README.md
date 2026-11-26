# Business one-pager comparison fixtures

`small.md` and `rich.md` preserve the two supplied Product Holdings briefs.
`product.odps.yaml` is a neutral shared ODPS draft so the comparison tests do
not add requirements from a different brief.

`tests/test_business_one_pager_handoff.py` uses the same synthetic catalog
context and mocked provider for both inputs. It checks evidence preservation and
package separation; it does not measure the quality of a real model response.
