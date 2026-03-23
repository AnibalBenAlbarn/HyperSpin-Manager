"""Helpers para INI de RocketLauncher (sin dependencias Qt)."""

from __future__ import annotations

import configparser
import os
import re
from pathlib import Path, PureWindowsPath


def _read_ini(path: str) -> configparser.RawConfigParser | None:
    if not path or not os.path.isfile(path):
        return None
    cfg = configparser.RawConfigParser(strict=False)
    cfg.optionxform = str
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read().lstrip("\ufeff")
        try:
            cfg.read_string(raw)
        except configparser.MissingSectionHeaderError:
            cfg.read_string("[_ROOT_]\n" + raw)
        return cfg
    except Exception:
        return None


def read_rl_folder_from_rlui_ini(ini_path: str) -> str:
    """
    Devuelve el valor de ``RL_Folder`` desde ``RocketLauncherUI.ini``.
    Soporta INI normal, key/value plano y archivos con BOM/preambulo.
    """
    cfg = _read_ini(ini_path)
    if cfg:
        for section in cfg.sections():
            for key, value in cfg.items(section):
                if key.strip().lower() == "rl_folder":
                    return (value or "").strip().strip('"')

    if not ini_path or not os.path.isfile(ini_path):
        return ""
    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except Exception:
        return ""

    match = re.search(r"(?im)^\s*RL_Folder\s*=\s*(.+?)\s*$", raw)
    if not match:
        return ""
    return match.group(1).strip().strip('"')


def parse_rl_emulators_ini(ini_path: str) -> dict:
    """Parsea ``Emulators.ini`` y devuelve emuladores y módulo por defecto."""
    result = {"default_emulator": "", "rom_path": "", "emulators": {}}
    cfg = _read_ini(ini_path)
    if not cfg:
        return result

    root_section = "_ROOT_"
    if cfg.has_section(root_section):
        result["default_emulator"] = cfg.get(root_section, "Default_Emulator", fallback="").strip()
        result["rom_path"] = cfg.get(root_section, "Rom_Path", fallback="").strip()

    for section in cfg.sections():
        if section == root_section:
            continue
        if section.lower() == "roms":
            result["default_emulator"] = cfg.get(section, "Default_Emulator", fallback="").strip()
            result["rom_path"] = cfg.get(section, "Rom_Path", fallback="").strip()
            continue

        module_raw = cfg.get(section, "Module", fallback="").strip()
        module_path = PureWindowsPath(module_raw) if module_raw else None
        result["emulators"][section] = {
            "emu_path": cfg.get(section, "Emu_Path", fallback="").strip(),
            "rom_extension": cfg.get(section, "Rom_Extension", fallback="").strip(),
            "module_raw": module_raw,
            "module_file": module_path.name if module_path else "",
            "module_folder": module_path.parent.name if module_path else "",
            "virtual": cfg.get(section, "Virtual_Emulator", fallback="false").lower() == "true",
        }
    return result


def parse_rl_rocketlauncher_ini(ini_path: str) -> dict:
    """Parsea ``RocketLauncher.ini`` y separa overrides vs ``use_global``."""
    result = {"overrides": {}, "using_global": [], "sections": [], "raw": {}}
    cfg = _read_ini(ini_path)
    if not cfg:
        return result

    result["sections"] = cfg.sections()
    for section in cfg.sections():
        result["raw"][section] = {}
        for key, val in cfg.items(section):
            value = (val or "").strip()
            result["raw"][section][key] = value
            fq_key = f"{section}.{key}"
            if value.lower() == "use_global":
                result["using_global"].append(fq_key)
            else:
                result["overrides"][fq_key] = value
    return result


def find_module_in_rl(rl_dir: str, module_file: str, module_folder: str = "") -> str:
    """Busca un ``.ahk`` dentro de ``RocketLauncher/Modules``."""
    if not rl_dir or not module_file:
        return ""

    modules_base = os.path.join(rl_dir, "Modules")
    if module_folder:
        candidate = os.path.join(modules_base, module_folder, module_file)
        if os.path.isfile(candidate):
            return candidate

    candidate = os.path.join(modules_base, module_file)
    if os.path.isfile(candidate):
        return candidate

    if os.path.isdir(modules_base):
        for folder in os.listdir(modules_base):
            fpath = os.path.join(modules_base, folder, module_file)
            if os.path.isfile(fpath):
                return fpath
    return ""


def get_module_ini_path(rl_dir: str, system_name: str) -> str:
    """Ruta del INI propio del sistema para módulos tipo PCLauncher/TeknoParrot."""
    return os.path.join(rl_dir, "Settings", system_name, f"{system_name}.ini")
