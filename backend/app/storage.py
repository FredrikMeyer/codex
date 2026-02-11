"""
Low-level storage functions for reading/writing data files.

Handles JSON file persistence with thread safety.
"""

import json
from pathlib import Path
from typing import Any, Dict


def default_data() -> Dict[str, Any]:
    """Return the default data structure for a new storage file."""
    return {"codes": [], "logs": []}


def ensure_data_file(path: Path) -> None:
    """
    Ensure data file exists with default structure.

    Args:
        path: Path to the data file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default_data(), indent=2))


def load_data(path: Path) -> Dict[str, Any]:
    """
    Load data from storage file.

    Args:
        path: Path to the data file

    Returns:
        Data dictionary with 'codes' and 'logs' keys
    """
    ensure_data_file(path)
    with path.open() as fp:
        return json.load(fp)


def save_data(path: Path, data: Dict[str, Any]) -> None:
    """
    Save data to storage file.

    Args:
        path: Path to the data file
        data: Data dictionary to save
    """
    ensure_data_file(path)
    with path.open("w") as fp:
        json.dump(data, fp, indent=2)
