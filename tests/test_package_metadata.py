from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_certifi_requirement_requires_the_emsign_remediation() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert '"certifi>=2026.10.19",' in pyproject
    assert "certifi>=2026.10.19" in requirements.splitlines()
