"""
Standalone utility for managing conversion history.
This module doesn't depend on Qt and can be used by both GUI and CLI components.
"""

import os
import sys
import json
import time


def get_config_dir() -> str:
    """Get the configuration directory path."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        app_data = os.path.expanduser("~/.config")

    config_dir = os.path.join(app_data, "csv-xls-converter")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_history_file_path() -> str:
    """Get the path to the persistent history file."""
    return os.path.join(get_config_dir(), "conversion_history.json")


def add_to_history(
    source_path: str, output_path: str, status: str, error_message: str = ""
) -> bool:
    """
    Add a conversion record to the persistent history.

    Args:
        source_path: Path to the source file
        output_path: Path to the output file
        status: Conversion status ("success", "failed", "skipped")
        error_message: Optional error message if failed

    Returns:
        True if successfully added, False otherwise
    """
    history_file = get_history_file_path()
    max_items = 20

    try:
        # Load existing history
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError):
                history = []

        # Create new history item
        new_item = {
            "source_path": source_path,
            "output_path": output_path,
            "status": status,
            "timestamp": time.time(),
            "error_message": error_message,
        }

        # Check if we're updating an existing "processing" item
        updated = False
        for i, item in enumerate(history):
            if (
                item.get("source_path") == source_path
                and item.get("status") == "processing"
            ):
                history[i] = new_item
                updated = True
                break

        # Add new item at the beginning if not updating
        if not updated:
            history.insert(0, new_item)

        # Trim to max size
        if len(history) > max_items:
            history = history[:max_items]

        # Save to disk
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

        return True

    except Exception as e:
        print(f"Warning: Could not save to conversion history: {e}")
        return False
