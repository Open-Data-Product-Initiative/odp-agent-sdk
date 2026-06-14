"""Generation prompt and source-document helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from .._context_artifacts import select_context_artifact
from .models import PathLike

PROMPT_DIR = Path(__file__).resolve().parent / "data" / "prompts"


def list_generation_prompts(prompt_dir: Optional[PathLike] = None) -> List[str]:
    """List bundled local generation prompt filenames."""
    root = Path(prompt_dir) if prompt_dir else PROMPT_DIR
    return sorted(path.name for path in root.glob("*.md"))


def load_generation_prompt(name: str, prompt_dir: Optional[PathLike] = None) -> str:
    """Load a bundled local generation prompt by filename."""
    if "/" in name or "\\" in name:
        raise KeyError(f"Unknown generation prompt: {name}")

    prompt_path = (Path(prompt_dir) if prompt_dir else PROMPT_DIR) / name
    if not prompt_path.is_file():
        raise KeyError(f"Unknown generation prompt: {name}")
    return prompt_path.read_text(encoding="utf-8")


def copy_generation_prompts(
    destination: PathLike,
    *,
    overwrite: bool = False,
) -> List[Path]:
    """Copy bundled generation prompts to a user-editable folder."""
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for prompt_path in sorted(PROMPT_DIR.glob("*.md")):
        output = target / prompt_path.name
        if output.exists() and not overwrite:
            raise FileExistsError(f"Prompt file already exists: {output}")
        shutil.copyfile(prompt_path, output)
        copied.append(output)
    return copied


def load_source_documents(source_dir: PathLike) -> str:
    """Load source documents as one prompt context."""
    paths = source_document_paths(source_dir)

    if not paths:
        raise ValueError(f"No supported source documents found at {source_dir}")

    sections = []
    for path in paths:
        heading, content = source_document_context(path)
        sections.append(
            "\n".join(
                [
                    heading,
                    content,
                ]
            )
        )
    return "\n\n".join(sections)


def source_document_context(path: Path) -> tuple[str, str]:
    """Return prompt heading and content for one source document."""
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            artifact = select_context_artifact(path, preferred=("gcf", "toon"))
        except FileNotFoundError:
            pass
        else:
            return (
                f"--- Source file: {path.name} (context: {artifact.path.name}) ---",
                artifact.content.strip(),
            )
    return f"--- Source file: {path.name} ---", path.read_text(encoding="utf-8").strip()


def source_document_paths(source: PathLike) -> List[Path]:
    """Return supported source files for generation."""
    root = Path(source)
    if root.is_file():
        return [root]
    if root.is_dir():
        return sorted(
            path
            for path in root.iterdir()
            if path.is_file()
            and (path.suffix.lower() in {".md", ".txt"} or has_context_sidecar(path))
        )
    raise FileNotFoundError(f"Source document path not found: {root}")


def has_context_sidecar(path: Path) -> bool:
    """Return whether a YAML source has a compact context sidecar."""
    if path.suffix.lower() not in {".yaml", ".yml"}:
        return False
    return path.with_suffix(".gcf").is_file() or path.with_suffix(".toon").is_file()


def render_generation_prompt(
    prompt_name: str,
    source_dir: PathLike,
    prompt_dir: Optional[PathLike] = None,
) -> str:
    """Render a generation prompt with source documents inlined."""
    return load_generation_prompt(prompt_name, prompt_dir=prompt_dir).replace(
        "{source_documents}",
        load_source_documents(source_dir),
    )
