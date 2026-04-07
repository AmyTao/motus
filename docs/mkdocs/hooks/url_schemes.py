"""MkDocs hook: handle special URL schemes and GitHub references.

- Converts relative file links outside docs/ to GitHub blob URLs
- Renders GitHub issue/PR references (#123) as clickable links with icons
"""

import logging
import re

log = logging.getLogger("mkdocs.hooks.url_schemes")

# Pattern to match GitHub issue/PR references like #123
GITHUB_REF_PATTERN = re.compile(r"(?<!\w)#(\d+)(?!\w)")


def on_page_markdown(markdown, page, config, files, **kwargs):
    """Process markdown content to enhance URL handling."""
    repo_url = config.get("repo_url", "").rstrip("/")
    if not repo_url:
        return markdown

    # Convert #123 references to GitHub links
    def replace_github_ref(match):
        number = match.group(1)
        return f"[#{number}]({repo_url}/issues/{number})"

    markdown = GITHUB_REF_PATTERN.sub(replace_github_ref, markdown)

    return markdown
