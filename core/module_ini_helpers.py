"""Helpers para INIs de módulo: PCLauncher y TeknoParrot."""

from __future__ import annotations

import configparser
import os
import re


def _read_ini_skip_preamble(ini_path: str) -> configparser.RawConfigParser:
    cfg = configparser.RawConfigParser(strict=False)
    cfg.optionxform = str
    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        first_section = next((i for i, line in enumerate(lines) if re.match(r"^\s*\[[^\]]+\]", line)), None)
        cfg.read_string("".join(lines[first_section or 0:]))
    except Exception:
        pass
    return cfg


def _upsert_section_block(ini_path: str, section_name: str, section_content: str, template: str) -> bool:
    """Inserta o reemplaza el bloque `[section_name]`."""
    if not os.path.isfile(ini_path):
        with open(ini_path, "w", encoding="utf-8") as fh:
            fh.write(template + "\n" + section_content)
        return False

    with open(ini_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    header = f"[{section_name}]"
    if header in content:
        pattern = re.compile(r"(?m)^\[" + re.escape(section_name) + r"\].*?(?=^\[|\Z)", re.DOTALL)
        with open(ini_path, "w", encoding="utf-8") as fh:
            fh.write(pattern.sub(section_content, content, count=1))
        return True

    with open(ini_path, "a", encoding="utf-8") as fh:
        fh.write("\n" + section_content)
    return False


def make_pclauncher_games_ini_entry(
    game_name: str,
    application: str,
    fade_title: str = "",
    exit_method: str = "InGame",
    app_wait_exe: str = "",
    post_launch: str = "",
    post_exit: str = "",
    fullscreen: bool = False,
    fade_title_timeout: int = 0,
) -> str:
    lines = [f"[{game_name}]", f"Application={application}"]
    if fade_title:
        lines.append(f"FadeTitle={fade_title}")
    if exit_method:
        lines.append(f"ExitMethod={exit_method}")
    if app_wait_exe:
        lines.append(f"AppWaitExe={app_wait_exe}")
    if fullscreen:
        lines.append("Fullscreen=true")
    if fade_title_timeout > 0:
        lines.append(f"FadeTitleTimeout={fade_title_timeout}")
    if post_launch:
        lines.append(f"PostLaunch={post_launch}")
    if post_exit:
        lines.append(f"PostExit={post_exit}")
    return "\n".join(lines) + "\n"


def append_pclauncher_game(
    games_ini_path: str,
    game_name: str,
    application: str,
    fade_title: str = "",
    exit_method: str = "InGame",
    app_wait_exe: str = "",
    post_launch: str = "",
    post_exit: str = "",
    fullscreen: bool = False,
    fade_title_timeout: int = 0,
) -> bool:
    entry = make_pclauncher_games_ini_entry(
        game_name=game_name,
        application=application,
        fade_title=fade_title,
        exit_method=exit_method,
        app_wait_exe=app_wait_exe,
        post_launch=post_launch,
        post_exit=post_exit,
        fullscreen=fullscreen,
        fade_title_timeout=fade_title_timeout,
    )
    template = "; Games.ini — PCLauncher\n; Generado por HyperSpin Manager"
    return _upsert_section_block(games_ini_path, game_name, entry, template)


def parse_pclauncher_games_ini(games_ini_path: str) -> list[dict]:
    if not os.path.isfile(games_ini_path):
        return []
    cfg = _read_ini_skip_preamble(games_ini_path)
    rows = []
    for section in cfg.sections():
        rows.append(
            {
                "name": section,
                "application": cfg.get(section, "Application", fallback=""),
                "fade_title": cfg.get(section, "FadeTitle", fallback=""),
                "exit_method": cfg.get(section, "ExitMethod", fallback=""),
                "app_wait_exe": cfg.get(section, "AppWaitExe", fallback=""),
                "post_launch": cfg.get(section, "PostLaunch", fallback=""),
                "post_exit": cfg.get(section, "PostExit", fallback=""),
                "fullscreen": cfg.get(section, "Fullscreen", fallback=""),
                "fade_title_timeout": cfg.get(section, "FadeTitleTimeout", fallback=""),
            }
        )
    return rows


def make_teknoparrot_games_ini_entry(game_name: str, short_name: str, profile_path: str, game_path: str = "", fade_title: str = "") -> str:
    if not fade_title:
        fade_title = f"Play! - [ {short_name} ] - TeknoParrot ahk_class Qt5152QWindowIcon"
    cmd = f'TeknoParrotUi.exe --startMinimized --profile="{profile_path}"'
    lines = [
        f"[{game_name}]",
        f"ShortName = {short_name}",
        f"FadeTitle = {fade_title}",
        f"CommandLine = {cmd}",
    ]
    if game_path:
        lines.append(f"GamePath = {game_path}")
    return "\n".join(lines) + "\n"


def append_teknoparrot_game(games_ini_path: str, game_name: str, short_name: str, profile_path: str, game_path: str = "", fade_title: str = "") -> bool:
    entry = make_teknoparrot_games_ini_entry(game_name, short_name, profile_path, game_path, fade_title)
    template = "; Games.ini — TeknoParrot\n; Generado por HyperSpin Manager"
    return _upsert_section_block(games_ini_path, game_name, entry, template)


def parse_teknoparrot_games_ini(games_ini_path: str) -> list[dict]:
    if not os.path.isfile(games_ini_path):
        return []
    cfg = _read_ini_skip_preamble(games_ini_path)
    rows = []
    for section in cfg.sections():
        rows.append(
            {
                "name": section,
                "short_name": cfg.get(section, "ShortName", fallback="").strip(),
                "fade_title": cfg.get(section, "FadeTitle", fallback="").strip(),
                "command_line": cfg.get(section, "CommandLine", fallback="").strip(),
                "game_path": cfg.get(section, "GamePath", fallback="").strip(),
            }
        )
    return rows


def detect_tp_window_class(games_ini_path: str) -> str:
    for game in parse_teknoparrot_games_ini(games_ini_path):
        fade = game.get("fade_title", "")
        if "Qt692" in fade:
            return "Qt692QWindowIcon"
        if "Qt5152" in fade:
            return "Qt5152QWindowIcon"
    return "Qt5152QWindowIcon"


def remove_games_from_module_ini(ini_path: str, name_set: set[str]) -> int:
    """
    Elimina secciones por nombre (case-insensitive) preservando preámbulo/comentarios.
    """
    if not os.path.isfile(ini_path):
        return 0

    lowered = {str(n).strip().lower() for n in name_set if str(n).strip()}
    if not lowered:
        return 0

    with open(ini_path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()

    first_sec = next((i for i, line in enumerate(lines) if re.match(r"^\s*\[", line)), len(lines))
    header = lines[:first_sec]
    body = lines[first_sec:]

    out_body = []
    skip = False
    removed = 0
    for line in body:
        m = re.match(r"^\s*\[(.+)\]\s*$", line)
        if m:
            key = m.group(1).strip().lower()
            if key in lowered:
                skip = True
                removed += 1
                continue
            skip = False
        if not skip:
            out_body.append(line)

    if removed > 0:
        with open(ini_path, "w", encoding="utf-8") as fh:
            fh.writelines(header + out_body)
    return removed
