"""Helpers de estadísticas globales para Dashboard."""

from __future__ import annotations

import os
from pathlib import Path

from core.xml_helpers import parse_xml_games

WHEEL_EXTS = {".png", ".jpg", ".jpeg"}
THEME_EXTS = {".zip"}
VIDEO_EXTS = {".mp4", ".flv", ".avi", ".mkv", ".m4v"}


def _file_stems(folder: str, exts: set[str]) -> set[str]:
    if not os.path.isdir(folder):
        return set()
    try:
        return {
            Path(f).stem.lower()
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f)) and Path(f).suffix.lower() in exts
        }
    except PermissionError:
        return set()


def _bezel_game_names(rl_dir: str, system_name: str) -> set[str]:
    if not rl_dir:
        return set()
    bezel_sys = os.path.join(rl_dir, "Media", "Bezels", system_name)
    if not os.path.isdir(bezel_sys):
        return set()
    try:
        return {
            d.lower()
            for d in os.listdir(bezel_sys)
            if os.path.isdir(os.path.join(bezel_sys, d)) and d.lower() != "_default"
        }
    except PermissionError:
        return set()


def collect_dashboard_stats(config: dict, progress_cb=None) -> dict:
    hs_dir = config.get("hyperspin_dir", "")
    rl_dir = config.get("rocketlauncher_dir", "")
    db_root = os.path.join(hs_dir, "Databases") if hs_dir else ""

    if not os.path.isdir(db_root):
        return {
            "systems": 0,
            "games": 0,
            "wheel_pct": 0.0,
            "video_pct": 0.0,
            "theme_pct": 0.0,
            "bezel_pct": 0.0,
            "incomplete_systems": [],
        }

    candidates = []
    for system_name in sorted(os.listdir(db_root)):
        sys_dir = os.path.join(db_root, system_name)
        if not os.path.isdir(sys_dir):
            continue
        xml_path = os.path.join(sys_dir, f"{system_name}.xml")
        if os.path.isfile(xml_path):
            candidates.append((system_name, xml_path))

    total_systems = len(candidates)
    total_games = 0
    wheel_ok = theme_ok = video_ok = bezel_ok = 0
    incomplete = []

    for idx, (sys_name, xml_path) in enumerate(candidates, start=1):
        if progress_cb:
            progress_cb(int(idx * 100 / max(total_systems, 1)), f"Escaneando {sys_name}…")

        games = parse_xml_games(xml_path)
        if not games:
            continue
        names = {g["name"].lower() for g in games}
        total_games += len(games)

        hs_media = os.path.join(hs_dir, "Media", sys_name)
        wheels = _file_stems(os.path.join(hs_media, "Images", "Wheel"), WHEEL_EXTS)
        themes = _file_stems(os.path.join(hs_media, "Themes"), THEME_EXTS)
        videos = _file_stems(os.path.join(hs_media, "Video"), VIDEO_EXTS)
        bezels = _bezel_game_names(rl_dir, sys_name)

        sys_missing = []
        for nm in names:
            has_wheel = nm in wheels
            has_theme = nm in themes
            has_video = nm in videos
            has_bezel = nm in bezels if rl_dir else False
            wheel_ok += int(has_wheel)
            theme_ok += int(has_theme)
            video_ok += int(has_video)
            bezel_ok += int(has_bezel)
            if not has_wheel or not has_theme or not has_video:
                sys_missing.append(nm)

        if sys_missing:
            incomplete.append(
                {
                    "system": sys_name,
                    "missing_count": len(sys_missing),
                    "total": len(games),
                }
            )

    def _pct(v: int) -> float:
        return (v * 100.0 / total_games) if total_games else 0.0

    incomplete.sort(key=lambda x: (-x["missing_count"], x["system"].lower()))
    return {
        "systems": total_systems,
        "games": total_games,
        "wheel_pct": _pct(wheel_ok),
        "theme_pct": _pct(theme_ok),
        "video_pct": _pct(video_ok),
        "bezel_pct": _pct(bezel_ok),
        "incomplete_systems": incomplete,
    }
