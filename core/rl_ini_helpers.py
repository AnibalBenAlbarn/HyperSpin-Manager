"""Helpers para INI de RocketLauncher (sin dependencias Qt)."""

from __future__ import annotations

import configparser
import os
from pathlib import Path


def _read_ini(path: str) -> configparser.RawConfigParser | None:
    if not path or not os.path.isfile(path):
        return None
    cfg = configparser.RawConfigParser(strict=False)
    cfg.optionxform = str
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            cfg.read_string(fh.read())
        return cfg
    except Exception:
        return None


def parse_rl_emulators_ini(ini_path: str) -> dict:
    """Parsea ``Emulators.ini`` y devuelve emuladores y módulo por defecto."""
    result = {"default_emulator": "", "rom_path": "", "emulators": {}}
    cfg = _read_ini(ini_path)
    if not cfg:
        return result

    for section in cfg.sections():
        if section.lower() == "roms":
            result["default_emulator"] = cfg.get(section, "Default_Emulator", fallback="").strip()
            result["rom_path"] = cfg.get(section, "Rom_Path", fallback="").strip()
            continue

        module_raw = cfg.get(section, "Module", fallback="").strip()
        result["emulators"][section] = {
            "emu_path": cfg.get(section, "Emu_Path", fallback="").strip(),
            "rom_extension": cfg.get(section, "Rom_Extension", fallback="").strip(),
            "module_raw": module_raw,
            "module_file": Path(module_raw).name if module_raw else "",
            "module_folder": Path(module_raw).parent.name if module_raw else "",
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
