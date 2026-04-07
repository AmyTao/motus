"""MkDocs hook: remove the 'developer preview' announcement banner for stable releases.

On Read the Docs, tagged builds (stable versions) should not show the
'developer preview' banner defined in main.html. This hook detects the
RTD version type and strips the announcement block if we're on a stable build.
"""

import logging
import os

log = logging.getLogger("mkdocs.hooks.remove_announcement")


def on_config(config, **kwargs):
    """Remove the announcement bar override when building a stable release."""
    version_type = os.environ.get("READTHEDOCS_VERSION_TYPE", "")

    if version_type == "tag":
        log.info("Stable release detected — removing announcement banner")
        # Remove the custom_dir so the announce block override is not applied
        # Alternatively, set a flag that main.html can check
        config["extra"]["is_stable"] = True
    else:
        config["extra"]["is_stable"] = False

    return config
