"""
KG Registry Module

Reads config/kg_config.yaml and exposes the enabled knowledge graphs so the GUI
can populate a domain selector instead of hardcoding one KG.
"""

from pathlib import Path
from typing import List, Dict
import yaml


def load_enabled_kgs(config_path: str = "config/kg_config.yaml") -> List[Dict]:
    """
    Load the list of enabled knowledge graphs from kg_config.yaml.

    Args:
        config_path: Path to kg_config.yaml (relative paths are resolved against
            the current working directory first, then the web_app package root)

    Returns:
        List of KG entry dicts (name, description, file, sparql_endpoint,
        source_type, notes), in file order, filtered to enabled: true.
    """
    path = Path(config_path)
    if not path.exists():
        package_dir = Path(__file__).parent.parent
        path = package_dir / config_path

    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    kgs = data.get("knowledge_graphs", []) or []
    return [kg for kg in kgs if kg.get("enabled")]
