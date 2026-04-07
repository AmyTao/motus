"""MkDocs hook: auto-generate example documentation pages from examples/ directory.

For each .py file or package in examples/, creates a markdown page under
docs/examples/ with the module docstring as description and the full source
embedded via a fenced code block.

Also generates .nav.yml files in each subdirectory so that mkdocs-awesome-nav
renders a proper hierarchical navigation tree.
"""

import ast
import logging
import re
from pathlib import Path

log = logging.getLogger("mkdocs.hooks.generate_examples")

# Directory name -> human-readable category label
CATEGORIES = {
    "runtime": "Runtime",
    "mcp": "MCP Integration",
    "memory": "Memory",
    "deep_research": "Deep Research",
    "code_agent": "Code Agent",
    "actusbot": "ActusBot",
    "openai_agents": "OpenAI Agents",
    "claude_adk": "Claude ADK",
    "omni": "Omni",
}

# Directories to skip
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "credentials", "cassettes_vcrpy"}


def on_pre_build(config, **kwargs):
    """Generate example .md files and .nav.yml before the MkDocs build runs."""
    docs_dir = Path(config["docs_dir"])
    examples_dir = docs_dir.parent / "examples"
    output_dir = docs_dir / "examples"

    if not examples_dir.exists():
        log.warning("examples/ directory not found, skipping example generation")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect top-level .py files
    top_level_pages = []
    for py_file in sorted(examples_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        _generate_page(py_file, output_dir, examples_dir)
        top_level_pages.append(py_file.stem + ".md")

    # Collect sub-directory categories
    category_dirs = []
    for subdir in sorted(examples_dir.iterdir()):
        if (
            not subdir.is_dir()
            or subdir.name in SKIP_DIRS
            or subdir.name.startswith(("_", "."))
        ):
            continue

        cat_dir = output_dir / subdir.name
        cat_dir.mkdir(parents=True, exist_ok=True)

        label = CATEGORIES.get(subdir.name, subdir.name.replace("_", " ").title())
        _generate_category_index(cat_dir, label, subdir, examples_dir)

        # Generate individual pages and collect for nav
        child_pages = []
        for py_file in sorted(subdir.rglob("*.py")):
            if py_file.name.startswith("_") or any(
                p in SKIP_DIRS for p in py_file.parts
            ):
                continue
            rel_to_subdir = py_file.relative_to(subdir)
            slug = str(rel_to_subdir).replace("/", "_").replace(".py", "")
            _generate_page(py_file, cat_dir, examples_dir, slug=slug)
            child_pages.append(slug + ".md")

        # Write .nav.yml for this category subdirectory
        _generate_nav_yml(cat_dir, label, child_pages)
        category_dirs.append(subdir.name)

    # Write top-level examples/.nav.yml
    _generate_top_nav_yml(output_dir, top_level_pages, category_dirs)


def _extract_docstring(py_file: Path) -> str:
    """Extract the module-level docstring from a Python file."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        return ast.get_docstring(tree) or ""
    except Exception:
        return ""


def _generate_page(
    py_file: Path, output_dir: Path, examples_root: Path, slug: str | None = None
):
    """Write one .md file for a single example .py file."""
    rel = py_file.relative_to(examples_root)
    title = (slug or py_file.stem).replace("_", " ").title()
    docstring = _extract_docstring(py_file)

    md_name = f"{slug or py_file.stem}.md"
    md_path = output_dir / md_name

    lines = [f"# {title}\n"]
    if docstring:
        lines.append(f"\n{docstring}\n")
    lines.append(f"\n**Source:** `examples/{rel}`\n")
    # Use pymdownx.snippets --8<-- to reference the source file at build time,
    # rather than copying file contents into the markdown (vLLM convention).
    # Six backticks avoid conflicts with code fences inside the included file.
    lines.append(f'\n``````python\n--8<-- "examples/{rel}"\n``````\n')

    md_path.write_text("\n".join(lines), encoding="utf-8")


def _rewrite_py_links(content: str, subdir: Path) -> str:
    """Rewrite relative .py markdown links to .md so mkdocs can resolve them."""

    def _replace(m: re.Match) -> str:
        text, target = m.group(1), m.group(2)
        if "://" in target or target.startswith("/"):
            return m.group(0)
        if (subdir / target).exists():
            return f"[{text}]({target.removesuffix('.py')}.md)"
        return m.group(0)

    return re.sub(r"\[([^\]]+)\]\(([^)]+\.py)\)", _replace, content)


def _generate_category_index(
    cat_dir: Path, label: str, subdir: Path, examples_root: Path
):
    """Generate an index.md for an example category."""
    readme = subdir / "README.md"
    md_path = cat_dir / "index.md"

    lines = [f"# {label}\n"]

    if readme.exists():
        content = readme.read_text(encoding="utf-8")
        content_lines = content.split("\n")
        if content_lines and content_lines[0].startswith("# "):
            content_lines = content_lines[1:]
        content = "\n".join(content_lines)
        content = _rewrite_py_links(content, subdir)
        lines.append("\n" + content)

    md_path.write_text("\n".join(lines), encoding="utf-8")


def _generate_nav_yml(cat_dir: Path, label: str, child_pages: list[str]):
    """Write a .nav.yml for a category subdirectory."""
    nav_path = cat_dir / ".nav.yml"
    lines = ["nav:"]
    lines.append("  - index.md")
    for page in child_pages:
        lines.append(f"  - {page}")
    lines.append("")
    nav_path.write_text("\n".join(lines), encoding="utf-8")


def _generate_top_nav_yml(
    output_dir: Path, top_level_pages: list[str], category_dirs: list[str]
):
    """Write the top-level examples/.nav.yml with categories as sections."""
    nav_path = output_dir / ".nav.yml"
    lines = ["nav:"]
    lines.append("  - index.md")

    # Top-level standalone examples
    for page in top_level_pages:
        lines.append(f"  - {page}")

    # Category subdirectories (awesome-nav will pick up their own .nav.yml)
    for dirname in category_dirs:
        label = CATEGORIES.get(dirname, dirname.replace("_", " ").title())
        lines.append(f"  - {label}: {dirname}")

    lines.append("")
    nav_path.write_text("\n".join(lines), encoding="utf-8")
