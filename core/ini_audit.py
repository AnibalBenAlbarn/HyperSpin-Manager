"""Auditoría de INIs de HyperSpin/RocketLauncher (lógica desacoplada de Qt)."""

from __future__ import annotations

import configparser
import json
import os
import re
import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from core.rl_ini_helpers import find_module_in_rl, parse_rl_emulators_ini

INI_TYPE_MMC = "main_menu_changer"
INI_TYPE_REAL = "real_system"
INI_TYPE_EXTERNAL = "external_app"
INI_TYPE_UNKNOWN = "unknown"
REAL_SYSTEM_SECTIONS = {"filters", "themes", "navigation"}
GLOBAL_INI_NAMES = {"settings.ini", "wheel settings.ini", "main menu.ini"}
REGISTRY_FILENAME = "systems_registry.json"


@dataclass
class HyperSpinIniData:
    ini_path: str
    filename: str = ""
    name: str = ""
    raw: dict = field(default_factory=dict)
    sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parse_ok: bool = False

    def __post_init__(self):
        self.filename = os.path.basename(self.ini_path)
        self.name = os.path.splitext(self.filename)[0]

    def parse(self) -> "HyperSpinIniData":
        cfg = configparser.RawConfigParser(strict=False)
        cfg.optionxform = str
        try:
            with open(self.ini_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            invalid_vals = re.findall(r"=\s*(0x[0-9A-Fa-f]*NAN\S*)", content)
            self.warnings.extend(f"Color inválido detectado: {value}" for value in invalid_vals)
            cfg.read_string(content)
            self.sections = cfg.sections()
            self.raw = {section.lower(): dict(cfg.items(section)) for section in self.sections}
            self.parse_ok = True
        except Exception as exc:
            self.warnings.append(f"Error al parsear: {exc}")
        return self

    def get(self, section: str, key: str, default: str = "") -> str:
        return self.raw.get(section.lower(), {}).get(key.lower(), default).strip()

    def has_section(self, section: str) -> bool:
        return section.lower() in self.raw

    @property
    def exe(self) -> str: return self.get("exe info", "exe")
    @property
    def path(self) -> str: return self.get("exe info", "path")
    @property
    def rompath(self) -> str: return self.get("exe info", "rompath")
    @property
    def romextension(self) -> str: return self.get("exe info", "romextension")
    @property
    def parameters(self) -> str: return self.get("exe info", "parameters")
    @property
    def pcgame(self) -> bool: return self.get("exe info", "pcgame", "false").lower() == "true"
    @property
    def hyperlaunch(self) -> bool: return self.get("exe info", "hyperlaunch", "false").lower() == "true"

    @property
    def mmc_filter(self) -> str:
        genres = re.findall(r"genre='([^']+)'", self.parameters)
        return " | ".join(genres) if genres else self.parameters


class IniClassifier:
    @staticmethod
    def classify(data: HyperSpinIniData) -> str:
        exe, path = data.exe.lower(), data.path.lower()
        if "mainmenuchanger" in exe or "mainmenuchanger" in path:
            return INI_TYPE_MMC
        if data.hyperlaunch and not data.pcgame:
            return INI_TYPE_REAL
        if not data.hyperlaunch and not data.pcgame and any(data.has_section(s) for s in REAL_SYSTEM_SECTIONS):
            return INI_TYPE_REAL
        if data.pcgame and not data.hyperlaunch:
            return INI_TYPE_EXTERNAL
        return INI_TYPE_UNKNOWN


@dataclass
class IniAuditResult:
    has_ini: bool = False
    has_xml: bool = False
    has_media: bool = False
    has_rompath: bool = False
    has_rl_settings: bool = False
    has_bezels: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.errors:
            return "ERROR"
        if self.warnings:
            return "AVISO"
        return "OK"


@dataclass
class SystemIniRecord:
    ini_data: HyperSpinIniData
    type: str
    managed: bool = True
    hidden_in_app: bool = False
    audit: IniAuditResult = field(default_factory=IniAuditResult)
    paths: dict = field(default_factory=dict)

    def __post_init__(self):
        self.paths = self.paths or {
            "ini": self.ini_data.ini_path,
            "xml": "",
            "media": "",
            "rocketlauncher_settings": "",
            "bezels": "",
            "fade": "",
            "module": "",
        }

    @property
    def name(self) -> str:
        return self.ini_data.name


class IniAuditService:
    def __init__(self, config: dict, registry_path: str = ""):
        self.config = config
        self.registry_path = registry_path or REGISTRY_FILENAME
        self.records: dict[str, SystemIniRecord] = {}
        self._saved_state: dict = {}

    @property
    def hs_dir(self) -> str: return self.config.get("hyperspin_dir", "")
    @property
    def rl_dir(self) -> str: return self.config.get("rocketlauncher_dir", "")
    @property
    def settings_dir(self) -> str: return os.path.join(self.hs_dir, "Settings")

    def load_registry(self):
        if os.path.isfile(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as fh:
                    self._saved_state = json.load(fh)
            except Exception:
                self._saved_state = {}

    def save_registry(self) -> bool:
        payload = {
            "_meta": {"generated": datetime.now().isoformat(), "hs_dir": self.hs_dir, "rl_dir": self.rl_dir},
            "systems": {
                name: {
                    "name": rec.name,
                    "type": rec.type,
                    "managed": rec.managed,
                    "hidden_in_app": rec.hidden_in_app,
                    "paths": rec.paths,
                    "audit": rec.audit.__dict__,
                }
                for name, rec in self.records.items()
            },
        }
        try:
            with open(self.registry_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def refresh(self, progress_callback=None) -> dict:
        self.load_registry()
        self.records = {}
        if not self.hs_dir or not os.path.isdir(self.settings_dir):
            return {"error": f"Directorio no encontrado: {self.settings_dir}"}

        ini_files = sorted(
            fn for fn in os.listdir(self.settings_dir)
            if fn.lower().endswith(".ini") and fn.lower() not in GLOBAL_INI_NAMES
        )
        for index, filename in enumerate(ini_files, start=1):
            if progress_callback:
                progress_callback(index, len(ini_files), filename)
            data = HyperSpinIniData(os.path.join(self.settings_dir, filename)).parse()
            record = SystemIniRecord(data, IniClassifier.classify(data))
            prev = self._saved_state.get("systems", {}).get(record.name, {})
            record.managed = prev.get("managed", True)
            record.hidden_in_app = prev.get("hidden_in_app", False)
            self._fill_paths(record)
            self._audit(record)
            self.records[record.name] = record

        self.save_registry()
        return {
            "total": len(self.records),
            "by_type": dict(Counter(r.type for r in self.records.values())),
            "with_errors": sum(1 for r in self.records.values() if r.audit.errors),
            "with_warnings": sum(1 for r in self.records.values() if r.audit.warnings),
            "hidden": sum(1 for r in self.records.values() if r.hidden_in_app),
        }

    def _fill_paths(self, rec: SystemIniRecord):
        name = rec.name
        rec.paths["xml"] = os.path.join(self.hs_dir, "Databases", name, f"{name}.xml")
        rec.paths["media"] = os.path.join(self.hs_dir, "Media", name)
        rec.paths["rocketlauncher_settings"] = os.path.join(self.rl_dir, "Settings", name) if self.rl_dir else ""
        rec.paths["bezels"] = os.path.join(self.rl_dir, "Media", "Bezels", name) if self.rl_dir else ""
        rec.paths["fade"] = os.path.join(self.rl_dir, "Media", "Fade", name) if self.rl_dir else ""

        emu_data = parse_rl_emulators_ini(os.path.join(rec.paths["rocketlauncher_settings"], "Emulators.ini"))
        default = emu_data.get("default_emulator", "")
        emulators = emu_data.get("emulators", {})
        emu = emulators.get(default, next(iter(emulators.values()), {}))
        rec.paths["module"] = find_module_in_rl(self.rl_dir, emu.get("module_file", ""), emu.get("module_folder", ""))

    def _audit(self, rec: SystemIniRecord):
        audit, data = rec.audit, rec.ini_data
        audit.has_ini = os.path.isfile(rec.paths["ini"])
        audit.has_xml = os.path.isfile(rec.paths["xml"])
        audit.has_media = os.path.isdir(rec.paths["media"])
        audit.has_rl_settings = os.path.isdir(rec.paths["rocketlauncher_settings"])
        audit.has_bezels = os.path.isdir(rec.paths["bezels"])
        audit.has_rompath = bool(data.rompath)
        audit.warnings.extend(data.warnings)

    def hide_in_app(self, name: str):
        if name in self.records:
            self.records[name].hidden_in_app = True
            self.records[name].managed = False
            self.save_registry()

    def restore_in_app(self, name: str):
        if name in self.records:
            self.records[name].hidden_in_app = False
            self.records[name].managed = True
            self.save_registry()

    def delete_real(self, name: str, options: dict) -> list[str]:
        if name not in self.records:
            return ["Sistema no encontrado"]
        rec = self.records[name]
        actions: list[str] = []

        def _rm_file(path, label):
            if path and os.path.isfile(path):
                os.remove(path)
                actions.append(f"✓ Borrado {label}: {path}")

        def _rm_dir(path, label):
            if path and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
                actions.append(f"✓ Borrada {label}: {path}")

        if options.get("delete_ini"): _rm_file(rec.paths["ini"], "INI")
        if options.get("delete_xml"): _rm_dir(os.path.dirname(rec.paths["xml"]), "carpeta XML")
        if options.get("delete_media"): _rm_dir(rec.paths["media"], "media")
        if options.get("delete_rl"): _rm_dir(rec.paths["rocketlauncher_settings"], "RL Settings")
        if options.get("delete_bezels"): _rm_dir(rec.paths["bezels"], "Bezels")

        del self.records[name]
        self.save_registry()
        return actions
