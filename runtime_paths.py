from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "Terminal Rogue"


def get_resource_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_project_root() -> Path:
    return Path(__file__).resolve().parent


def get_user_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / APP_NAME
    else:
        path = Path.home() / f".{APP_NAME.lower().replace(' ', '_')}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_resource_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return get_resource_root() / path


def resolve_user_data_path(filename: str) -> Path:
    path = Path(filename)
    if path.is_absolute():
        if path.parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return get_user_data_dir() / path
