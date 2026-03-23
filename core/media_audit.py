"""Auditoría de media HS/RL desacoplada de UI."""

from __future__ import annotations

import os
from pathlib import Path

from core.xml_helpers import parse_xml_games

HS_MEDIA_STRUCTURE = [
    ("Images/Wheel", True, "Wheels (logos PNG)"),
    ("Images/Artwork1", False, "Artwork 1"),
    ("Images/Artwork2", False, "Artwork 2"),
    ("Images/Artwork3", False, "Artwork 3"),
    ("Images/Artwork4", False, "Artwork 4"),
    ("Images/Backgrounds", False, "Fondos"),
    ("Themes", True, "Temas (ZIP)"),
    ("Video", True, "Vídeos"),
]
RL_MEDIA_STRUCTURE = [
    ("Bezels", False, "Bezels RocketLauncher"),
    ("Fade", False, "Fade RocketLauncher"),
]

WHEEL_EXTS = {".png", ".jpg", ".jpeg"}
THEME_EXTS = {".zip"}
VIDEO_EXTS = {".mp4", ".flv", ".avi", ".mkv", ".m4v"}


def _count_files_in(folder: str, exts: set | None = None) -> int:
    if not os.path.isdir(folder):
        return -1
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    if exts:
        files = [f for f in files if Path(f).suffix.lower() in exts]
    return len(files)


def _file_stems(folder: str, exts: set) -> set[str]:
    if not os.path.isdir(folder):
        return set()
    return {
        Path(f).stem.lower()
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and Path(f).suffix.lower() in exts
    }


class AuditWorker:
    """Worker de auditoría reusable desde UI o tests (sin QThread)."""

    def __init__(self, system_name: str, config: dict):
        self.system_name = system_name
        self.config = config

    def run(self) -> dict:
        hs_dir = self.config.get("hyperspin_dir", "")
        rl_dir = self.config.get("rocketlauncher_dir", "")
        rlui_dir = self.config.get("rocketlauncherui_dir", "")
        name = self.system_name

        hs_media = os.path.join(hs_dir, "Media", name)
        hs_wheel = os.path.join(hs_media, "Images", "Wheel")
        hs_theme = os.path.join(hs_media, "Themes")
        hs_video = os.path.join(hs_media, "Video")
        rl_bezel = os.path.join(rl_dir, "Media", "Bezels", name) if rl_dir else ""
        rl_fade = os.path.join(rl_dir, "Media", "Fade", name) if rl_dir else ""

        hs_db_path = os.path.join(hs_dir, "Databases", name, f"{name}.xml")
        rl_db_path = os.path.join(rlui_dir, "Databases", name, f"{name}.xml") if rlui_dir else ""

        wheels = _file_stems(hs_wheel, WHEEL_EXTS)
        themes = _file_stems(hs_theme, THEME_EXTS)
        videos = _file_stems(hs_video, VIDEO_EXTS)

        hs_games = parse_xml_games(hs_db_path)
        rl_games = parse_xml_games(rl_db_path) if rl_db_path else []
        rl_names = {g["name"].lower() for g in rl_games}

        rows = []
        for g in hs_games:
            key = g["name"].lower()
            rows.append(
                {
                    "name": g["name"],
                    "description": g.get("description") or g["name"],
                    "wheel": key in wheels,
                    "theme": key in themes,
                    "video": key in videos,
                    "in_rl_db": key in rl_names,
                }
            )

        media_stats = {}
        for rel_path, required, label in HS_MEDIA_STRUCTURE:
            abs_path = os.path.join(hs_media, rel_path.replace("/", os.sep))
            exts = {"Images/Wheel": WHEEL_EXTS, "Themes": THEME_EXTS, "Video": VIDEO_EXTS}.get(rel_path)
            media_stats[rel_path] = {
                "path": abs_path,
                "exists": os.path.isdir(abs_path),
                "count": _count_files_in(abs_path, exts),
                "required": required,
                "label": label,
            }

        media_stats["RL/Bezels"] = {
            "path": rl_bezel,
            "exists": os.path.isdir(rl_bezel) if rl_bezel else False,
            "count": _count_files_in(rl_bezel) if rl_bezel else -1,
            "required": False,
            "label": "Bezels RocketLauncher",
        }
        media_stats["RL/Fade"] = {
            "path": rl_fade,
            "exists": os.path.isdir(rl_fade) if rl_fade else False,
            "count": _count_files_in(rl_fade) if rl_fade else -1,
            "required": False,
            "label": "Fade RocketLauncher",
        }

        return {
            "rows": rows,
            "media_stats": media_stats,
            "hs_db_path": hs_db_path,
            "rl_db_path": rl_db_path,
            "hs_count": len(hs_games),
            "rl_count": len(rl_games),
            "system_name": name,
        }
