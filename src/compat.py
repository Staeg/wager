"""Shared compatibility helpers."""

import os
import sys


def get_asset_dir():
    """Return the path to the assets directory, handling PyInstaller frozen builds."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "assets")
    return os.path.join(os.path.dirname(__file__), "..", "assets")


def setup_frozen_path():
    """Insert MEIPASS into sys.path for frozen builds."""
    if getattr(sys, "frozen", False):
        sys.path.insert(0, sys._MEIPASS)
