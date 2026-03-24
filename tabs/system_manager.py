"""
tabs/system_manager.py
SystemManagerTab — Gestor, auditor y comparador de sistemas HyperSpin/RocketLauncher
"""

import os
import re
import json
import shutil
import configparser
from pathlib import Path
from typing import Optional
from datetime import datetime
from collections import Counter

import xml.etree.ElementTree as ET

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QGroupBox, QScrollArea, QFrame, QTabWidget, QHeaderView,
    QMessageBox, QFileDialog, QProgressDialog, QAbstractItemView,
    QSizePolicy, QTextEdit, QDialog, QDialogButtonBox, QCheckBox,
    QGridLayout, QProgressBar, QFormLayout, QMenu, QInputDialog,
    QListWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush
from utils import mainmenu_utils

try:
    from main import TabModule
except ImportError:
    class TabModule:
        tab_title = "Módulo"
        tab_icon  = ""
        def __init__(self, parent): self.parent = parent
        def widget(self): raise NotImplementedError
        def load_data(self, config): pass
        def save_data(self): return {}


# ─── Paleta de colores para tablas ────────────────────────────────────────────
C_OK      = QColor("#0d3a20")
C_OK_FG   = QColor("#69f0ae")
C_WARN    = QColor("#3a2a0a")
C_WARN_FG = QColor("#ffb74d")
C_ERR     = QColor("#3a1020")
C_ERR_FG  = QColor("#ef9a9a")
C_NEUTRAL = QColor("#12151c")
C_DIM     = QColor("#3a4560")

ROM_EXTENSIONS = {
    ".zip", ".7z", ".rar", ".iso", ".bin", ".cue", ".img",
    ".chd", ".rom", ".nes", ".smc", ".sfc", ".gba", ".gb",
    ".gbc", ".n64", ".z64", ".v64", ".nds", ".3ds", ".cia",
    ".cso", ".pbp", ".elf", ".xex", ".gcm", ".rvz", ".wad",
}

# ─── Helpers compartidos (core) ─────────────────────────────────────────────
from core.rl_ini_helpers import (
    find_module_in_rl,
    parse_rl_emulators_ini,
    parse_rl_rocketlauncher_ini,
)
from core.module_ini_helpers import remove_games_from_module_ini

# ─── Estructura de media de RocketLauncher (estructura real observada) ──────
#
# RocketLauncher/Media/
#   Artwork/<Sistema>/<Juego>/           ← artwork por juego
#   Backgrounds/<Sistema>/<Juego>/       ← fondos por juego + _Default/
#   Bezels/<Sistema>/
#     _Default/Horizontal/, _Default/Vertical/
#     <Juego>/                           ← bezels por juego (con Horizontal/Vertical opcionalmente)
#   Controller/                          ← (vacío o global)
#   Fade/<Sistema>/
#     _Default/                          ← fade por defecto
#     <Juego>/                           ← fade por juego
#   Fonts/                               ← fuentes globales
#   Guides/<Sistema>/<Juego>/            ← guías
#   Manuals/<Sistema>/<Juego>/           ← manuales + _Default/
#   Menu Images/Pause/Icons|Mouse Overlay
#   Menu Images/RocketLauncher/
#   Menu Images/Rom Mapping Launch Menu/Icons|Language Flags
#   Moves List/_Default/                 ← lista de movimientos
#   MultiGame/<Sistema>/<Juego>/
#   Music/<Sistema>/<Juego>/
#   Rating/_Default/                     ← imágenes de ratings
#   Shaders/                             ← shaders globales
#   Sounds/Error|Menu|Mouse              ← sonidos UI
#   Videos/<Sistema>/<Juego>|_Default/
#   Wheels/<Sistema>/_Default/           ← wheels de sistema (NO de juegos)

RL_MEDIA_STRUCTURE = [
    # Bezels — estructura principal
    ("Bezels/{sys}",                 True,  "Bezels del sistema"),
    ("Bezels/{sys}/_Default",        True,  "Bezel por defecto"),
    ("Bezels/{sys}/_Default/Horizontal", False, "Bezel horizontal"),
    ("Bezels/{sys}/_Default/Vertical",   False, "Bezel vertical"),
    # Fade
    ("Fade/{sys}",                   False, "Fade del sistema"),
    ("Fade/{sys}/_Default",          False, "Fade por defecto"),
    # Artwork
    ("Artwork/{sys}",                False, "Artwork del sistema"),
    # Backgrounds
    ("Backgrounds/{sys}",            False, "Fondos del sistema"),
    ("Backgrounds/{sys}/_Default",   False, "Fondo por defecto"),
    # Wheels (del sistema en RL Media)
    ("Wheels/{sys}",                 False, "Wheels del sistema (RL)"),
    ("Wheels/{sys}/_Default",        False, "Wheel por defecto"),
    # Guides / Manuals
    ("Guides/{sys}",                 False, "Guías del sistema"),
    ("Manuals/{sys}",                False, "Manuales del sistema"),
    ("Manuals/{sys}/_Default",       False, "Manual por defecto"),
    # MultiGame / Music / Videos
    ("MultiGame/{sys}",              False, "MultiGame del sistema"),
    ("Music/{sys}",                  False, "Música del sistema"),
    ("Videos/{sys}",                 False, "Vídeos del sistema"),
    ("Videos/{sys}/_Default",        False, "Vídeo por defecto"),
]

# Carpetas globales de RocketLauncher/Media (no por sistema)
RL_MEDIA_GLOBAL = [
    ("Controller",                   False, "Controller global"),
    ("Fonts",                        False, "Fuentes"),
    ("Menu Images/Pause/Icons",      False, "Iconos de Pause"),
    ("Menu Images/RocketLauncher",   False, "Imágenes RL UI"),
    ("Moves List/_Default",          False, "Lista de movimientos"),
    ("Rating/_Default",              False, "Imágenes de ratings"),
    ("Shaders",                      False, "Shaders"),
    ("Sounds/Error",                 False, "Sonidos de error"),
    ("Sounds/Menu",                  False, "Sonidos de menú"),
    ("Sounds/Mouse",                 False, "Sonidos de ratón"),
]

INI_TYPE_MMC      = "MAINMENUCHANGER_ENTRY"
INI_TYPE_REAL     = "REAL_SYSTEM"
INI_TYPE_EXTERNAL = "EXTERNAL_APP"
INI_TYPE_UNKNOWN  = "UNKNOWN"

# Archivos globales que NO administramos aquí
GLOBAL_INI_NAMES = {
    "settings.ini", "global rocketlauncher.ini", "global bezel.ini",
    "global plugins.ini", "global pause.ini", "global emulators.ini",
    "frontends.ini", "rocketlauncherui.ini", "rocketlauncher.ini",
    "main menu.ini",
}

REGISTRY_FILENAME = "systems_registry.json"

INI_TYPE_COLORS = {
    INI_TYPE_MMC:      ("#1a3a5e", "#4fc3f7"),
    INI_TYPE_REAL:     ("#1a3e20", "#69f0ae"),
    INI_TYPE_EXTERNAL: ("#3e2e10", "#ffb74d"),
    INI_TYPE_UNKNOWN:  ("#3e1a1a", "#ef9a9a"),
}
INI_TYPE_LABELS = {
    INI_TYPE_MMC:      "MainMenuChanger",
    INI_TYPE_REAL:     "Sistema real",
    INI_TYPE_EXTERNAL: "App externa",
    INI_TYPE_UNKNOWN:  "Desconocido",
}

# Secciones que identifican un sistema real completo
REAL_SYSTEM_SECTIONS = {"filters", "themes", "navigation"}


def _parse_rom_extensions(raw_exts: str) -> set[str]:
    """Normaliza Rom_Extension de RL a set con punto: 'zip|7z' -> {'.zip','.7z'}."""
    if not raw_exts:
        return set()
    parts = re.split(r"[|,; ]+", str(raw_exts).strip())
    out = set()
    for p in parts:
        p = p.strip().lower().lstrip(".")
        if p:
            out.add(f".{p}")
    return out


def _resolve_rl_path(base_dir: str, raw_path: str) -> str:
    """Resuelve rutas de RL con ..\\ y separadores mixtos."""
    if not raw_path:
        return ""
    norm = raw_path.replace("\\", os.sep).replace("/", os.sep)
    if os.path.isabs(norm):
        return os.path.normpath(norm)
    return os.path.normpath(os.path.join(base_dir, norm))


def _file_stem_maps(folder: str, exts: set[str]) -> tuple[set[str], dict[str, set[str]], dict[str, set[str]]]:
    """
    Devuelve:
      - stems lower exactos
      - mapa lower -> stems originales
      - mapa normalizado [a-z0-9] lower -> stems originales
    """
    lower_stems: set[str] = set()
    by_lower: dict[str, set[str]] = {}
    by_norm: dict[str, set[str]] = {}
    if not os.path.isdir(folder):
        return lower_stems, by_lower, by_norm
    try:
        for f in os.listdir(folder):
            full = os.path.join(folder, f)
            if not os.path.isfile(full):
                continue
            if Path(f).suffix.lower() not in exts:
                continue
            stem = Path(f).stem
            stem_l = stem.lower()
            norm = re.sub(r"[^a-z0-9]", "", stem_l)
            lower_stems.add(stem_l)
            by_lower.setdefault(stem_l, set()).add(stem)
            by_norm.setdefault(norm, set()).add(stem)
    except PermissionError:
        pass
    return lower_stems, by_lower, by_norm


# ─── Capa 1: Parser de INI ───────────────────────────────────────────────────

class HyperSpinIniData:
    """
    Parser tolerante de archivos .ini de HyperSpin/Settings.
    Soporta valores inválidos como 0x000NAN sin romper el parseo.
    """

    def __init__(self, ini_path: str):
        self.ini_path  = ini_path
        self.filename  = os.path.basename(ini_path)
        self.name      = os.path.splitext(self.filename)[0]
        self.raw:      dict = {}
        self.sections: list = []
        self.warnings: list = []
        self.parse_ok  = False

    def parse(self) -> "HyperSpinIniData":
        cfg = configparser.RawConfigParser(strict=False)
        cfg.optionxform = str
        try:
            with open(self.ini_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Detectar colores inválidos (0x000NAN, etc.) antes de parsear
            invalid_vals = re.findall(r"=\s*(0x[0-9A-Fa-f]*NAN\S*)", content)
            for iv in invalid_vals:
                self.warnings.append(f"Color inválido detectado: {iv}")
            cfg.read_string(content)
            self.sections = cfg.sections()
            for sec in self.sections:
                self.raw[sec.lower()] = dict(cfg.items(sec))
            self.parse_ok = True
        except Exception as e:
            self.warnings.append(f"Error al parsear: {e}")
        return self

    def get(self, section: str, key: str, default: str = "") -> str:
        return self.raw.get(section.lower(), {}).get(key.lower(), default).strip()

    def has_section(self, section: str) -> bool:
        return section.lower() in self.raw

    # — [exe info] —
    @property
    def exe(self)          -> str:  return self.get("exe info", "exe")
    @property
    def path(self)         -> str:  return self.get("exe info", "path")
    @property
    def rompath(self)      -> str:  return self.get("exe info", "rompath")
    @property
    def romextension(self) -> str:  return self.get("exe info", "romextension")
    @property
    def parameters(self)   -> str:  return self.get("exe info", "parameters")
    @property
    def pcgame(self)       -> bool: return self.get("exe info", "pcgame", "false").lower() == "true"
    @property
    def hyperlaunch(self)  -> bool: return self.get("exe info", "hyperlaunch", "false").lower() == "true"
    @property
    def winstate(self)     -> str:  return self.get("exe info", "winstate")

    # — secciones visuales —
    @property
    def has_wheel(self)      -> bool: return self.has_section("wheel")
    @property
    def has_filters(self)    -> bool: return self.has_section("filters")
    @property
    def has_navigation(self) -> bool: return self.has_section("navigation")
    @property
    def has_themes(self)     -> bool: return self.has_section("themes")
    @property
    def has_game_text(self)  -> bool: return self.has_section("game text")
    @property
    def has_special_art(self) -> bool:
        return any(self.has_section(f"special art {x}") for x in ("a", "b", "c"))

    @property
    def mmc_filter(self) -> str:
        """Extrae el filtro de género del campo parameters (genre='X'_OR_genre='Y')."""
        params = self.parameters
        genres = re.findall(r"genre='([^']+)'", params)
        if genres:
            return " | ".join(genres)
        return params  # All, Back, etc.


# ─── Capa 2: Clasificador ───────────────────────────────────────────────────

class IniClassifier:
    """
    Clasifica un HyperSpinIniData en uno de los 4 tipos.
    Reglas basadas en los INIs reales observados.
    """

    @staticmethod
    def classify(data: HyperSpinIniData) -> str:
        exe  = data.exe.lower()
        path = data.path.lower()

        # REGLA 1 — MainMenuChanger (prioridad absoluta)
        if "mainmenuchanger" in exe or "mainmenuchanger" in path:
            return INI_TYPE_MMC

        # REGLA 2 — Sistema real (hyperlaunch=true + secciones visuales)
        if data.hyperlaunch and not data.pcgame:
            return INI_TYPE_REAL
        # Sistema real sin configurar (paths vacíos pero secciones presentes)
        if not data.hyperlaunch and not data.pcgame:
            if any(data.has_section(s) for s in REAL_SYSTEM_SECTIONS):
                return INI_TYPE_REAL

        # REGLA 3 — App externa (pcgame=true, exe propio)
        if data.pcgame and not data.hyperlaunch:
            return INI_TYPE_EXTERNAL

        return INI_TYPE_UNKNOWN


# ─── Capa 3: Modelo de datos ─────────────────────────────────────────────────

class IniAuditResult:
    """Resultado de auditoría de un sistema individual."""

    def __init__(self):
        self.has_ini          = False
        self.has_xml          = False
        self.has_media        = False
        self.has_rompath      = False
        self.has_rl_settings  = False
        self.has_bezels       = False
        self.warnings: list   = []
        self.errors:   list   = []

    @property
    def status(self) -> str:
        if self.errors:   return "ERROR"
        if self.warnings: return "AVISO"
        return "OK"

    def to_dict(self) -> dict:
        return {
            "has_ini": self.has_ini, "has_xml": self.has_xml,
            "has_media": self.has_media, "has_rompath": self.has_rompath,
            "has_rl_settings": self.has_rl_settings, "has_bezels": self.has_bezels,
            "warnings": self.warnings, "errors": self.errors,
        }


class SystemIniRecord:
    """Registro completo: INI parseado + clasificación + auditoría."""

    def __init__(self, data: HyperSpinIniData, ini_type: str):
        self.name          = data.name
        self.ini_file      = data.filename
        self.type          = ini_type
        self.managed       = True
        self.hidden_in_app = False
        self.ini_data      = data
        self.audit         = IniAuditResult()
        self.paths: dict   = {
            "ini": data.ini_path, "xml": "", "media": "",
            "rocketlauncher_settings": "", "bezels": "",
        }

    def to_dict(self) -> dict:
        d = self.ini_data
        return {
            "name": self.name, "ini_file": self.ini_file,
            "type": self.type, "managed": self.managed,
            "hidden_in_app": self.hidden_in_app,
            "ini_info": {
                "exe": d.exe, "path": d.path, "rompath": d.rompath,
                "romextension": d.romextension, "parameters": d.parameters,
                "pcgame": d.pcgame, "hyperlaunch": d.hyperlaunch,
                "winstate": d.winstate, "mmc_filter": d.mmc_filter,
                "has_wheel": d.has_wheel, "has_filters": d.has_filters,
                "has_navigation": d.has_navigation, "has_special_art": d.has_special_art,
                "has_game_text": d.has_game_text, "sections": d.sections,
                "warnings": d.warnings,
            },
            "paths": self.paths,
            "audit": self.audit.to_dict(),
        }


# ─── Capa 4: Servicio de auditoría ───────────────────────────────────────────

class IniAuditService:
    """
    Lee, clasifica y audita todos los .ini de HyperSpin/Settings.
    Mantiene el registro en memoria y lo persiste en systems_registry.json.
    """

    def __init__(self, config: dict, registry_path: str = ""):
        self.config        = config
        self.registry_path = registry_path or REGISTRY_FILENAME
        self.records: dict = {}          # name → SystemIniRecord
        self._saved_state: dict = {}

    @property
    def hs_dir(self) -> str:
        return self.config.get("hyperspin_dir", "")

    @property
    def rl_dir(self) -> str:
        return self.config.get("rocketlauncher_dir", "")

    @property
    def settings_dir(self) -> str:
        return os.path.join(self.hs_dir, "Settings")

    @staticmethod
    def _is_global(filename: str) -> bool:
        return filename.lower() in GLOBAL_INI_NAMES

    # -- Persistencia ---------------------------------------------------------

    def load_registry(self):
        if os.path.isfile(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    self._saved_state = json.load(f)
            except Exception:
                self._saved_state = {}

    def save_registry(self) -> bool:
        data = {
            "_meta": {
                "generated": datetime.now().isoformat(),
                "hs_dir": self.hs_dir, "rl_dir": self.rl_dir,
            },
            "systems": {name: rec.to_dict() for name, rec in self.records.items()}
        }
        try:
            os.makedirs(os.path.dirname(self.registry_path) or ".", exist_ok=True)
            tmp_path = self.registry_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.registry_path)
            return True
        except Exception as e:
            print(f"[ERROR] No se pudo guardar registry: {e}")
            return False

    def _build_record_for_system(self, name: str) -> SystemIniRecord:
        ini_path = os.path.join(self.settings_dir, f"{name}.ini")
        if os.path.isfile(ini_path):
            data = HyperSpinIniData(ini_path).parse()
            ini_type = IniClassifier.classify(data)
        else:
            data = HyperSpinIniData(ini_path)
            data.name = name
            data.filename = f"{name}.ini"
            ini_type = INI_TYPE_REAL
        rec = SystemIniRecord(data, ini_type)
        self._fill_paths(rec)
        self._audit(rec)
        return rec

    # -- Escaneo principal ----------------------------------------------------

    def refresh(self, progress_callback=None) -> dict:
        """
        Lee todos los .ini de HyperSpin/Settings, los clasifica y audita.
        Devuelve estadísticas del escaneo.
        """
        self.load_registry()
        self.records = {}

        if not self.hs_dir or not os.path.isdir(self.settings_dir):
            return {"error": f"Directorio no encontrado: {self.settings_dir}"}

        ini_files = sorted(
            f for f in os.listdir(self.settings_dir)
            if f.lower().endswith(".ini") and not self._is_global(f)
        )
        total = len(ini_files)

        for i, filename in enumerate(ini_files):
            if progress_callback:
                try:
                    progress_callback(i + 1, total, filename)
                except Exception:
                    pass
            ini_path = os.path.join(self.settings_dir, filename)
            data     = HyperSpinIniData(ini_path).parse()
            ini_type = IniClassifier.classify(data)
            rec      = SystemIniRecord(data, ini_type)

            # Restaurar managed/hidden del estado previo
            prev = self._saved_state.get("systems", {}).get(data.name, {})
            if prev:
                rec.managed       = prev.get("managed", True)
                rec.hidden_in_app = prev.get("hidden_in_app", False)

            self._fill_paths(rec)
            self._audit(rec)
            self.records[data.name] = rec

        stats = {
            "total":         len(self.records),
            "by_type":       dict(Counter(r.type for r in self.records.values())),
            "with_errors":   sum(1 for r in self.records.values() if r.audit.errors),
            "with_warnings": sum(1 for r in self.records.values() if r.audit.warnings),
            "hidden":        sum(1 for r in self.records.values() if r.hidden_in_app),
        }
        self.save_registry()
        return stats

    def _compute_stats(self) -> dict:
        return {
            "total":         len(self.records),
            "by_type":       dict(Counter(r.type for r in self.records.values())),
            "with_errors":   sum(1 for r in self.records.values() if r.audit.errors),
            "with_warnings": sum(1 for r in self.records.values() if r.audit.warnings),
            "hidden":        sum(1 for r in self.records.values() if r.hidden_in_app),
        }

    def import_from_rocketlauncher(self, progress_callback=None) -> dict:
        """
        Importa sistemas existentes en RocketLauncher/Settings al registro.
        No duplica sistemas que ya estén registrados.
        """
        if not self.rl_dir:
            return {"error": "RocketLauncher no está configurado."}
        settings_root = os.path.join(self.rl_dir, "Settings")
        if not os.path.isdir(settings_root):
            return {"error": f"No existe: {settings_root}"}

        # Cargar estado previo y completar records actuales si están vacíos.
        self.load_registry()
        if not self.records:
            self.refresh()

        candidates = sorted(
            d for d in os.listdir(settings_root)
            if os.path.isdir(os.path.join(settings_root, d))
            and d.lower() not in {"global", "_global", "default"}
        )
        imported = 0
        skipped = 0
        for idx, name in enumerate(candidates, start=1):
            if progress_callback:
                try:
                    progress_callback(idx, len(candidates), name)
                except Exception:
                    pass
            if name in self.records:
                skipped += 1
                continue

            rec = self._build_record_for_system(name)
            # Clasificación orientada a RL cuando falta INI de HyperSpin.
            if not os.path.isfile(rec.paths.get("ini", "")):
                emu_ini = os.path.join(settings_root, name, "Emulators.ini")
                emu_data = parse_rl_emulators_ini(emu_ini)
                default_emu = emu_data.get("default_emulator", "")
                module = ""
                if default_emu and default_emu in emu_data.get("emulators", {}):
                    module = emu_data["emulators"][default_emu].get("module_file", "").lower()
                if any(x in module for x in ("pclauncher", "teknoparrot", "pc game")):
                    rec.type = INI_TYPE_EXTERNAL
                else:
                    rec.type = INI_TYPE_REAL
                rec.audit.warnings.append("Importado desde RL Settings (sin INI de HyperSpin).")

            self.records[name] = rec
            imported += 1

        self.save_registry()
        stats = self._compute_stats()
        stats.update({"imported": imported, "skipped": skipped, "scanned_rl": len(candidates)})
        return stats

    def _fill_paths(self, rec: SystemIniRecord):
        name   = rec.name
        hs_dir = self.hs_dir
        rl_dir = self.rl_dir

        # HyperSpin paths
        rec.paths["xml"]   = os.path.join(hs_dir, "Databases", name, f"{name}.xml")
        rec.paths["media"] = os.path.join(hs_dir, "Media", name)

        # RocketLauncher Settings
        rl_settings = os.path.join(rl_dir, "Settings", name) if rl_dir else ""
        rec.paths["rocketlauncher_settings"] = rl_settings

        # RL Media — rutas más importantes
        rec.paths["bezels"] = os.path.join(rl_dir, "Media", "Bezels", name) if rl_dir else ""
        rec.paths["fade"]   = os.path.join(rl_dir, "Media", "Fade",   name) if rl_dir else ""

        # Emulators.ini — leer el módulo configurado
        emulators_ini = os.path.join(rl_settings, "Emulators.ini") if rl_settings else ""
        emu_data      = parse_rl_emulators_ini(emulators_ini)
        default_emu   = emu_data.get("default_emulator", "")
        emulators     = emu_data.get("emulators", {})

        mod_file = mod_folder = ""
        if default_emu and default_emu in emulators:
            mod_file   = emulators[default_emu].get("module_file", "")
            mod_folder = emulators[default_emu].get("module_folder", "")
        elif emulators:
            first = next(iter(emulators.values()))
            mod_file   = first.get("module_file", "")
            mod_folder = first.get("module_folder", "")

        mod_path = find_module_in_rl(rl_dir, mod_file, mod_folder) if rl_dir else ""
        rec.paths["module"] = mod_path

        # Guardar datos del emulador para auditoría avanzada
        rec.paths["_default_emulator"] = default_emu
        rec.paths["_module_file"]      = mod_file

    def _audit(self, rec: SystemIniRecord):
        a, d, t = rec.audit, rec.ini_data, rec.type
        a.has_ini         = os.path.isfile(rec.paths["ini"])
        a.has_xml         = os.path.isfile(rec.paths["xml"])
        a.has_media       = os.path.isdir(rec.paths["media"])
        a.has_rl_settings = bool(rec.paths["rocketlauncher_settings"]) and \
                            os.path.isdir(rec.paths["rocketlauncher_settings"])
        a.has_bezels      = bool(rec.paths.get("bezels")) and \
                            os.path.isdir(rec.paths.get("bezels", ""))
        a.has_rompath     = bool(d.rompath)
        a.warnings.extend(d.warnings)

        mod_path = rec.paths.get("module", "")
        mod_file = rec.paths.get("_module_file", "")

        if t == INI_TYPE_REAL:
            if not d.exe:           a.warnings.append("exe vacío — emulador no configurado")
            if not d.path:          a.warnings.append("path vacío — directorio no configurado")
            if not d.rompath:       a.warnings.append("rompath vacío — ROMs no configuradas")
            if not d.romextension:  a.warnings.append("romextension vacío")
            if not d.has_filters:   a.warnings.append("Falta sección [filters]")
            if not d.has_navigation: a.warnings.append("Falta sección [navigation]")
            if not a.has_xml:       a.warnings.append(f"Falta XML: {rec.paths['xml']}")
            if not a.has_media:     a.warnings.append(f"Falta carpeta media: {rec.paths['media']}")
            if not a.has_rl_settings: a.warnings.append("Sin settings de RocketLauncher")
            # Verificar módulo .ahk
            if not mod_file:
                a.warnings.append("Módulo .ahk no configurado en Emulators.ini")
            elif not mod_path:
                a.warnings.append(f"Módulo .ahk no encontrado en disco: {mod_file}")

        elif t == INI_TYPE_MMC:
            if not d.exe:  a.errors.append("exe vacío en entrada MainMenuChanger")
            if not d.path: a.errors.append("path vacío en entrada MainMenuChanger")
            if any("NAN" in w.upper() for w in a.warnings):
                a.warnings.append("Colores 0x000NAN en [wheel] (normal en Back.ini)")

        elif t == INI_TYPE_EXTERNAL:
            if not d.exe:  a.errors.append("exe vacío en app externa")
            if not d.path: a.warnings.append("path vacío en app externa")

    # -- Operaciones de gestión -----------------------------------------------

    def hide_in_app(self, name: str):
        """Oculta el sistema SOLO en la app. Cero archivos modificados en disco."""
        if name in self.records:
            self.records[name].hidden_in_app = True
            self.records[name].managed       = False
            self.save_registry()

    def restore_in_app(self, name: str):
        if name in self.records:
            self.records[name].hidden_in_app = False
            self.records[name].managed       = True
            self.save_registry()

    def delete_real(self, name: str, options: dict) -> list:
        """Borrado real de archivos con las opciones seleccionadas."""
        if name not in self.records:
            return ["Sistema no encontrado"]
        rec     = self.records[name]
        actions = []

        def _rm_file(path, label):
            if path and os.path.isfile(path):
                try:    os.remove(path);                      actions.append(f"✓ Borrado {label}: {path}")
                except Exception as e:                         actions.append(f"✗ Error {label}: {e}")

        def _rm_dir(path, label):
            if path and os.path.isdir(path):
                try:    shutil.rmtree(path, ignore_errors=True); actions.append(f"✓ Borrada {label}: {path}")
                except Exception as e:                            actions.append(f"✗ Error {label}: {e}")

        if options.get("delete_ini"):    _rm_file(rec.paths["ini"],  "INI")
        if options.get("delete_xml"):    _rm_dir(os.path.dirname(rec.paths["xml"]), "carpeta XML")
        if options.get("delete_media"):  _rm_dir(rec.paths["media"], "media")
        if options.get("delete_rl"):     _rm_dir(rec.paths["rocketlauncher_settings"], "RL Settings")
        if options.get("delete_bezels"):
            _rm_dir(rec.paths["bezels"], "Bezels")
            _rm_dir(rec.paths.get("fade", ""), "Fade")

        del self.records[name]
        self.save_registry()
        actions.append(f"Sistema '{name}' eliminado del registro")
        return actions

    def reaudit_one(self, name: str):
        """Re-parsea y re-audita un solo sistema sin reescanear todo."""
        if name not in self.records:
            return
        rec          = self.records[name]
        rec.ini_data = HyperSpinIniData(rec.paths["ini"]).parse()
        rec.type     = IniClassifier.classify(rec.ini_data)
        rec.audit    = IniAuditResult()
        self._fill_paths(rec)
        self._audit(rec)
        self.save_registry()


# ─── Worker de refresco en hilo ──────────────────────────────────────────────

class IniRefreshWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)

    def __init__(self, service: IniAuditService):
        super().__init__()
        self.service = service

    def run(self):
        def cb(done, total, name):
            self.progress.emit(int(done * 100 / max(total, 1)), name)
        stats = self.service.refresh(progress_callback=cb)
        self.finished.emit(stats)


class ImportWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)

    def __init__(self, service: IniAuditService):
        super().__init__()
        self.service = service

    def run(self):
        def cb(done, total, name):
            self.progress.emit(int(done * 100 / max(total, 1)), name)
        stats = self.service.import_from_rocketlauncher(progress_callback=cb)
        self.finished.emit(stats)


# ─── Diálogo eliminar sistema ────────────────────────────────────────────────

class DeleteSystemDialog(QDialog):
    MODE_HIDE = "hide"
    MODE_REAL = "real"

    def __init__(self, rec: SystemIniRecord, parent=None):
        super().__init__(parent)
        self.rec     = rec
        self.mode    = self.MODE_HIDE
        self.options = {}
        self.setWindowTitle(f"Eliminar sistema: {rec.name}")
        self.setMinimumWidth(540)
        self.setModal(True)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        hdr = QLabel(f"¿Cómo quieres eliminar <b>{self.rec.name}</b>?")
        hdr.setTextFormat(Qt.TextFormat.RichText)
        hdr.setStyleSheet("font-size:13px; color:#c8cdd8; padding:4px;")
        lay.addWidget(hdr)

        # Opción A — Ocultar (recomendada)
        gb_a = QGroupBox("✓  Recomendado — Eliminar solo de la app")
        gb_a.setStyleSheet(
            "QGroupBox{border:2px solid #1b5e20;border-radius:8px;"
            "color:#69f0ae;font-weight:700;padding:10px;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}")
        a_lay = QVBoxLayout(gb_a)
        desc_a = QLabel(
            "No se borra ningún archivo de disco.\n"
            "El sistema queda oculto en la app. Puedes restaurarlo en cualquier momento.")
        desc_a.setWordWrap(True)
        desc_a.setStyleSheet("color:#5a6278; font-size:12px;")
        btn_a = QPushButton("Ocultar solo en la app  (RECOMENDADO)")
        btn_a.setObjectName("btn_success")
        btn_a.clicked.connect(lambda: self._confirm(self.MODE_HIDE))
        a_lay.addWidget(desc_a)
        a_lay.addWidget(btn_a)

        # Opción B — Borrado real
        gb_b = QGroupBox("⚠  Avanzado — Borrado real de archivos")
        gb_b.setStyleSheet(
            "QGroupBox{border:2px solid #b71c1c;border-radius:8px;"
            "color:#ef9a9a;font-weight:700;padding:10px;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}")
        b_lay = QVBoxLayout(gb_b)

        warn = QLabel("⚠  ATENCIÓN: borra archivos del disco. Esta acción NO se puede deshacer.")
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "color:#ef9a9a; font-weight:700; font-size:12px; "
            "background:#2a0a0a; border-radius:4px; padding:6px;")

        # Resumen de lo que existe
        p = self.rec.paths
        exists = []
        if os.path.isfile(p.get("ini", "")):   exists.append("INI")
        if os.path.isfile(p.get("xml", "")):   exists.append("XML")
        if os.path.isdir(p.get("media", "")):  exists.append("Media")
        if os.path.isdir(p.get("rocketlauncher_settings", "")): exists.append("RL Settings")
        if os.path.isdir(p.get("bezels", "")): exists.append("Bezels")
        lbl_exists = QLabel("En disco: " + ("  ·  ".join(exists) if exists else "(nada encontrado)"))
        lbl_exists.setStyleSheet("color:#3a4560; font-size:11px;")

        self.chk_ini    = QCheckBox(f"Borrar INI  ({os.path.basename(p.get('ini',''))})")
        self.chk_xml    = QCheckBox("Borrar base de datos XML")
        self.chk_media  = QCheckBox("Borrar carpeta de media HyperSpin")
        self.chk_rl     = QCheckBox("Borrar settings de RocketLauncher")
        self.chk_bezels = QCheckBox("Borrar bezels y fade")
        for chk in [self.chk_ini, self.chk_xml, self.chk_media, self.chk_rl, self.chk_bezels]:
            chk.setStyleSheet("color:#8892a4; font-size:12px;")

        btn_b = QPushButton("Borrar archivos seleccionados")
        btn_b.setObjectName("btn_danger")
        btn_b.clicked.connect(lambda: self._confirm(self.MODE_REAL))

        b_lay.addWidget(warn)
        b_lay.addWidget(lbl_exists)
        for chk in [self.chk_ini, self.chk_xml, self.chk_media, self.chk_rl, self.chk_bezels]:
            b_lay.addWidget(chk)
        b_lay.addWidget(btn_b)

        btns = QDialogButtonBox(QDialogButtonBox.Cancel)
        btns.rejected.connect(self.reject)

        lay.addWidget(gb_a)
        lay.addWidget(gb_b)
        lay.addWidget(btns)

    def _confirm(self, mode: str):
        self.mode = mode
        if mode == self.MODE_REAL:
            if not any([self.chk_ini.isChecked(), self.chk_xml.isChecked(),
                        self.chk_media.isChecked(), self.chk_rl.isChecked(),
                        self.chk_bezels.isChecked()]):
                QMessageBox.warning(self, "Nada seleccionado",
                                    "Selecciona al menos un tipo de archivo a borrar.")
                return
            ok = QMessageBox.warning(
                self, "Confirmar borrado real",
                f"¿Seguro que quieres borrar archivos de disco?\n\n"
                f"Sistema: {self.rec.name}\n\nEsta acción NO se puede deshacer.",
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if ok != QMessageBox.Yes:
                return
        self.options = {
            "delete_ini":    self.chk_ini.isChecked(),
            "delete_xml":    self.chk_xml.isChecked(),
            "delete_media":  self.chk_media.isChecked(),
            "delete_rl":     self.chk_rl.isChecked(),
            "delete_bezels": self.chk_bezels.isChecked(),
        }
        self.accept()

# ─── Helpers XML ─────────────────────────────────────────────────────────────
#
# FORMATOS XML REALES OBSERVADOS:
#
# AAE.xml (juegos de sistema) — sin <header>, enabled="Yes"/"No", atributos index e image:
#   <game name="astdelux" index="true" image="a">
#     <description>astdelux</description>
#     <cloneof></cloneof>
#     <crc></crc>
#     <manufacturer></manufacturer>
#     <year></year>
#     <genre></genre>
#     <rating></rating>
#     <enabled>Yes</enabled>
#   </game>
#
# All.xml (sistemas del menú principal) — sin <header>, solo genre/year/manufacturer:
#   <game name="Capcom Play System III">
#     <genre>Arcades</genre>
#     <year>1996</year>
#     <manufacturer>Capcom</manufacturer>
#   </game>
#
# Main Menu.xml (rueda principal MMC) — entradas mínimas con atributo exe="true":
#   <game name="Arcades" exe="true"></game>
#   <game name="PC Games" enabled="1"/>
#
# NORMALIZACIÓN:
#   - enabled: "Yes"/"yes"/1/"1"/True → True  |  resto → False
#   - index/image: atributos opcionales, pueden ser "" o "true"/"a"
#   - Los XML de sistema (juegos) pueden o no tener <header>
#   - Los XML de menú (sistemas) no tienen <header>

def _normalize_enabled(val: str) -> bool:
    """Normaliza el campo enabled: Yes/yes/1/true → True, resto → False."""
    return str(val).strip().lower() in ("yes", "1", "true")


def _parse_xml_safe(xml_path: str):
    """
    Parser XML tolerante con BOM UTF-8 y comentarios HTML.
    Devuelve el root de ElementTree o None si falla.
    """
    if not xml_path or not os.path.isfile(xml_path):
        return None
    try:
        # Eliminar BOM si existe y leer como texto para tolerancia
        with open(xml_path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        # Eliminar comentarios que pueden romper el parser
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        root = ET.fromstring(content)
        return root
    except ET.ParseError as e:
        print(f"[WARN] Error parseando {xml_path}: {e}")
        return None
    except Exception as e:
        print(f"[WARN] Error leyendo {xml_path}: {e}")
        return None


def parse_xml_games(xml_path: str) -> list:
    """
    Lee un XML de base de datos de juegos de HyperSpin o RocketLauncherUI.
    Formato real: <game name="romname" index="" image=""> con subelementos.
    Tolera XMLs sin <header>, con enabled="Yes"/"No", con o sin todos los campos.
    """
    games = []
    root  = _parse_xml_safe(xml_path)
    if root is None:
        return games

    for game in root.findall("game"):
        name = game.get("name", "").strip()
        if not name:
            continue

        # enabled: atributo del tag O subelemento
        enabled_attr = game.get("enabled", "")
        enabled_text = game.findtext("enabled", "")
        enabled_raw  = enabled_attr if enabled_attr else enabled_text
        # Si no hay ni atributo ni subelemento, asumir habilitado
        enabled = _normalize_enabled(enabled_raw) if enabled_raw else True

        games.append({
            "name":         name,
            "description":  game.findtext("description", name).strip() or name,
            "cloneof":      game.findtext("cloneof", "").strip(),
            "crc":          game.findtext("crc", "").strip(),
            "manufacturer": game.findtext("manufacturer", "").strip(),
            "year":         game.findtext("year", "").strip(),
            "genre":        game.findtext("genre", "").strip(),
            "rating":       game.findtext("rating", "").strip(),
            "enabled":      enabled,
            # Atributos propios del XML de HyperSpin
            "index":        game.get("index", "").strip(),
            "image":        game.get("image", "").strip(),
            # Atributo especial de Main Menu.xml
            "exe":          game.get("exe", "").strip(),
        })
    return games


def parse_xml_systems(xml_path: str) -> list:
    """
    Lee All.xml / Main Menu.xml / Categories.xml.
    Formato: <game name="Sistema"> con genre/year/manufacturer como subelementos.
    También soporta el formato de Main Menu.xml con exe="true".
    """
    systems = []
    root    = _parse_xml_safe(xml_path)
    if root is None:
        return systems

    for game in root.findall("game"):
        name = game.get("name", "").strip()
        if not name:
            continue

        enabled_raw = game.get("enabled", game.findtext("enabled", "1"))
        systems.append({
            "name":         name,
            "description":  game.findtext("description", name).strip() or name,
            "genre":        game.findtext("genre", "").strip(),
            "year":         game.findtext("year", "").strip(),
            "manufacturer": game.findtext("manufacturer", "").strip(),
            "enabled":      _normalize_enabled(enabled_raw),
            # Atributos de Main Menu.xml
            "exe":          game.get("exe", "").strip(),
        })
    return systems


def save_xml_games(xml_path: str, games: list, menu_name: str = "menu",
                   preserve_order: bool = False):
    """
    Escribe lista de juegos al formato XML de HyperSpin.
    Respeta el formato real: sin <header>, atributos index e image,
    enabled como subelemento con valor "Yes"/"No".
    """
    os.makedirs(os.path.dirname(xml_path) if os.path.dirname(xml_path) else ".", exist_ok=True)

    root = ET.Element("menu")

    entries = list(games)
    if not preserve_order:
        sort_key = lambda g: (g.get("description") or g.get("name") or "").lower()
        entries.sort(key=sort_key)

    for g in entries:
        attrs = {"name": g.get("name", "")}
        # Solo añadir index/image si tienen valor
        if g.get("index"):  attrs["index"] = g["index"]
        if g.get("image"):  attrs["image"]  = g["image"]

        el = ET.SubElement(root, "game", **attrs)

        ET.SubElement(el, "description").text = g.get("description") or g.get("name", "")
        ET.SubElement(el, "cloneof").text     = g.get("cloneof", "")
        ET.SubElement(el, "crc").text         = g.get("crc", "")
        ET.SubElement(el, "manufacturer").text = g.get("manufacturer", "")
        ET.SubElement(el, "year").text         = g.get("year", "")
        ET.SubElement(el, "genre").text        = g.get("genre", "")
        ET.SubElement(el, "rating").text       = g.get("rating", "")

        # enabled: escribir "Yes"/"No" (formato HyperSpin real)
        enabled_val = g.get("enabled", True)
        if isinstance(enabled_val, bool):
            enabled_str = "Yes" if enabled_val else "No"
        elif str(enabled_val).lower() in ("yes", "1", "true"):
            enabled_str = "Yes"
        else:
            enabled_str = "No"
        ET.SubElement(el, "enabled").text = enabled_str

    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")

    _create_xml_backup(xml_path, max_backups=5)
    tmp_path = f"{xml_path}.tmp"
    try:
        tree.write(tmp_path, encoding="UTF-8", xml_declaration=True)
        os.replace(tmp_path, xml_path)
    finally:
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)


def _create_xml_backup(xml_path: str, max_backups: int = 5):
    """
    Crea backup rotativo antes de sobrescribir XML:
      - <Sistema>.xml.bak (última copia rápida)
      - <Sistema>.xml.bak.YYYYmmdd_HHMMSS (histórico)
    """
    if not xml_path or not os.path.isfile(xml_path):
        return

    bak_plain = f"{xml_path}.bak"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_stamped = f"{xml_path}.bak.{timestamp}"

    try:
        shutil.copy2(xml_path, bak_plain)
        shutil.copy2(xml_path, bak_stamped)
    except Exception as e:
        raise RuntimeError(f"No se pudo crear backup de XML: {e}") from e

    backup_dir = os.path.dirname(xml_path) or "."
    base_name = os.path.basename(xml_path)
    stamped = sorted(
        [
            os.path.join(backup_dir, n)
            for n in os.listdir(backup_dir)
            if n.startswith(base_name + ".bak.")
        ],
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )
    for old in stamped[max_backups:]:
        try:
            os.remove(old)
        except OSError:
            pass


def save_xml_systems(xml_path: str, systems: list, include_comments: bool = True):
    """
    Escribe All.xml / Categories.xml en el formato real observado.
    Agrupa por género si include_comments=True.
    """
    os.makedirs(os.path.dirname(xml_path) if os.path.dirname(xml_path) else ".", exist_ok=True)

    root = ET.Element("menu")

    if include_comments:
        # Agrupar por género para insertar comentarios
        from collections import defaultdict
        by_genre = defaultdict(list)
        no_genre  = []
        for s in systems:
            g = s.get("genre", "").strip()
            if g:
                by_genre[g].append(s)
            else:
                no_genre.append(s)

        for genre, items in sorted(by_genre.items()):
            comment = ET.Comment(f" ================= {genre.upper()} ================= ")
            root.append(comment)
            for s in sorted(items, key=lambda x: (x.get("year", ""), x.get("name", ""))):
                _append_system_element(root, s)

        for s in no_genre:
            _append_system_element(root, s)
    else:
        for s in sorted(systems, key=lambda x: x.get("name", "").lower()):
            _append_system_element(root, s)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    # Escribir con declaración UTF-8
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write("<?xml version='1.0' encoding='utf-8'?>\n")
        f.write(ET.tostring(root, encoding="unicode"))


def _append_system_element(parent: ET.Element, s: dict) -> ET.Element:
    """Añade un elemento <game> de sistema al XML padre."""
    attrs = {"name": s.get("name", "")}
    if s.get("exe"):     attrs["exe"]     = s["exe"]
    if not s.get("enabled", True):
        attrs["enabled"] = "0"
    el = ET.SubElement(parent, "game", **attrs)
    if s.get("genre"):        ET.SubElement(el, "genre").text        = s["genre"]
    if s.get("year"):         ET.SubElement(el, "year").text         = s["year"]
    if s.get("manufacturer"): ET.SubElement(el, "manufacturer").text = s["manufacturer"]
    return el


def xml_game_count(xml_path: str) -> int:
    """Devuelve el número de entradas <game> en un XML. -1 si no existe."""
    if not xml_path or not os.path.isfile(xml_path):
        return -1
    root = _parse_xml_safe(xml_path)
    if root is None:
        return -1
    return len(root.findall("game"))


# ─── Estructura de media de HyperSpin (basada en estructura real observada) ────
#
# HyperSpin/Media/<Sistema>/
#   Images/
#     Artwork1/, Artwork2/, Artwork3/, Artwork4/
#     Backgrounds/
#     Genre/Backgrounds/, Genre/Wheel/
#     Letters/
#     Other/, Particle/, Special/
#     Wheel/          ← PRINCIPAL — logos PNG de los juegos
#       Original/     ← subfolder de backups/originals
#   Sound/
#     Background Music/
#     System Exit/
#     System Start/
#     Wheel Sounds/
#   Themes/           ← archivos ZIP por juego
#   Video/            ← MP4/FLV/AVI por juego
#     Override Transitions/

# Estructura de media esperada: (ruta_relativa, requerida, descripción)
HS_MEDIA_STRUCTURE = [
    # Imágenes — Wheel es la más importante
    ("Images/Wheel",                True,  "Wheels (logos PNG)"),
    ("Images/Artwork1",             False, "Artwork 1"),
    ("Images/Artwork2",             False, "Artwork 2"),
    ("Images/Artwork3",             False, "Artwork 3"),
    ("Images/Artwork4",             False, "Artwork 4"),
    ("Images/Backgrounds",          False, "Fondos de pantalla"),
    ("Images/Genre/Wheel",          False, "Wheels de género"),
    ("Images/Genre/Backgrounds",    False, "Fondos de género"),
    ("Images/Letters",              False, "Letras del índice"),
    ("Images/Other",                False, "Imágenes otras"),
    ("Images/Particle",             False, "Partículas"),
    ("Images/Special",              False, "Imágenes especiales"),
    # Sonido
    ("Sound/Background Music",      False, "Música de fondo"),
    ("Sound/System Exit",           False, "Sonido salida"),
    ("Sound/System Start",          False, "Sonido inicio"),
    ("Sound/Wheel Sounds",          False, "Sonidos de rueda"),
    # Temas y vídeo
    ("Themes",                      True,  "Temas (ZIP)"),
    ("Video",                       True,  "Vídeos (MP4/FLV)"),
    ("Video/Override Transitions",  False, "Transiciones override"),
]

# Extensiones por tipo de media
WHEEL_EXTS  = {".png", ".jpg", ".jpeg"}
THEME_EXTS  = {".zip"}
VIDEO_EXTS  = {".mp4", ".flv", ".avi", ".mkv", ".m4v"}
SOUND_EXTS  = {".mp3", ".ogg", ".wav", ".flac"}
ARTWORK_EXTS = {".png", ".jpg", ".jpeg"}


def _count_files_in(folder: str, exts: set = None) -> int:
    """Cuenta archivos en una carpeta, opcionalmente filtrando por extensión."""
    if not os.path.isdir(folder):
        return -1
    try:
        files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
        if exts:
            files = [f for f in files if Path(f).suffix.lower() in exts]
        return len(files)
    except PermissionError:
        return -1


def _file_stems(folder: str, exts: set) -> set:
    """Devuelve el conjunto de stems (nombres sin ext) de archivos en la carpeta."""
    if not os.path.isdir(folder):
        return set()
    try:
        return {
            Path(f).stem.lower()
            for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
            and Path(f).suffix.lower() in exts
        }
    except PermissionError:
        return set()


# ─── Worker de auditoría ──────────────────────────────────────────────────────

class AuditWorker(QThread):
    progress = pyqtSignal(int, str)
    result   = pyqtSignal(dict)   # resultado completo con juegos + stats de media

    def __init__(self, system_name: str, config: dict):
        super().__init__()
        self.system_name = system_name
        self.config      = config

    def run(self):
        cfg      = self.config
        hs_dir   = cfg.get("hyperspin_dir", "")
        rl_dir   = cfg.get("rocketlauncher_dir", "")
        rlui_dir = cfg.get("rocketlauncherui_dir", "")
        sys_name = self.system_name

        self.progress.emit(5, "Cargando base de datos HyperSpin…")

        # ── Rutas de media HyperSpin ─────────────────────────────────────────
        hs_media  = os.path.join(hs_dir, "Media", sys_name)
        hs_wheel  = os.path.join(hs_media, "Images", "Wheel")
        hs_art1   = os.path.join(hs_media, "Images", "Artwork1")
        hs_art2   = os.path.join(hs_media, "Images", "Artwork2")
        hs_art3   = os.path.join(hs_media, "Images", "Artwork3")
        hs_art4   = os.path.join(hs_media, "Images", "Artwork4")
        hs_bg     = os.path.join(hs_media, "Images", "Backgrounds")
        hs_gwh    = os.path.join(hs_media, "Images", "Genre", "Wheel")
        hs_gbg    = os.path.join(hs_media, "Images", "Genre", "Backgrounds")
        hs_theme  = os.path.join(hs_media, "Themes")
        hs_video  = os.path.join(hs_media, "Video")
        hs_bgm    = os.path.join(hs_media, "Sound", "Background Music")
        hs_whs    = os.path.join(hs_media, "Sound", "Wheel Sounds")

        # ── Rutas de media RocketLauncher ────────────────────────────────────
        rl_bezel  = os.path.join(rl_dir, "Media", "Bezels", sys_name) if rl_dir else ""
        rl_fade   = os.path.join(rl_dir, "Media", "Fade",   sys_name) if rl_dir else ""

        # ── Base de datos HyperSpin ──────────────────────────────────────────
        hs_db_path = os.path.join(hs_dir, "Databases", sys_name, f"{sys_name}.xml")
        # RLUI puede estar en otra ruta
        rl_db_path = os.path.join(rlui_dir, "Databases", sys_name, f"{sys_name}.xml") \
                     if rlui_dir else ""

        self.progress.emit(15, "Indexando archivos de media…")

        # ── Índices de archivos existentes por tipo ──────────────────────────
        wheels, wheel_by_lower, wheel_by_norm = _file_stem_maps(hs_wheel, WHEEL_EXTS)
        themes  = _file_stems(hs_theme, THEME_EXTS)
        videos  = _file_stems(hs_video, VIDEO_EXTS)
        art1    = _file_stems(hs_art1,  ARTWORK_EXTS)
        art2    = _file_stems(hs_art2,  ARTWORK_EXTS)
        art3    = _file_stems(hs_art3,  ARTWORK_EXTS)
        art4    = _file_stems(hs_art4,  ARTWORK_EXTS)
        bgm     = _file_stems(hs_bgm,   SOUND_EXTS)
        whs     = _file_stems(hs_whs,   SOUND_EXTS)

        # Bezels por juego en RL
        bezel_games: set = set()
        if rl_bezel and os.path.isdir(rl_bezel):
            try:
                bezel_games = {
                    d.lower() for d in os.listdir(rl_bezel)
                    if os.path.isdir(os.path.join(rl_bezel, d))
                    and d.lower() != "_default"
                }
            except PermissionError:
                pass

        self.progress.emit(30, f"Parseando {os.path.basename(hs_db_path)}…")

        # ── Parsear base de datos de juegos ──────────────────────────────────
        hs_games  = parse_xml_games(hs_db_path)
        rl_games  = parse_xml_games(rl_db_path) if rl_db_path else []
        rl_names  = {g["name"].lower() for g in rl_games}

        # ── ROMs vs XML (según Emulators.ini del sistema) ───────────────────
        emu_ini = os.path.join(rl_dir, "Settings", sys_name, "Emulators.ini") if rl_dir else ""
        emu_data = parse_rl_emulators_ini(emu_ini) if emu_ini else {}
        rom_path_raw = emu_data.get("rom_path", "") if emu_data else ""
        rom_base = os.path.dirname(emu_ini) if emu_ini else ""
        rom_dir = _resolve_rl_path(rom_base, rom_path_raw) if rom_path_raw else ""

        default_emu = emu_data.get("default_emulator", "") if emu_data else ""
        emulators = emu_data.get("emulators", {}) if emu_data else {}
        rom_exts = set(ROM_EXTENSIONS)
        if default_emu and default_emu in emulators:
            parsed = _parse_rom_extensions(emulators[default_emu].get("rom_extension", ""))
            if parsed:
                rom_exts = parsed

        rom_stems = _file_stems(rom_dir, rom_exts) if rom_dir else set()
        xml_stems = {g["name"].lower() for g in hs_games}
        rom_only = sorted(rom_stems - xml_stems)
        xml_missing_rom = sorted(xml_stems - rom_stems)

        total = len(hs_games)
        rows  = []

        for i, g in enumerate(hs_games):
            if i % 10 == 0:
                pct = 30 + int(i * 60 / max(total, 1))
                self.progress.emit(pct, f"Auditando {i+1}/{total}: {g['name']}")

            name_l = g["name"].lower()
            name_norm = re.sub(r"[^a-z0-9]", "", name_l)
            wheel_exact_names = wheel_by_lower.get(name_l, set())
            wheel_case_issue = bool(wheel_exact_names) and g["name"] not in wheel_exact_names
            wheel_similar = set()
            if not wheel_exact_names:
                wheel_similar = wheel_by_norm.get(name_norm, set())
            wheel_naming_issue = wheel_case_issue or bool(wheel_similar)
            if wheel_case_issue:
                wheel_warning = f"Case distinto: {', '.join(sorted(wheel_exact_names))}"
            elif wheel_similar:
                wheel_warning = f"Nombre similar detectado: {', '.join(sorted(wheel_similar)[:3])}"
            else:
                wheel_warning = ""
            rows.append({
                # Datos del juego
                "name":         g["name"],
                "description":  g.get("description") or g["name"],
                "year":         g.get("year", ""),
                "manufacturer": g.get("manufacturer", ""),
                "genre":        g.get("genre", ""),
                "enabled":      g.get("enabled", True),
                "index":        g.get("index", ""),
                # Media HyperSpin
                "wheel":        name_l in wheels,
                "theme":        name_l in themes,
                "video":        name_l in videos,
                "artwork1":     name_l in art1,
                "artwork2":     name_l in art2,
                "artwork3":     name_l in art3,
                "artwork4":     name_l in art4,
                "bgm":          name_l in bgm,
                "wheel_sound":  name_l in whs,
                "wheel_naming_issue": wheel_naming_issue,
                "wheel_warning": wheel_warning,
                # Media RocketLauncher
                "bezel":        name_l in bezel_games,
                # Cross-check RLUI
                "in_rl_db":     name_l in rl_names,
                # ROMs vs XML
                "has_rom":      name_l in rom_stems,
            })

        self.progress.emit(95, "Calculando estadísticas de carpetas…")

        # ── Estadísticas de carpetas de media ────────────────────────────────
        media_stats = {}
        for rel_path, required, label in HS_MEDIA_STRUCTURE:
            abs_path = os.path.join(hs_media, rel_path.replace("/", os.sep))
            ext_map = {
                "Images/Wheel":    WHEEL_EXTS,
                "Themes":          THEME_EXTS,
                "Video":           VIDEO_EXTS,
                "Sound/Background Music": SOUND_EXTS,
                "Sound/Wheel Sounds":     SOUND_EXTS,
                "Sound/System Exit":      SOUND_EXTS,
                "Sound/System Start":     SOUND_EXTS,
            }
            exts   = ext_map.get(rel_path)
            count  = _count_files_in(abs_path, exts)
            exists = os.path.isdir(abs_path)
            media_stats[rel_path] = {
                "path":     abs_path,
                "exists":   exists,
                "count":    count,
                "required": required,
                "label":    label,
            }

        # Estadísticas de RL
        media_stats["RL/Bezels"] = {
            "path":     rl_bezel,
            "exists":   os.path.isdir(rl_bezel) if rl_bezel else False,
            "count":    _count_files_in(rl_bezel) if rl_bezel else -1,
            "required": False,
            "label":    "Bezels RocketLauncher",
        }
        media_stats["RL/Fade"] = {
            "path":     rl_fade,
            "exists":   os.path.isdir(rl_fade) if rl_fade else False,
            "count":    _count_files_in(rl_fade) if rl_fade else -1,
            "required": False,
            "label":    "Fade RocketLauncher",
        }

        self.progress.emit(100, "Auditoría completada.")

        # Resultado completo
        self.result.emit({
            "rows":        rows,
            "media_stats": media_stats,
            "hs_db_path":  hs_db_path,
            "rl_db_path":  rl_db_path,
            "hs_count":    len(hs_games),
            "rl_count":    len(rl_games),
            "system_name": sys_name,
            "rom_audit": {
                "rom_dir": rom_dir,
                "xml_without_rom": xml_missing_rom,
                "rom_without_xml": rom_only,
                "rom_exts": sorted(rom_exts),
            },
        })


# ─── Diálogo de informe de diferencias ───────────────────────────────────────

class DiffReportDialog(QDialog):
    def __init__(self, only_hs: list, only_rl: list, parent=None):
        super().__init__(parent)
        self.only_hs = only_hs
        self.only_rl = only_rl
        self.setWindowTitle("Informe de diferencias de bases de datos")
        self.setMinimumSize(700, 500)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14)

        header = QLabel(
            f"<b>Solo en HyperSpin</b> ({len(self.only_hs)} juegos — no se ejecutarán)  "
            f"&nbsp;&nbsp;|&nbsp;&nbsp;  "
            f"<b>Solo en RocketLauncher</b> ({len(self.only_rl)} juegos — no aparecerán)"
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setStyleSheet("color: #8892a4; font-size: 12px; padding: 4px;")
        lay.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel HS
        hs_w = QWidget()
        hs_l = QVBoxLayout(hs_w)
        hs_l.setContentsMargins(0, 0, 0, 0)
        hs_label = QLabel("Solo en HyperSpin XML")
        hs_label.setStyleSheet("color: #ffb74d; font-weight: 700; font-size: 12px; padding: 4px;")
        hs_list = QTextEdit()
        hs_list.setReadOnly(True)
        hs_list.setStyleSheet("background: #0a0d12; border: 1px solid #1e2330; color: #ffb74d; font-size: 11px;")
        hs_list.setText("\n".join(self.only_hs) if self.only_hs else "(ninguno)")
        hs_l.addWidget(hs_label)
        hs_l.addWidget(hs_list)

        # Panel RL
        rl_w = QWidget()
        rl_l = QVBoxLayout(rl_w)
        rl_l.setContentsMargins(0, 0, 0, 0)
        rl_label = QLabel("Solo en RocketLauncher DB")
        rl_label.setStyleSheet("color: #ef9a9a; font-weight: 700; font-size: 12px; padding: 4px;")
        rl_list = QTextEdit()
        rl_list.setReadOnly(True)
        rl_list.setStyleSheet("background: #0a0d12; border: 1px solid #1e2330; color: #ef9a9a; font-size: 11px;")
        rl_list.setText("\n".join(self.only_rl) if self.only_rl else "(ninguno)")
        rl_l.addWidget(rl_label)
        rl_l.addWidget(rl_list)

        splitter.addWidget(hs_w)
        splitter.addWidget(rl_w)
        lay.addWidget(splitter)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)

        # Botón exportar
        btn_exp = QPushButton("Exportar informe .txt")
        btn_exp.setObjectName("btn_primary")
        btn_exp.clicked.connect(self._export)
        btns.addButton(btn_exp, QDialogButtonBox.ActionRole)

        lay.addWidget(btns)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar informe", "diff_report.txt", "Texto (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write("=== SOLO EN HYPERSPIN ===\n")
            f.write("\n".join(self.only_hs) + "\n\n")
            f.write("=== SOLO EN ROCKETLAUNCHER ===\n")
            f.write("\n".join(self.only_rl) + "\n")
        QMessageBox.information(self, "Exportado", f"Informe guardado en:\n{path}")


# ─── Helper: eliminar entradas del INI de módulo (PCLauncher/TeknoParrot) ────

def _read_module_ini(ini_path: str) -> configparser.RawConfigParser:
    """Lee INI de módulo preservando claves no editadas."""
    cfg = configparser.RawConfigParser(strict=False)
    cfg.optionxform = str
    try:
        cfg.read(ini_path, encoding="utf-8")
    except Exception:
        cfg.read(ini_path, encoding="latin-1")
    return cfg


def _write_module_ini(ini_path: str, cfg: configparser.RawConfigParser) -> None:
    with open(ini_path, "w", encoding="utf-8") as f:
        cfg.write(f)


# ─── Diálogo de eliminación de juego ─────────────────────────────────────────

class RemoveGameDialog(QDialog):
    """
    Diálogo que pregunta al usuario el alcance de la eliminación:
      A) Solo de HyperSpin (XML de HS)
      B) De HyperSpin Y de RocketLauncherUI (XML de RLUI + INI del módulo si existe)
    """

    def __init__(self, game_names: list, sys_name: str,
                 config: dict, parent=None):
        super().__init__(parent)
        self.game_names  = game_names
        self.sys_name    = sys_name
        self.config      = config
        self.scope       = "hs_only"   # valor por defecto
        self.setWindowTitle("Eliminar juego(s)")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # ── Cabecera ──────────────────────────────────────────────────────────
        n = len(self.game_names)
        hdr = QLabel(
            f"<b>Eliminar {n} juego(s)</b> del sistema <b>{self.sys_name}</b>")
        hdr.setTextFormat(Qt.TextFormat.RichText)
        hdr.setStyleSheet("font-size:13px;color:#c8cdd8;padding:4px;")
        lay.addWidget(hdr)

        # Lista de nombres (máx 8 visibles)
        preview = "\n".join(f"  • {g}" for g in self.game_names[:8])
        if n > 8:
            preview += f"\n  … y {n-8} más"
        lbl_list = QLabel(preview)
        lbl_list.setStyleSheet(
            "color:#5a6278;font-size:11px;font-family:Consolas,monospace;"
            "background:#080a0f;border:1px solid #1e2330;border-radius:4px;"
            "padding:6px 10px;")
        lay.addWidget(lbl_list)

        # ── Opción A — Solo HyperSpin ─────────────────────────────────────────
        gb_hs = QGroupBox("📗  Solo de HyperSpin")
        gb_hs.setStyleSheet(
            "QGroupBox{border:2px solid #1b5e20;border-radius:8px;"
            "color:#69f0ae;font-weight:700;padding:10px;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}")
        hs_lay = QVBoxLayout(gb_hs)

        # Determinar qué archivos afecta
        hs_dir  = self.config.get("hyperspin_dir", "")
        hs_xml  = os.path.join(hs_dir, "Databases", self.sys_name,
                               f"{self.sys_name}.xml") if hs_dir else "(no configurado)"
        desc_a = QLabel(
            f"Elimina el juego solo del XML de HyperSpin.\n"
            f"El juego desaparece del frontend pero sigue en RLUI y en disco.\n\n"
            f"Archivo: {hs_xml}")
        desc_a.setWordWrap(True)
        desc_a.setStyleSheet("color:#5a6278;font-size:12px;")

        btn_a = QPushButton("Eliminar solo de HyperSpin")
        btn_a.setObjectName("btn_success")
        btn_a.clicked.connect(lambda: self._accept("hs_only"))

        hs_lay.addWidget(desc_a)
        hs_lay.addWidget(btn_a)

        # ── Opción B — HyperSpin + RLUI ───────────────────────────────────────
        gb_rl = QGroupBox("🗑  De HyperSpin Y de RocketLauncherUI")
        gb_rl.setStyleSheet(
            "QGroupBox{border:2px solid #b71c1c;border-radius:8px;"
            "color:#ef9a9a;font-weight:700;padding:10px;margin-top:8px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;}")
        rl_lay = QVBoxLayout(gb_rl)

        rlui_dir = self.config.get("rocketlauncherui_dir", "")
        rl_dir   = self.config.get("rocketlauncher_dir", "")

        rlui_xml = os.path.join(rlui_dir, "Databases", self.sys_name,
                                f"{self.sys_name}.xml") if rlui_dir else "(no configurado)"
        mod_ini  = os.path.join(rl_dir, "Settings", self.sys_name,
                                f"{self.sys_name}.ini") if rl_dir else "(no configurado)"
        mod_ini_exists = os.path.isfile(mod_ini) if rl_dir else False

        # Detectar si el sistema usa un módulo con INI propio
        mod_note = ""
        if mod_ini_exists:
            mod_note = f"\n  • Módulo INI ({os.path.basename(mod_ini)}): {mod_ini}"

        desc_b = QLabel(
            f"Elimina el juego de todos los sitios:\n"
            f"  • HyperSpin XML: {hs_xml}\n"
            f"  • RLUI XML: {rlui_xml}"
            + mod_note)
        desc_b.setWordWrap(True)
        desc_b.setStyleSheet("color:#8892a4;font-size:12px;")

        # Advertencia si RLUI no está configurado
        if not rlui_dir:
            warn = QLabel("⚠  RocketLauncherUI no configurado — solo se borrará de HyperSpin")
            warn.setStyleSheet(
                "color:#ffb74d;font-size:11px;font-weight:600;"
                "background:#2a1a00;border-radius:4px;padding:4px 8px;")
            warn.setWordWrap(True)
            rl_lay.addWidget(warn)

        btn_b = QPushButton("Eliminar de HyperSpin Y RocketLauncherUI")
        btn_b.setObjectName("btn_danger")
        btn_b.clicked.connect(lambda: self._accept("hs_and_rl"))

        rl_lay.addWidget(desc_b)
        rl_lay.addWidget(btn_b)

        # ── Botón cancelar ────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Cancel)
        btns.rejected.connect(self.reject)

        lay.addWidget(gb_hs)
        lay.addWidget(gb_rl)
        lay.addWidget(btns)

    def _accept(self, scope: str):
        self.scope = scope
        self.accept()


# ─── Módulo principal ─────────────────────────────────────────────────────────

class SystemManagerTab(TabModule):
    tab_title = "🗂 Sistemas"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config:  dict  = {}
        self._systems: list  = []   # lista completa de sistemas
        self._current_system: str = ""
        self._audit_rows: list = []
        self._main_widget: Optional[QWidget] = None
        self._audit_worker: Optional[AuditWorker] = None
        # INI Audit
        self._ini_service: Optional[IniAuditService] = None
        self._ini_worker:  Optional[IniRefreshWorker] = None
        self._import_worker: Optional[ImportWorker] = None
        # Juegos/XML
        self._games_data: list[dict] = []
        self._games_cols: list[str] = []
        self._games_dirty: bool = False
        self._games_sort_col: int = 1
        self._games_sort_order = Qt.SortOrder.AscendingOrder
        # INI de módulo por juego
        self._module_ini_path: str = ""
        self._module_type: str = ""
        self._module_fields: dict[str, QLineEdit] = {}
        self._module_fields_order: list[str] = []
        self._module_ini_dirty: bool = False
        self._updating_module_fields: bool = False

    # ── API TabModule ──────────────────────────────────────────────────────────

    def widget(self) -> QWidget:
        if self._main_widget is None:
            self._main_widget = self._build()
        return self._main_widget

    def load_data(self, config: dict):
        self._config = config
        self._current_system = (config or {}).get("last_selected_system", "")
        # Inicializar servicio INI con ruta al registry junto al config.json
        registry_path = os.path.join(
            os.path.dirname(config.get("hyperspin_dir", "") or "."),
            REGISTRY_FILENAME)
        self._ini_service = IniAuditService(config, registry_path)
        if self._main_widget:
            self._reload_systems()

    def save_data(self) -> dict:
        return {"last_selected_system": self._current_system}

    # ── Construcción UI ────────────────────────────────────────────────────────

    def _build(self) -> QWidget:
        root = QWidget()
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────────
        top = self._build_topbar()
        root_lay.addWidget(top)

        # ── Splitter principal ───────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #1e2330; }")

        # Panel izquierdo: lista de sistemas
        left = self._build_system_list()
        left.setMinimumWidth(220)
        left.setMaximumWidth(320)

        # Panel derecho: pestañas de detalle
        right = self._build_detail_tabs()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([260, 900])

        root_lay.addWidget(splitter, 1)
        return root

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background: #080a0f; border-bottom: 1px solid #1e2330;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(10)

        title = QLabel("Gestión de Sistemas")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #c8cdd8;")

        lbl_filter = QLabel("Género:")
        lbl_filter.setStyleSheet("color: #5a6278; font-size: 12px;")

        self.cmb_genre = QComboBox()
        self.cmb_genre.addItems(["Todos", "Arcade", "Console", "Computer",
                                  "Handheld", "Other"])
        self.cmb_genre.setFixedWidth(130)
        self.cmb_genre.currentTextChanged.connect(self._filter_systems)

        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("Buscar sistema…")
        self.inp_search.setFixedWidth(200)
        self.inp_search.textChanged.connect(self._filter_systems)

        btn_reload = QPushButton("↻ Recargar")
        btn_reload.setFixedWidth(100)
        btn_reload.clicked.connect(self._reload_systems)

        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #3a4560; font-size: 12px;")

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(lbl_filter)
        lay.addWidget(self.cmb_genre)
        lay.addWidget(self.inp_search)
        lay.addWidget(btn_reload)
        lay.addWidget(self.lbl_count)
        return bar

    def _build_system_list(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #0a0d12; border-right: 1px solid #1e2330;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QLabel("  Sistemas")
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(
            "background: #080a0f; color: #3a4560; font-size: 11px; "
            "font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; "
            "border-bottom: 1px solid #1e2330; padding: 0 12px;")

        self.system_list = QTreeWidget()
        self.system_list.setHeaderHidden(True)
        self.system_list.setStyleSheet("""
            QTreeWidget {
                background: #0a0d12;
                border: none;
                outline: none;
            }
            QTreeWidget::item {
                padding: 6px 12px;
                border-bottom: 1px solid #0d0f14;
                color: #6878a0;
                font-size: 12px;
            }
            QTreeWidget::item:hover {
                background: #12151c;
                color: #a0aabb;
            }
            QTreeWidget::item:selected {
                background: #0d3a5e;
                color: #4fc3f7;
            }
        """)
        self.system_list.currentItemChanged.connect(self._on_system_selected)
        self.system_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.system_list.customContextMenuRequested.connect(self._on_system_list_context_menu)

        lay.addWidget(hdr)
        lay.addWidget(self.system_list, 1)
        return w

    def _on_system_list_context_menu(self, pos):
        item = self.system_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self.system_list)
        menu.addAction("Eliminar sistema…").triggered.connect(self._delete_selected_system_from_main_list)
        menu.exec(self.system_list.viewport().mapToGlobal(pos))

    def _delete_selected_system_from_main_list(self):
        item = self.system_list.currentItem()
        if not item:
            return
        sys_data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        name = sys_data.get("name", "").strip()
        if not name:
            return

        if not self._ini_service:
            self._ini_service = IniAuditService(self._config or {})
        rec = self._ini_service.records.get(name) if self._ini_service else None
        if not rec and self._ini_service:
            rec = self._ini_service._build_record_for_system(name)

        if not rec:
            QMessageBox.warning(self.parent, "Error", f"No se pudo cargar el sistema '{name}'.")
            return

        dlg = DeleteSystemDialog(rec, parent=self.parent)
        if dlg.exec() != QDialog.Accepted:
            return

        if dlg.mode == DeleteSystemDialog.MODE_HIDE:
            self._ini_service.hide_in_app(name)
            msg = f"Sistema '{name}' ocultado en la app."
        else:
            actions = self._ini_service.delete_real(name, dlg.options)
            QMessageBox.information(
                self.parent, "Resultado del borrado",
                f"Acciones para '{name}':\n\n" + "\n".join(actions))
            msg = f"Sistema '{name}' eliminado."

        self._reload_systems()
        self._ini_populate_tree()
        if self.parent:
            self.parent.statusBar().showMessage(msg, 6000)

    def _build_detail_tabs(self) -> QTabWidget:
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setDocumentMode(True)

        self.detail_tabs.addTab(self._build_folders_tab(),    "📁 Carpetas")
        self.detail_tabs.addTab(self._build_dbdiff_tab(),     "⚖ Base de datos")
        self.detail_tabs.addTab(self._build_audit_tab(),      "🔍 Auditoría media")
        self._games_tab_index = self.detail_tabs.addTab(self._build_games_tab(), "🎮 Juegos")
        self.detail_tabs.addTab(self._build_ini_audit_tab(),  "⚙ INI Audit")
        # Nota: "📚 Main Menu" es ahora una pestaña independiente en la barra principal
        return self.detail_tabs

    # ── Tab: Carpetas ──────────────────────────────────────────────────────────

    def _build_folders_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(14)

        self.lbl_folders_title = QLabel("Selecciona un sistema para ver su estructura.")
        self.lbl_folders_title.setStyleSheet("color: #3a4560; font-size: 13px;")

        self.folders_tree = QTreeWidget()
        self.folders_tree.setHeaderLabels(["Carpeta / Archivo", "Archivos", "Estado"])
        self.folders_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.folders_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.folders_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.folders_tree.setAlternatingRowColors(False)
        self.folders_tree.setStyleSheet("""
            QTreeWidget {
                background: #0a0d12;
                border: 1px solid #1e2330;
                border-radius: 6px;
            }
            QTreeWidget::item { padding: 4px 8px; }
            QTreeWidget::item:selected { background: #0d3a5e; color: #4fc3f7; }
        """)

        lay.addWidget(self.lbl_folders_title)
        lay.addWidget(self.folders_tree, 1)
        return w

    # ── Tab: Diff de bases de datos ────────────────────────────────────────────

    def _build_dbdiff_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        # Info
        info = QLabel(
            "Compara la base de datos de HyperSpin con la de RocketLauncherUI "
            "para encontrar juegos que no se mostrarán o no podrán ejecutarse."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #5a6278; font-size: 12px;")

        # Botones
        btn_row = QHBoxLayout()
        self.btn_diff = QPushButton("⚖  Comparar bases de datos")
        self.btn_diff.setObjectName("btn_primary")
        self.btn_diff.setFixedWidth(220)
        self.btn_diff.clicked.connect(self._run_db_diff)

        self.btn_sync_to_rl = QPushButton("→ Sincronizar a RL")
        self.btn_sync_to_rl.setToolTip(
            "Copia las entradas que faltan en RocketLauncherUI desde HyperSpin")
        self.btn_sync_to_rl.clicked.connect(lambda: self._sync_db("hs_to_rl"))
        self.btn_sync_to_rl.setEnabled(False)

        self.btn_sync_to_hs = QPushButton("← Sincronizar a HS")
        self.btn_sync_to_hs.setToolTip(
            "Copia las entradas que faltan en HyperSpin desde RocketLauncherUI")
        self.btn_sync_to_hs.clicked.connect(lambda: self._sync_db("rl_to_hs"))
        self.btn_sync_to_hs.setEnabled(False)

        self.btn_report = QPushButton("📄 Ver informe")
        self.btn_report.clicked.connect(self._show_diff_report)
        self.btn_report.setEnabled(False)

        btn_row.addWidget(self.btn_diff)
        btn_row.addWidget(self.btn_sync_to_rl)
        btn_row.addWidget(self.btn_sync_to_hs)
        btn_row.addWidget(self.btn_report)
        btn_row.addStretch()

        # Tabla resumen
        self.diff_table = QTableWidget(0, 3)
        self.diff_table.setHorizontalHeaderLabels(["Juego", "HyperSpin", "RocketLauncher"])
        self.diff_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.diff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.diff_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.diff_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.diff_table.setStyleSheet(
            "QTableWidget { background: #0a0d12; border: 1px solid #1e2330; border-radius: 6px; }")

        self._diff_only_hs: list = []
        self._diff_only_rl: list = []

        lay.addWidget(info)
        lay.addLayout(btn_row)
        lay.addWidget(self.diff_table, 1)
        return w

    # ── Tab: Auditoría de media ────────────────────────────────────────────────

    def _build_audit_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        top_row = QHBoxLayout()
        self.btn_audit = QPushButton("▶  Auditar media")
        self.btn_audit.setObjectName("btn_primary")
        self.btn_audit.setFixedWidth(160)
        self.btn_audit.clicked.connect(self._run_audit)

        self.btn_copy_bezels = QPushButton("Copiar _Default → juegos sin bezel")
        self.btn_copy_bezels.setToolTip("Crea symlinks o carpetas vacías para juegos sin bezel personalizado")
        self.btn_copy_bezels.clicked.connect(self._copy_default_bezels)
        self.btn_copy_bezels.setEnabled(False)

        self.lbl_audit_stats = QLabel("")
        self.lbl_audit_stats.setStyleSheet("color: #3a4560; font-size: 12px;")
        self.lbl_rom_audit = QLabel("")
        self.lbl_rom_audit.setStyleSheet("color: #8fa2c4; font-size: 12px;")
        self.lbl_rom_audit.setWordWrap(True)

        self.audit_progress = QProgressBar()
        self.audit_progress.setFixedHeight(4)
        self.audit_progress.hide()

        top_row.addWidget(self.btn_audit)
        top_row.addWidget(self.btn_copy_bezels)
        top_row.addStretch()
        top_row.addWidget(self.lbl_audit_stats)

        # Filtros
        filter_row = QHBoxLayout()
        lbl_f = QLabel("Mostrar:")
        lbl_f.setStyleSheet("color: #5a6278; font-size: 12px;")
        self.chk_missing_wheel  = QCheckBox("Falta wheel")
        self.chk_missing_theme  = QCheckBox("Falta theme")
        self.chk_missing_video  = QCheckBox("Falta video")
        self.chk_missing_bezel  = QCheckBox("Falta bezel")
        for chk in [self.chk_missing_wheel, self.chk_missing_theme,
                    self.chk_missing_video, self.chk_missing_bezel]:
            chk.setStyleSheet("color: #6878a0; font-size: 12px;")
            chk.stateChanged.connect(self._filter_audit_table)
        btn_filter = QPushButton("Filtrar")
        btn_filter.setFixedWidth(70)
        btn_filter.clicked.connect(self._filter_audit_table)

        filter_row.addWidget(lbl_f)
        for chk in [self.chk_missing_wheel, self.chk_missing_theme,
                    self.chk_missing_video, self.chk_missing_bezel]:
            filter_row.addWidget(chk)
        filter_row.addWidget(btn_filter)
        filter_row.addStretch()

        # Tabla de auditoría
        COLS = ["Nombre", "Descripción", "Wheel", "Theme", "Video", "Bezel", "Activo"]
        self.audit_table = QTableWidget(0, len(COLS))
        self.audit_table.setHorizontalHeaderLabels(COLS)
        self.audit_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.audit_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(COLS)):
            self.audit_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.audit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.audit_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.audit_table.setAlternatingRowColors(False)
        self.audit_table.setStyleSheet(
            "QTableWidget { background: #0a0d12; border: 1px solid #1e2330; border-radius: 6px; }")

        lay.addLayout(top_row)
        lay.addWidget(self.audit_progress)
        lay.addWidget(self.lbl_rom_audit)
        lay.addLayout(filter_row)
        lay.addWidget(self.audit_table, 1)
        return w

    # ── Tab: Juegos ────────────────────────────────────────────────────────────

    def _build_games_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        top_row = QHBoxLayout()
        self.btn_load_games = QPushButton("⟳  Cargar XML")
        self.btn_load_games.clicked.connect(self._load_games)

        self.btn_add_game = QPushButton("+ Añadir juego")
        self.btn_add_game.setObjectName("btn_success")
        self.btn_add_game.clicked.connect(self._add_game_dialog)
        self.btn_add_game.setEnabled(False)

        self.btn_remove_game = QPushButton("− Eliminar")
        self.btn_remove_game.setObjectName("btn_danger")
        self.btn_remove_game.clicked.connect(self._remove_game)
        self.btn_remove_game.setEnabled(False)

        self.btn_toggle_enabled = QPushButton("⏻ Habilitar/Deshabilitar")
        self.btn_toggle_enabled.clicked.connect(self._toggle_selected_games_enabled)
        self.btn_toggle_enabled.setEnabled(False)

        self.btn_gen_from_roms = QPushButton("📂 Generar desde ROMs")
        self.btn_gen_from_roms.setObjectName("btn_primary")
        self.btn_gen_from_roms.clicked.connect(self._generate_from_roms)
        self.btn_gen_from_roms.setEnabled(False)

        self.btn_save_games = QPushButton("💾 Guardar XML")
        self.btn_save_games.clicked.connect(self._save_games_xml)
        self.btn_save_games.setEnabled(False)

        self.lbl_games_count = QLabel("")
        self.lbl_games_count.setStyleSheet("color: #3a4560; font-size: 12px;")

        for b in [self.btn_load_games, self.btn_add_game, self.btn_remove_game,
                  self.btn_toggle_enabled,
                  self.btn_gen_from_roms, self.btn_save_games]:
            top_row.addWidget(b)
        top_row.addStretch()
        top_row.addWidget(self.lbl_games_count)

        # Búsqueda
        search_row = QHBoxLayout()
        self.inp_game_search = QLineEdit()
        self.inp_game_search.setPlaceholderText("Buscar juego…")
        self.inp_game_search.textChanged.connect(self._filter_games_table)
        search_row.addWidget(QLabel("Buscar:"))
        search_row.addWidget(self.inp_game_search)
        search_row.addStretch()

        # Tabla de juegos
        GCOLS = ["name", "description", "year", "manufacturer", "genre", "rating", "enabled"]
        GCOLS_LABEL = ["ROM Name", "Descripción", "Año", "Fabricante", "Género", "Rating", "Activo"]
        self.games_table = QTableWidget(0, len(GCOLS))
        self.games_table.setHorizontalHeaderLabels(GCOLS_LABEL)
        self.games_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.games_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(GCOLS)):
            self.games_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.games_table.setSortingEnabled(True)
        self.games_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.games_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.games_table.itemChanged.connect(self._on_game_item_changed)
        self.games_table.itemSelectionChanged.connect(self._on_games_selection_changed)
        self.games_table.horizontalHeader().sortIndicatorChanged.connect(self._on_games_sort_changed)
        self.games_table.setStyleSheet(
            "QTableWidget { background: #0a0d12; border: 1px solid #1e2330; border-radius: 6px; }")

        lay.addLayout(top_row)
        lay.addLayout(search_row)
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        body.addWidget(self.games_table)
        body.addWidget(self._build_module_ini_editor())
        body.setSizes([900, 380])
        lay.addWidget(body, 1)

        self._games_cols = GCOLS
        return w

    def _build_module_ini_editor(self) -> QWidget:
        panel = QGroupBox("INI de módulo (juego seleccionado)")
        panel.setMinimumWidth(330)
        lay = QVBoxLayout(panel)
        lay.setSpacing(8)

        self.lbl_module_info = QLabel("Selecciona un juego para editar su INI de módulo.")
        self.lbl_module_info.setWordWrap(True)
        self.lbl_module_info.setStyleSheet("color:#5a6278;font-size:12px;")
        lay.addWidget(self.lbl_module_info)

        self.module_form = QFormLayout()
        self.module_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addLayout(self.module_form)

        self._module_field_rows: dict[str, tuple[QLabel, QLineEdit]] = {}
        for key in ["Application", "FadeTitle", "ExitMethod", "AppWaitExe",
                    "PostLaunch", "PostExit", "ShortName", "CommandLine", "GamePath"]:
            lbl = QLabel(f"{key}:")
            edit = QLineEdit()
            edit.textChanged.connect(self._on_module_ini_field_changed)
            self.module_form.addRow(lbl, edit)
            self._module_field_rows[key] = (lbl, edit)
            lbl.hide()
            edit.hide()

        btns = QHBoxLayout()
        self.btn_module_ini_save = QPushButton("Guardar INI módulo")
        self.btn_module_ini_save.setEnabled(False)
        self.btn_module_ini_save.clicked.connect(self._save_module_ini_for_selected_game)
        self.btn_module_ini_reload = QPushButton("Recargar INI")
        self.btn_module_ini_reload.setEnabled(False)
        self.btn_module_ini_reload.clicked.connect(self._load_module_ini_for_selected_game)
        btns.addWidget(self.btn_module_ini_save)
        btns.addWidget(self.btn_module_ini_reload)
        lay.addLayout(btns)
        lay.addStretch()
        return panel

    # ── Carga de sistemas ──────────────────────────────────────────────────────

    def _reload_systems(self):
        if not self._confirm_discard_pending_changes():
            return
        cfg    = self._config
        hs_dir = cfg.get("hyperspin_dir", "")
        self._systems = []

        if not hs_dir:
            return

        # Buscar All.xml o Main Menu.xml (con soporte MainMenuChanger)
        db_base = os.path.join(hs_dir, "Databases", "Main Menu")
        candidates = ["All.xml", "Main Menu.xml", "Categories.xml"]
        xml_path = None
        for c in candidates:
            p = os.path.join(db_base, c)
            if os.path.isfile(p):
                xml_path = p
                break

        if xml_path:
            self._systems = parse_xml_systems(xml_path)
        else:
            # Fallback: escanear carpetas de Databases/
            db_root = os.path.join(hs_dir, "Databases")
            if os.path.isdir(db_root):
                for d in sorted(os.listdir(db_root)):
                    if d.lower() == "main menu":
                        continue
                    if os.path.isdir(os.path.join(db_root, d)):
                        self._systems.append({"name": d, "description": d, "genre": "", "enabled": "1"})

        self._filter_systems()

    def _filter_systems(self):
        genre_filter  = self.cmb_genre.currentText()
        search_filter = self.inp_search.text().lower()
        hidden_systems = set()
        if self._ini_service:
            self._ini_service.load_registry()
            hidden_systems = {
                n for n, d in self._ini_service._saved_state.get("systems", {}).items()
                if d.get("hidden_in_app", False)
            }

        self.system_list.clear()
        count = 0
        for sys in self._systems:
            name  = sys.get("name", "")
            genre = sys.get("genre", "")
            if name in hidden_systems:
                continue
            if genre_filter != "Todos" and genre_filter.lower() not in genre.lower():
                continue
            if search_filter and search_filter not in name.lower():
                continue
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, sys)
            if sys.get("enabled", "1") != "1":
                item.setForeground(0, QBrush(C_DIM))
            self.system_list.addTopLevelItem(item)
            count += 1

        self.lbl_count.setText(f"{count} sistemas")
        self._restore_system_selection()

    def _restore_system_selection(self):
        desired = (self._current_system or "").lower()
        if self.system_list.topLevelItemCount() == 0:
            return

        candidate = None
        for i in range(self.system_list.topLevelItemCount()):
            item = self.system_list.topLevelItem(i)
            if desired and item.text(0).lower() == desired:
                candidate = item
                break
        if candidate is None:
            candidate = self.system_list.topLevelItem(0)

        if candidate:
            self.system_list.setCurrentItem(candidate)

    # ── Selección de sistema ───────────────────────────────────────────────────

    def _on_system_selected(self, current, previous):
        if not current:
            return
        if not self._confirm_discard_pending_changes():
            self.system_list.blockSignals(True)
            self.system_list.setCurrentItem(previous)
            self.system_list.blockSignals(False)
            return
        sys_data = current.data(0, Qt.ItemDataRole.UserRole)
        if not sys_data:
            return
        self._current_system = sys_data.get("name", "")
        self._load_system_details()

    def _load_system_details(self):
        sys_name = self._current_system
        if not sys_name:
            return
        cfg    = self._config
        hs_dir = cfg.get("hyperspin_dir", "")
        rl_dir = cfg.get("rocketlauncher_dir", "")

        self.lbl_folders_title.setText(f"Sistema: {sys_name}")
        self._populate_folders_tree(sys_name, hs_dir, rl_dir)
        # Habilitar botones que dependen de sistema seleccionado
        self.btn_diff.setEnabled(True)
        self.btn_audit.setEnabled(True)
        self.btn_add_game.setEnabled(True)
        self.btn_remove_game.setEnabled(True)
        self.btn_toggle_enabled.setEnabled(True)
        self.btn_gen_from_roms.setEnabled(True)
        self.btn_save_games.setEnabled(True)
        self._load_games()

    # ── Árbol de carpetas ──────────────────────────────────────────────────────

    def _populate_folders_tree(self, sys_name: str, hs_dir: str, rl_dir: str):
        self.folders_tree.clear()

        hs_media = os.path.join(hs_dir, "Media", sys_name)

        def _item(parent, label: str, path: str, required: bool = False,
                  ext_filter: set = None, note: str = ""):
            """Añade un ítem al árbol con estado y conteo de archivos."""
            exists = os.path.isdir(path) if path else False
            count  = _count_files_in(path, ext_filter) if exists else -1

            item = QTreeWidgetItem(parent)
            item.setText(0, label)
            item.setText(1, str(count) if count >= 0 else "—")
            item.setToolTip(0, path)

            if exists:
                if count == 0 and required:
                    item.setText(2, "Vacío")
                    item.setForeground(2, QBrush(C_WARN_FG))
                else:
                    item.setText(2, "✓" + (f" ({note})" if note else ""))
                    item.setForeground(2, QBrush(C_OK_FG))
            else:
                item.setText(2, "FALTA" if required else "—")
                item.setForeground(2, QBrush(C_ERR_FG if required else C_DIM))

            return item

        def _file_item(parent, label: str, path: str, required: bool = False):
            exists = os.path.isfile(path) if path else False
            item   = QTreeWidgetItem(parent)
            item.setText(0, label)
            item.setText(1, "")
            item.setText(2, "✓" if exists else ("FALTA" if required else "—"))
            item.setForeground(2, QBrush(C_OK_FG if exists else (C_ERR_FG if required else C_DIM)))
            item.setToolTip(0, path)
            return item

        def _group(label: str, color: str) -> QTreeWidgetItem:
            g = QTreeWidgetItem(self.folders_tree)
            g.setText(0, label)
            g.setForeground(0, QBrush(QColor(color)))
            g.setFlags(g.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            f = g.font(0); f.setBold(True); g.setFont(0, f)
            return g

        # ── HyperSpin Media ──────────────────────────────────────────────────
        grp_img = _group(f"📁  HyperSpin/Media/{sys_name}/Images", "#4fc3f7")
        _item(grp_img, "Wheel",                 os.path.join(hs_media, "Images", "Wheel"),       required=True, ext_filter=WHEEL_EXTS)
        art_node = _item(grp_img, "Artwork1-4", os.path.join(hs_media, "Images", "Artwork1"),    required=False)
        for n in range(2, 5):
            _item(grp_img, f"Artwork{n}",       os.path.join(hs_media, "Images", f"Artwork{n}"), required=False, ext_filter=ARTWORK_EXTS)
        _item(grp_img, "Backgrounds",           os.path.join(hs_media, "Images", "Backgrounds"), required=False, ext_filter=ARTWORK_EXTS)
        genre_node = QTreeWidgetItem(grp_img, ["Genre", "", ""])
        _item(genre_node, "Genre/Wheel",        os.path.join(hs_media, "Images", "Genre", "Wheel"),       required=False)
        _item(genre_node, "Genre/Backgrounds",  os.path.join(hs_media, "Images", "Genre", "Backgrounds"), required=False)
        _item(grp_img, "Letters",               os.path.join(hs_media, "Images", "Letters"),  required=False)
        _item(grp_img, "Other",                 os.path.join(hs_media, "Images", "Other"),    required=False)
        _item(grp_img, "Particle",              os.path.join(hs_media, "Images", "Particle"), required=False)
        _item(grp_img, "Special",               os.path.join(hs_media, "Images", "Special"),  required=False)
        grp_img.setExpanded(True)

        grp_snd = _group(f"🔊  HyperSpin/Media/{sys_name}/Sound", "#b39ddb")
        _item(grp_snd, "Background Music", os.path.join(hs_media, "Sound", "Background Music"), ext_filter=SOUND_EXTS)
        _item(grp_snd, "System Exit",      os.path.join(hs_media, "Sound", "System Exit"),      ext_filter=SOUND_EXTS)
        _item(grp_snd, "System Start",     os.path.join(hs_media, "Sound", "System Start"),     ext_filter=SOUND_EXTS)
        _item(grp_snd, "Wheel Sounds",     os.path.join(hs_media, "Sound", "Wheel Sounds"),     ext_filter=SOUND_EXTS)
        grp_snd.setExpanded(True)

        grp_thm = _group(f"🎨  HyperSpin/Media/{sys_name}/Themes + Video", "#ffb74d")
        _item(grp_thm, "Themes (ZIP)",               os.path.join(hs_media, "Themes"),       required=True,  ext_filter=THEME_EXTS)
        vid_node = _item(grp_thm, "Video",            os.path.join(hs_media, "Video"),        required=True,  ext_filter=VIDEO_EXTS)
        _item(grp_thm, "Video/Override Transitions",  os.path.join(hs_media, "Video", "Override Transitions"))
        grp_thm.setExpanded(True)

        # ── HyperSpin Settings + Databases ───────────────────────────────────
        grp_ini = _group(f"📄  HyperSpin/Settings + Databases", "#ffb74d")
        ini_path = os.path.join(hs_dir, "Settings", f"{sys_name}.ini")
        xml_path = os.path.join(hs_dir, "Databases", sys_name, f"{sys_name}.xml")
        _file_item(grp_ini, f"{sys_name}.ini",  ini_path,  required=True)
        _file_item(grp_ini, f"{sys_name}.xml",  xml_path,  required=True)

        # Contar juegos en el XML
        count_games = xml_game_count(xml_path)
        if count_games >= 0:
            lbl = QTreeWidgetItem(grp_ini)
            lbl.setText(0, "  └ juegos en XML")
            lbl.setText(1, str(count_games))
            lbl.setText(2, "")
            lbl.setForeground(1, QBrush(QColor("#4fc3f7")))
        grp_ini.setExpanded(True)

        # ── RocketLauncher Settings ───────────────────────────────────────────
        rl_settings      = os.path.join(rl_dir, "Settings", sys_name) if rl_dir else ""
        emulators_ini    = os.path.join(rl_settings, "Emulators.ini") if rl_settings else ""
        emu_info         = self._get_emulator_info(emulators_ini)
        rl_ini_info      = parse_rl_rocketlauncher_ini(
                               os.path.join(rl_settings, "RocketLauncher.ini") if rl_settings else "")

        grp_rl = _group(f"⚙  RocketLauncher/Settings/{sys_name}", "#69f0ae")
        for ini_file, req in [
            ("RocketLauncher.ini", True),
            ("Emulators.ini",      True),
            ("Bezel.ini",          False),
            ("Pause.ini",          False),
            ("Plugins.ini",        False),
            ("Games.ini",          False),
            ("Game Options.ini",   False),
        ]:
            ini_full = os.path.join(rl_settings, ini_file) if rl_settings else ""
            item = _file_item(grp_rl, ini_file, ini_full, required=req)

        # Sub-nodo: info del emulador leída de Emulators.ini
        if emu_info.get("emulator_name"):
            emu_node = QTreeWidgetItem(grp_rl)
            emu_node.setText(0, f"  ↳ Emulador: {emu_info['emulator_name']}")
            emu_node.setForeground(0, QBrush(QColor("#4fc3f7")))
            if emu_info.get("rom_path"):
                rp_node = QTreeWidgetItem(emu_node)
                rp_node.setText(0, f"    Rom_Path: {emu_info['rom_path']}")
                rp_node.setForeground(0, QBrush(C_DIM))
            if emu_info.get("emu_path"):
                ep_node = QTreeWidgetItem(emu_node)
                ep_node.setText(0, f"    Emu_Path: {emu_info['emu_path']}")
                ep_node.setForeground(0, QBrush(C_DIM))
            if emu_info.get("rom_extension"):
                re_node = QTreeWidgetItem(emu_node)
                re_node.setText(0, f"    Extensions: {emu_info['rom_extension']}")
                re_node.setForeground(0, QBrush(C_DIM))
            if emu_info.get("virtual"):
                virt_node = QTreeWidgetItem(emu_node)
                virt_node.setText(0, f"    Virtual_Emulator: true")
                virt_node.setForeground(0, QBrush(C_WARN_FG))

        # Sub-nodo: overrides de RocketLauncher.ini
        if rl_ini_info.get("overrides"):
            ovr_node = QTreeWidgetItem(grp_rl)
            ovr_node.setText(0, f"  ↳ Overrides activos ({len(rl_ini_info['overrides'])})")
            ovr_node.setForeground(0, QBrush(C_WARN_FG))
            for k, v in sorted(rl_ini_info["overrides"].items()):
                kv = QTreeWidgetItem(ovr_node)
                kv.setText(0, f"    {k} = {v}")
                kv.setForeground(0, QBrush(C_WARN_FG))

        grp_rl.setExpanded(True)

        # ── RocketLauncher Modules ─────────────────────────────────────────────
        grp_mod = _group("🔧  RocketLauncher/Modules", "#b39ddb")
        mf = emu_info.get("module_file", "")
        mfolder = emu_info.get("module_folder", "")

        if mf:
            mod_path = find_module_in_rl(rl_dir, mf, mfolder) if rl_dir else ""
            label    = f"{mfolder}/{mf}" if mfolder else mf
            mod_item = _file_item(grp_mod, label, mod_path, required=True)

            # Buscar también el .isd y el .ini de edición del módulo
            if mod_path:
                mod_dir  = os.path.dirname(mod_path)
                stem     = Path(mf).stem
                for ext, desc in [(".isd", "ISD config"), ("_edit.ini", "INI edición"),
                                   ("_edit.ahk", "AHK edición")]:
                    companion = os.path.join(mod_dir, stem + ext)
                    if os.path.isfile(companion):
                        comp_item = _file_item(grp_mod, f"  └ {stem}{ext}", companion)
                # Mostrar también otros archivos .ahk en la misma carpeta
                if os.path.isdir(mod_dir):
                    others = [f for f in os.listdir(mod_dir)
                              if f != mf and f.endswith(".ahk")]
                    if others:
                        oth = QTreeWidgetItem(grp_mod)
                        oth.setText(0, f"  + {len(others)} módulos relacionados")
                        oth.setForeground(0, QBrush(C_DIM))
        else:
            nomod = QTreeWidgetItem(grp_mod, ["(emulador no configurado)", "", "—"])
            nomod.setForeground(2, QBrush(C_DIM))
        grp_mod.setExpanded(True)

        # ── RocketLauncher Media — por sistema ────────────────────────────────
        grp_rl_media = _group(f"🎭  RocketLauncher/Media — {sys_name}", "#69f0ae")

        for rel_tpl, required, label in RL_MEDIA_STRUCTURE:
            rel = rel_tpl.replace("{sys}", sys_name)
            abs_path = os.path.join(rl_dir, "Media", rel.replace("/", os.sep)) if rl_dir else ""
            _item(grp_rl_media, rel, abs_path, required=required)

        # Contar bezels personalizados (carpetas que no son _Default)
        bezel_sys_dir = os.path.join(rl_dir, "Media", "Bezels", sys_name) if rl_dir else ""
        if os.path.isdir(bezel_sys_dir):
            custom_bezels = [d for d in os.listdir(bezel_sys_dir)
                             if os.path.isdir(os.path.join(bezel_sys_dir, d))
                             and d != "_Default"]
            if custom_bezels:
                cb_node = QTreeWidgetItem(grp_rl_media)
                cb_node.setText(0, f"  ↳ {len(custom_bezels)} bezels por juego")
                cb_node.setText(1, str(len(custom_bezels)))
                cb_node.setForeground(0, QBrush(C_OK_FG))

        grp_rl_media.setExpanded(True)

        # ── RLUI Database ─────────────────────────────────────────────────────
        rlui_dir = self._config.get("rocketlauncherui_dir", "")
        if rlui_dir:
            grp_rlui = _group(f"🗃  RocketLauncherUI/Databases/{sys_name}", "#b39ddb")
            rlui_xml = os.path.join(rlui_dir, "Databases", sys_name, f"{sys_name}.xml")
            _file_item(grp_rlui, f"{sys_name}.xml", rlui_xml, required=False)
            count_rlui = xml_game_count(rlui_xml)
            if count_rlui >= 0:
                lbl_rlui = QTreeWidgetItem(grp_rlui)
                lbl_rlui.setText(0, "  └ juegos en XML")
                lbl_rlui.setText(1, str(count_rlui))
                lbl_rlui.setForeground(1, QBrush(QColor("#b39ddb")))
            grp_rlui.setExpanded(True)

    def _get_module_name(self, emulators_ini: str) -> str:
        """
        Lee el Emulators.ini del sistema y devuelve el nombre del archivo .ahk
        del emulador por defecto (o el primero que encuentre).
        """
        data = parse_rl_emulators_ini(emulators_ini)
        default_emu = data.get("default_emulator", "")
        emulators   = data.get("emulators", {})

        # Primero intentar con el emulador por defecto
        if default_emu and default_emu in emulators:
            return emulators[default_emu].get("module_file", "")

        # Fallback: primer emulador disponible
        for emu_name, emu_data in emulators.items():
            mf = emu_data.get("module_file", "")
            if mf:
                return mf
        return ""

    def _get_emulator_info(self, emulators_ini: str) -> dict:
        """
        Devuelve información completa del emulador configurado para el sistema.
        """
        data = parse_rl_emulators_ini(emulators_ini)
        default_emu = data.get("default_emulator", "")
        emulators   = data.get("emulators", {})

        if default_emu and default_emu in emulators:
            info = dict(emulators[default_emu])
            info["emulator_name"] = default_emu
            info["default_emulator"] = default_emu
            info["rom_path"] = data.get("rom_path", "")
            return info

        # Fallback
        for name, emu in emulators.items():
            info = dict(emu)
            info["emulator_name"] = name
            info["default_emulator"] = default_emu or name
            info["rom_path"] = data.get("rom_path", "")
            return info

        return {
            "emulator_name": default_emu or "(no configurado)",
            "default_emulator": default_emu,
            "rom_path": data.get("rom_path", ""),
            "module_file": "", "module_folder": "",
            "emu_path": "", "rom_extension": "", "virtual": False,
        }

    # ── Diff de bases de datos ─────────────────────────────────────────────────

    def _run_db_diff(self):
        sys_name = self._current_system
        if not sys_name:
            return

        cfg       = self._config
        hs_dir    = cfg.get("hyperspin_dir", "")
        rlui_dir  = cfg.get("rocketlauncherui_dir", "")

        hs_xml  = os.path.join(hs_dir,   "Databases", sys_name, f"{sys_name}.xml")
        rl_xml  = os.path.join(rlui_dir, "Databases", sys_name, f"{sys_name}.xml")

        hs_games = {g["name"] for g in parse_xml_games(hs_xml)}
        rl_games = {g["name"] for g in parse_xml_games(rl_xml)}

        self._diff_only_hs = sorted(hs_games - rl_games)
        self._diff_only_rl = sorted(rl_games - hs_games)
        both               = sorted(hs_games & rl_games)

        self.diff_table.setRowCount(0)
        all_games = sorted(hs_games | rl_games)
        self.diff_table.setRowCount(len(all_games))

        for row, name in enumerate(all_games):
            in_hs = name in hs_games
            in_rl = name in rl_games

            self.diff_table.setItem(row, 0, QTableWidgetItem(name))
            hs_cell = QTableWidgetItem("✓" if in_hs else "✗")
            rl_cell = QTableWidgetItem("✓" if in_rl else "✗")

            if in_hs and in_rl:
                hs_cell.setForeground(QBrush(C_OK_FG))
                rl_cell.setForeground(QBrush(C_OK_FG))
            elif in_hs:
                hs_cell.setForeground(QBrush(C_OK_FG))
                rl_cell.setForeground(QBrush(C_ERR_FG))
                for c in range(3):
                    item = self.diff_table.item(row, c) or QTableWidgetItem("")
                    item.setBackground(QBrush(C_WARN))
                    self.diff_table.setItem(row, c, item)
            else:
                hs_cell.setForeground(QBrush(C_ERR_FG))
                rl_cell.setForeground(QBrush(C_OK_FG))
                for c in range(3):
                    item = self.diff_table.item(row, c) or QTableWidgetItem("")
                    item.setBackground(QBrush(C_ERR))
                    self.diff_table.setItem(row, c, item)

            hs_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rl_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.diff_table.setItem(row, 1, hs_cell)
            self.diff_table.setItem(row, 2, rl_cell)

        self.btn_sync_to_rl.setEnabled(bool(self._diff_only_hs))
        self.btn_sync_to_hs.setEnabled(bool(self._diff_only_rl))
        self.btn_report.setEnabled(True)

        if self.parent:
            self.parent.statusBar().showMessage(
                f"Diff: {len(self._diff_only_hs)} solo en HS, "
                f"{len(self._diff_only_rl)} solo en RL, "
                f"{len(both)} comunes.", 5000)

    def _sync_db(self, direction: str):
        """Copia entradas faltantes entre bases de datos."""
        sys_name = self._current_system
        if not sys_name:
            return
        cfg      = self._config
        hs_dir   = cfg.get("hyperspin_dir", "")
        rlui_dir = cfg.get("rocketlauncherui_dir", "")
        hs_xml   = os.path.join(hs_dir,   "Databases", sys_name, f"{sys_name}.xml")
        rl_xml   = os.path.join(rlui_dir, "Databases", sys_name, f"{sys_name}.xml")

        hs_games = parse_xml_games(hs_xml)
        rl_games = parse_xml_games(rl_xml)
        hs_names = {g["name"] for g in hs_games}
        rl_names = {g["name"] for g in rl_games}

        if direction == "hs_to_rl":
            missing = [g for g in hs_games if g["name"] not in rl_names]
            target_xml = rl_xml
            merged = rl_games + missing
            label  = f"RL ({len(missing)} juegos añadidos)"
        else:
            missing = [g for g in rl_games if g["name"] not in hs_names]
            target_xml = hs_xml
            merged = hs_games + missing
            label  = f"HyperSpin ({len(missing)} juegos añadidos)"

        if not missing:
            QMessageBox.information(self.parent, "Sin cambios", "No hay juegos que sincronizar.")
            return

        os.makedirs(os.path.dirname(target_xml), exist_ok=True)
        save_xml_games(target_xml, merged, menu_name=sys_name)
        QMessageBox.information(self.parent, "Sincronizado",
                                f"Base de datos de {label}\nArchivo: {target_xml}")
        self._run_db_diff()

    def _show_diff_report(self):
        dlg = DiffReportDialog(self._diff_only_hs, self._diff_only_rl, parent=self.parent)
        dlg.exec()

    # ── Auditoría de media ─────────────────────────────────────────────────────

    def _run_audit(self):
        sys_name = self._current_system
        if not sys_name:
            return

        self.audit_progress.show()
        self.audit_progress.setValue(0)
        self.btn_audit.setEnabled(False)
        self.audit_table.setRowCount(0)
        self.lbl_audit_stats.setText("Auditando…")
        self.lbl_rom_audit.setText("")

        self._audit_worker = AuditWorker(sys_name, self._config)
        self._audit_worker.progress.connect(self._on_audit_progress)
        self._audit_worker.result.connect(self._on_audit_result)
        self._audit_worker.start()

    def _on_audit_progress(self, pct: int, msg: str):
        self.audit_progress.setValue(pct)

    def _on_audit_result(self, result: dict):
        rows              = result.get("rows", [])
        rom_audit         = result.get("rom_audit", {})
        self._audit_rows  = rows
        self.audit_progress.hide()
        self.btn_audit.setEnabled(True)
        self._populate_audit_table(rows)
        self.btn_copy_bezels.setEnabled(True)

        xml_without_rom = rom_audit.get("xml_without_rom", [])
        rom_without_xml = rom_audit.get("rom_without_xml", [])
        rom_dir = rom_audit.get("rom_dir", "")
        if rom_dir:
            miss_sample = ", ".join(xml_without_rom[:6]) if xml_without_rom else "—"
            orphan_sample = ", ".join(rom_without_xml[:6]) if rom_without_xml else "—"
            self.lbl_rom_audit.setText(
                f"ROMs vs XML · XML sin ROM: {len(xml_without_rom)} · ROMs sin XML: {len(rom_without_xml)}"
                f"\nRuta ROM: {rom_dir}"
                f"\nEjemplos XML sin ROM: {miss_sample}"
                f"\nEjemplos ROM sin XML: {orphan_sample}"
            )
        else:
            self.lbl_rom_audit.setText("ROMs vs XML: sin Rom_Path válido en Emulators.ini.")

        # Mostrar stats de carpetas de media en la barra de estado
        hs_count = result.get("hs_count", 0)
        rl_count = result.get("rl_count", 0)
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ Auditoría completada — {hs_count} juegos HS  ·  {rl_count} en RLUI", 6000)

    def _populate_audit_table(self, rows: list):
        # ── Columnas ────────────────────────────────────────────────────────
        COLS     = ["ROM name", "Descripción", "Wheel", "Theme", "Video",
                    "Art1", "Art2", "Art3", "Art4", "BGM", "Wheel Snd", "Bezel",
                    "en RLUI", "ROM", "Wheel naming", "Activo"]
        COL_KEYS = ["name", "description", "wheel", "theme", "video",
                    "artwork1", "artwork2", "artwork3", "artwork4", "bgm", "wheel_sound",
                    "bezel", "in_rl_db", "has_rom", "wheel_naming_issue", "enabled"]

        self.audit_table.setColumnCount(len(COLS))
        self.audit_table.setHorizontalHeaderLabels(COLS)
        hdr = self.audit_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i in range(2, len(COLS)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.audit_table.setRowCount(len(rows))

        # ── Definición de tipos de columnas ─────────────────────────────────
        bool_keys = ["wheel", "theme", "video", "artwork1", "artwork2",
                     "artwork3", "artwork4", "bgm", "wheel_sound", "bezel",
                     "in_rl_db", "has_rom", "wheel_naming_issue", "enabled"]
        critical  = {"wheel", "theme", "video", "has_rom"}   # falta = fondo rojo

        # Fondos semitransparentes (BGR con alpha simulado via QColor darker)
        BG_OK   = QColor(0,  80,  30,  45)   # verde muy oscuro semitransparente
        BG_WARN = QColor(80, 55,  0,   45)   # ámbar muy oscuro semitransparente
        BG_ERR  = QColor(80, 0,   20,  55)   # rojo muy oscuro semitransparente

        counts = {k: 0 for k in bool_keys}

        for r, game in enumerate(rows):
            # ── Determinar color de fila según estado global ─────────────
            has_critical_missing = any(
                not game.get(k) for k in critical)
            has_warn_missing = any(
                not game.get(k)
                for k in ["artwork1", "artwork2", "bezel", "bgm"])
            naming_issue = bool(game.get("wheel_naming_issue"))

            for c, key in enumerate(COL_KEYS):
                val = game.get(key)

                if key in bool_keys:
                    # ── Celda booleana ────────────────────────────────────
                    if key == "wheel_naming_issue":
                        symbol = "⚠" if val else "✓"
                    else:
                        symbol = "✓" if val else "✗"

                    cell = QTableWidgetItem(symbol)
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    if key == "wheel_naming_issue":
                        if val:
                            # Problema de naming: fondo ámbar
                            cell.setForeground(QBrush(C_WARN_FG))
                            cell.setBackground(QBrush(BG_WARN))
                            cell.setToolTip(game.get("wheel_warning", "Nombre de wheel no exacto"))
                        else:
                            cell.setForeground(QBrush(C_OK_FG))
                            counts[key] += 1
                    elif val:
                        # Presente: texto verde + fondo verde muy tenue
                        cell.setForeground(QBrush(C_OK_FG))
                        cell.setBackground(QBrush(BG_OK))
                        counts[key] += 1
                    else:
                        # Faltante: color e intensidad según criticidad
                        if key in critical:
                            cell.setForeground(QBrush(C_ERR_FG))
                            cell.setBackground(QBrush(BG_ERR))
                        else:
                            cell.setForeground(QBrush(C_WARN_FG))
                            cell.setBackground(QBrush(BG_WARN))

                elif key == "name":
                    cell = QTableWidgetItem(str(val) if val is not None else "")
                    cell.setForeground(QBrush(QColor("#c8d4ec")))
                    cell.setFont(QFont("Consolas", 10))

                elif key == "description":
                    cell = QTableWidgetItem(str(val) if val is not None else "")
                    cell.setForeground(QBrush(QColor("#a0b0cc")))

                else:
                    cell = QTableWidgetItem(str(val) if val is not None else "")
                    cell.setForeground(QBrush(QColor("#8892a4")))

                self.audit_table.setItem(r, c, cell)

            # ── Colorear fila completa con alpha muy suave ────────────────
            # Solo las celdas de texto (col 0 y 1) toman el tinte de fila
            if has_critical_missing:
                row_bg = QColor(50, 0, 10, 20)
            elif has_warn_missing or naming_issue:
                row_bg = QColor(50, 35, 0, 15)
            else:
                row_bg = QColor(0, 0, 0, 0)

            for text_col in [0, 1]:
                item = self.audit_table.item(r, text_col)
                if item:
                    item.setBackground(QBrush(row_bg))

        # ── Estadísticas en header ────────────────────────────────────────
        total = len(rows)
        stats_parts = [f"Juegos: {total}"]
        for key, label in [
            ("wheel",            "Wheel"),
            ("theme",            "Theme"),
            ("video",            "Video"),
            ("bezel",            "Bezel"),
            ("in_rl_db",         "en RLUI"),
            ("has_rom",          "con ROM"),
            ("wheel_naming_issue", "Naming OK"),
        ]:
            cnt = counts[key]
            pct = int(cnt * 100 / max(total, 1))
            stats_parts.append(f"{label}: {cnt}/{total} ({pct}%)")
        self.lbl_audit_stats.setText("  ·  ".join(stats_parts))

    def _filter_audit_table(self):
        if not self._audit_rows:
            return
        show_mw = self.chk_missing_wheel.isChecked()
        show_mt = self.chk_missing_theme.isChecked()
        show_mv = self.chk_missing_video.isChecked()
        show_mb = self.chk_missing_bezel.isChecked()
        any_filter = show_mw or show_mt or show_mv or show_mb

        for r, game in enumerate(self._audit_rows):
            hide = False
            if any_filter:
                match = (
                    (show_mw and not game.get("wheel"))  or
                    (show_mt and not game.get("theme"))  or
                    (show_mv and not game.get("video"))  or
                    (show_mb and not game.get("bezel"))
                )
                hide = not match
            self.audit_table.setRowHidden(r, hide)

    def _copy_default_bezels(self):
        sys_name = self._current_system
        if not sys_name:
            return
        rl_dir     = self._config.get("rocketlauncher_dir", "")
        bezel_sys  = os.path.join(rl_dir, "Media", "Bezels", sys_name)
        default_dir = os.path.join(bezel_sys, "_Default")

        if not os.path.isdir(default_dir):
            QMessageBox.warning(self.parent, "Sin _Default",
                                f"No existe la carpeta _Default en:\n{bezel_sys}")
            return

        copied = 0
        for game in self._audit_rows:
            if not game.get("bezel"):
                dest = os.path.join(bezel_sys, game["name"])
                if not os.path.exists(dest):
                    try:
                        shutil.copytree(default_dir, dest)
                        copied += 1
                    except Exception as e:
                        print(f"[WARN] No se pudo copiar bezel para {game['name']}: {e}")

        QMessageBox.information(self.parent, "Bezeles copiados",
                                f"Se copiaron {copied} carpetas de bezel _Default.")
        self._run_audit()

    # ── Gestión de juegos ──────────────────────────────────────────────────────

    def _set_games_dirty(self, dirty: bool):
        self._games_dirty = dirty
        if hasattr(self, "detail_tabs") and hasattr(self, "_games_tab_index"):
            title = "🎮 Juegos*" if dirty else "🎮 Juegos"
            self.detail_tabs.setTabText(self._games_tab_index, title)

    def _confirm_discard_pending_changes(self) -> bool:
        if not self._games_dirty and not self._module_ini_dirty:
            return True
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Cambios sin guardar")
        msg.setText("Hay cambios pendientes.")
        msg.setInformativeText("¿Quieres guardarlos antes de continuar?")
        msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Save)
        res = msg.exec()
        if res == QMessageBox.Cancel:
            return False
        if res == QMessageBox.Save:
            if self._module_ini_dirty:
                self._save_module_ini_for_selected_game()
                if self._module_ini_dirty:
                    return False
            if self._games_dirty:
                self._save_games_xml()
                return not self._games_dirty
        return True

    def _sync_games_data_from_table(self):
        synced = []
        for r in range(self.games_table.rowCount()):
            row_data = {}
            for c, key in enumerate(self._games_cols):
                item = self.games_table.item(r, c)
                row_data[key] = item.text().strip() if item else ""
            synced.append(row_data)
        self._games_data = synced

    def _save_current_games_xml(self, show_status: bool = True) -> bool:
        sys_name = self._current_system
        if not sys_name:
            return False
        hs_dir = self._config.get("hyperspin_dir", "")
        if not hs_dir:
            return False
        xml_path = os.path.join(hs_dir, "Databases", sys_name, f"{sys_name}.xml")
        os.makedirs(os.path.dirname(xml_path), exist_ok=True)
        self._sync_games_data_from_table()
        try:
            save_xml_games(xml_path, self._games_data, preserve_order=True)
            self._set_games_dirty(False)
            if show_status and self.parent:
                self.parent.statusBar().showMessage(f"✓ XML guardado: {xml_path}", 5000)
            return True
        except Exception as e:
            QMessageBox.critical(self.parent, "Error al guardar XML", f"No se pudo guardar el XML.\n{e}")
            return False

    def _load_games(self):
        sys_name = self._current_system
        if not sys_name:
            return
        if not self._confirm_discard_pending_changes():
            return
        hs_dir  = self._config.get("hyperspin_dir", "")
        xml_path = os.path.join(hs_dir, "Databases", sys_name, f"{sys_name}.xml")
        self._games_data = parse_xml_games(xml_path)
        self._populate_games_table(self._games_data)
        self._set_games_dirty(False)
        self._module_ini_dirty = False
        self._load_module_ini_for_selected_game()

    def _populate_games_table(self, games: list):
        self.games_table.blockSignals(True)
        self.games_table.setSortingEnabled(False)
        self.games_table.setRowCount(len(games))
        for r, g in enumerate(games):
            for c, key in enumerate(self._games_cols):
                val = g.get(key, "")
                # enabled: normalizar a texto para mostrar en tabla
                if key == "enabled":
                    if isinstance(val, bool):
                        val = "Yes" if val else "No"
                    elif str(val).lower() in ("yes", "1", "true"):
                        val = "Yes"
                    else:
                        val = "No"
                item = QTableWidgetItem(str(val) if val is not None else "")
                self.games_table.setItem(r, c, item)
        self.games_table.setSortingEnabled(True)
        self.games_table.sortItems(self._games_sort_col, self._games_sort_order)
        self.games_table.blockSignals(False)
        self.lbl_games_count.setText(f"{len(games)} juegos")

    def _filter_games_table(self):
        text = self.inp_game_search.text().lower()
        for r in range(self.games_table.rowCount()):
            name_item = self.games_table.item(r, 0)
            desc_item = self.games_table.item(r, 1)
            visible = (
                (not text) or
                (name_item and text in name_item.text().lower()) or
                (desc_item and text in desc_item.text().lower())
            )
            self.games_table.setRowHidden(r, not visible)

    def _on_game_item_changed(self, item: QTableWidgetItem):
        self._set_games_dirty(True)

    def _on_games_sort_changed(self, col: int, order):
        self._games_sort_col = col
        self._games_sort_order = order

    def _on_games_selection_changed(self):
        self._load_module_ini_for_selected_game()

    def _get_selected_game_name(self) -> str:
        rows = sorted({i.row() for i in self.games_table.selectedIndexes()})
        if not rows:
            return ""
        item = self.games_table.item(rows[0], 0)
        return item.text().strip() if item else ""

    def _toggle_selected_games_enabled(self):
        rows = sorted({i.row() for i in self.games_table.selectedIndexes()})
        if not rows:
            return
        changed = 0
        self.games_table.blockSignals(True)
        enabled_col = self._games_cols.index("enabled")
        for r in rows:
            item = self.games_table.item(r, enabled_col)
            old_val = item.text().strip().lower() if item else "yes"
            new_val = "No" if old_val in ("yes", "1", "true") else "Yes"
            if item is None:
                item = QTableWidgetItem(new_val)
                self.games_table.setItem(r, enabled_col, item)
            else:
                item.setText(new_val)
            changed += 1
        self.games_table.blockSignals(False)
        self._sync_games_data_from_table()
        self._set_games_dirty(True)
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ {changed} juego(s) actualizado(s) (habilitar/deshabilitar)", 4000)

    def _resolve_module_ini_context(self) -> tuple[str, str]:
        sys_name = self._current_system
        rl_dir = self._config.get("rocketlauncher_dir", "")
        if not sys_name or not rl_dir:
            return "", ""
        ini_path = os.path.join(rl_dir, "Settings", sys_name, f"{sys_name}.ini")
        emu_ini = os.path.join(rl_dir, "Settings", sys_name, "Emulators.ini")
        emu_info = self._get_emulator_info(emu_ini)
        module_file = (emu_info.get("module_file") or "").lower()
        module_type = ""
        if "pclauncher" in module_file:
            module_type = "pclauncher"
        elif "teknoparrot" in module_file:
            module_type = "teknoparrot"
        return ini_path, module_type

    def _on_module_ini_field_changed(self):
        if getattr(self, "_updating_module_fields", False):
            return
        self._module_ini_dirty = True

    def _visible_module_keys(self, cfg: configparser.RawConfigParser, section: str, module_type: str) -> list[str]:
        if module_type == "pclauncher":
            keys = ["Application", "FadeTitle", "ExitMethod"]
            keys += [k for k in ["AppWaitExe", "PostLaunch", "PostExit"] if cfg.has_option(section, k)]
            return keys
        if module_type == "teknoparrot":
            return ["ShortName", "FadeTitle", "CommandLine", "GamePath"]
        return []

    def _load_module_ini_for_selected_game(self):
        game_name = self._get_selected_game_name()
        ini_path, module_type = self._resolve_module_ini_context()
        self._module_ini_path = ini_path
        self._module_type = module_type

        if self._module_ini_dirty:
            if not self._confirm_discard_pending_changes():
                return

        self.btn_module_ini_reload.setEnabled(bool(game_name and os.path.isfile(ini_path)))
        self.btn_module_ini_save.setEnabled(bool(game_name and os.path.isfile(ini_path)))
        self._module_ini_dirty = False

        for key, (lbl, edit) in self._module_field_rows.items():
            lbl.hide()
            edit.hide()
            edit.setText("")

        if not game_name:
            self.lbl_module_info.setText("Selecciona un juego para editar su INI de módulo.")
            return
        if not module_type or not os.path.isfile(ini_path):
            self.lbl_module_info.setText("Módulo no compatible o INI no encontrado (solo PCLauncher/TeknoParrot).")
            return

        cfg = _read_module_ini(ini_path)
        if not cfg.has_section(game_name):
            self.lbl_module_info.setText(f"El juego '{game_name}' no tiene sección en {os.path.basename(ini_path)}.")
            return

        self._updating_module_fields = True
        keys = self._visible_module_keys(cfg, game_name, module_type)
        self._module_fields_order = keys
        self.lbl_module_info.setText(
            f"Sistema: {self._current_system} · Juego: {game_name} · Módulo: {module_type}")
        for key in keys:
            lbl, edit = self._module_field_rows[key]
            lbl.show()
            edit.show()
            edit.setText(cfg.get(game_name, key, fallback=""))
        self._updating_module_fields = False

    def _save_module_ini_for_selected_game(self):
        game_name = self._get_selected_game_name()
        ini_path, module_type = self._resolve_module_ini_context()
        if not game_name or not ini_path or not os.path.isfile(ini_path) or not module_type:
            return
        cfg = _read_module_ini(ini_path)
        if not cfg.has_section(game_name):
            cfg.add_section(game_name)
        for key in self._module_fields_order:
            _, edit = self._module_field_rows[key]
            cfg.set(game_name, key, edit.text().strip())
        _write_module_ini(ini_path, cfg)
        self._module_ini_dirty = False
        if self.parent:
            self.parent.statusBar().showMessage(f"✓ INI guardado: {ini_path}", 5000)

    def _add_game_dialog(self):
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("Añadir juego")
        dlg.setMinimumWidth(480)
        lay = QGridLayout(dlg)
        lay.setSpacing(10)

        fields = {}
        for row_i, (label, key) in enumerate([
            ("ROM Name (sin ext.)", "name"),
            ("Descripción",         "description"),
            ("Año",                 "year"),
            ("Fabricante",          "manufacturer"),
            ("Género",              "genre"),
            ("Rating",              "rating"),
        ]):
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("color: #5a6278; font-size: 12px;")
            inp = QLineEdit()
            fields[key] = inp
            lay.addWidget(lbl, row_i, 0)
            lay.addWidget(inp, row_i, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns, len(fields), 0, 1, 2)

        if dlg.exec() == QDialog.Accepted:
            new_game = {k: fields[k].text().strip() for k in fields}
            if not new_game["name"]:
                return
            # Eliminar extensión si la pusieron
            new_game["name"] = Path(new_game["name"]).stem
            if not new_game["description"]:
                new_game["description"] = new_game["name"]
            self._games_data.append(new_game)
            self._games_data.sort(key=lambda x: x.get("description", "").lower())
            self._populate_games_table(self._games_data)
            self._set_games_dirty(True)

    def _remove_game(self):
        """
        Elimina el/los juegos seleccionados.
        Muestra diálogo para elegir:
          A) Solo de HyperSpin (solo de la lista en memoria, requiere Guardar XML)
          B) De HyperSpin Y de RocketLauncherUI (borra de ambas bases de datos en disco)
        """
        self._sync_games_data_from_table()
        rows  = sorted({i.row() for i in self.games_table.selectedIndexes()})
        if not rows:
            return

        # Juegos seleccionados (solo los que están dentro del rango)
        selected = [self._games_data[r] for r in rows if r < len(self._games_data)]
        if not selected:
            return

        names    = [g["name"] for g in selected]
        n        = len(names)
        preview  = "\n".join(f"  • {n}" for n in names[:12])
        if len(names) > 12:
            preview += f"\n  … y {len(names)-12} más"

        # ── Diálogo de opciones ───────────────────────────────────────────────
        dlg = RemoveGameDialog(
            game_names=names,
            sys_name=self._current_system,
            config=self._config,
            parent=self.parent,
        )
        if dlg.exec() != QDialog.Accepted:
            return

        scope = dlg.scope   # "hs_only" | "hs_and_rl"

        # ── Eliminar de la lista en memoria (siempre) ─────────────────────────
        for r in sorted(rows, reverse=True):
            if r < len(self._games_data):
                del self._games_data[r]
        self._populate_games_table(self._games_data)
        self._set_games_dirty(True)

        results = [f"Eliminado de HyperSpin (XML en memoria): {n} juego(s)"]

        # ── Guardar HyperSpin XML en disco inmediatamente ────────────────────
        sys_name = self._current_system
        hs_dir   = self._config.get("hyperspin_dir", "")
        hs_xml   = os.path.join(hs_dir, "Databases", sys_name, f"{sys_name}.xml")
        if hs_dir and sys_name:
            try:
                save_xml_games(hs_xml, self._games_data, preserve_order=True)
                self._set_games_dirty(False)
                results.append(f"✓ HyperSpin XML guardado: {hs_xml}")
            except Exception as e:
                results.append(f"✗ Error guardando HS XML: {e}")

        # ── Si se eligió también RLUI ─────────────────────────────────────────
        if scope == "hs_and_rl":
            rlui_dir  = self._config.get("rocketlauncherui_dir", "")
            rl_dir    = self._config.get("rocketlauncher_dir", "")
            name_set  = {g["name"].lower() for g in selected}

            # 1. RocketLauncherUI/Databases/<sistema>/<sistema>.xml
            if rlui_dir:
                rlui_xml = os.path.join(rlui_dir, "Databases", sys_name, f"{sys_name}.xml")
                if os.path.isfile(rlui_xml):
                    try:
                        rl_games = parse_xml_games(rlui_xml)
                        rl_after = [g for g in rl_games
                                    if g["name"].lower() not in name_set]
                        removed  = len(rl_games) - len(rl_after)
                        save_xml_games(rlui_xml, rl_after, preserve_order=True)
                        results.append(
                            f"✓ RLUI XML: {removed} juego(s) eliminado(s) — {rlui_xml}")
                    except Exception as e:
                        results.append(f"✗ Error en RLUI XML: {e}")
                else:
                    results.append(f"ℹ  RLUI XML no existe: {rlui_xml}")

            # 2. RocketLauncher/Settings/<sistema>/<sistema>.ini
            #    (INI del módulo PCLauncher / TeknoParrot)
            if rl_dir and sys_name:
                mod_ini = os.path.join(rl_dir, "Settings", sys_name, f"{sys_name}.ini")
                if os.path.isfile(mod_ini):
                    removed_mod = remove_games_from_module_ini(mod_ini, name_set)
                    if removed_mod > 0:
                        results.append(
                            f"✓ Módulo INI: {removed_mod} entrada(s) eliminada(s) — {mod_ini}")
                    else:
                        results.append(
                            f"ℹ  Módulo INI: ninguna entrada coincide — {mod_ini}")

        # ── Mostrar resumen ───────────────────────────────────────────────────
        msg = "\n".join(results)
        QMessageBox.information(
            self.parent, "Juego(s) eliminado(s)", msg)
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ {n} juego(s) eliminado(s) de {self._current_system}", 5000)

    def _generate_from_roms(self):
        folder = QFileDialog.getExistingDirectory(
            self.parent, "Seleccionar carpeta de ROMs", "")
        if not folder:
            return

        sys_name = self._current_system
        new_games = []
        for f in sorted(os.listdir(folder)):
            full = os.path.join(folder, f)
            if not os.path.isfile(full):
                continue
            ext = Path(f).suffix.lower()
            if ext not in ROM_EXTENSIONS:
                continue
            stem = Path(f).stem
            new_games.append({
                "name":         stem,
                "description":  stem,
                "year":         "",
                "manufacturer": "",
                "genre":        "",
                "rating":       "",
                "enabled":      "1",
            })

        if not new_games:
            QMessageBox.information(self.parent, "Sin ROMs",
                                    "No se encontraron archivos de ROM en la carpeta seleccionada.")
            return

        merge = QMessageBox.question(
            self.parent, "Fusionar o reemplazar",
            f"Se encontraron {len(new_games)} ROMs.\n"
            "¿Fusionar con la lista actual? (No = reemplazar)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if merge == QMessageBox.Cancel:
            return
        if merge == QMessageBox.No:
            self._games_data = new_games
        else:
            existing_names = {g["name"] for g in self._games_data}
            self._games_data += [g for g in new_games if g["name"] not in existing_names]
            self._games_data.sort(key=lambda x: x.get("description", "").lower())

        self._populate_games_table(self._games_data)
        self._set_games_dirty(True)
        QMessageBox.information(self.parent, "Completado",
                                f"Base de datos generada con {len(self._games_data)} juegos.")

    def _save_games_xml(self):
        sys_name = self._current_system
        if not sys_name:
            return
        self._save_current_games_xml(show_status=True)

    # ── Tab: Main Menu ────────────────────────────────────────────────────────

    def _build_mainmenu_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        self.lbl_mainmenu_status = QLabel("Configura HyperSpin para gestionar el Main Menu.")
        self.lbl_mainmenu_status.setWordWrap(True)
        self.lbl_mainmenu_status.setStyleSheet("color:#5a6278;font-size:12px;")

        btn_row = QHBoxLayout()
        self.btn_mm_refresh = QPushButton("⟳ Recargar")
        self.btn_mm_refresh.clicked.connect(self._mainmenu_refresh)
        self.btn_mm_to_mmc = QPushButton("Main Menu.xml → All/Categories")
        self.btn_mm_to_mmc.clicked.connect(self._mainmenu_convert_to_mmc)
        self.btn_mm_to_classic = QPushButton("All/Categories → Main Menu.xml")
        self.btn_mm_to_classic.clicked.connect(self._mainmenu_convert_to_classic)
        self.btn_mm_sync = QPushButton("Sincronizar categorías")
        self.btn_mm_sync.clicked.connect(self._mainmenu_sync_categories)
        for b in [self.btn_mm_refresh, self.btn_mm_to_mmc, self.btn_mm_to_classic, self.btn_mm_sync]:
            btn_row.addWidget(b)
        btn_row.addStretch()

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet("QSplitter::handle{background:#1e2330;}")

        cat_box = QGroupBox("Categorías (Categories.xml)")
        cat_lay = QVBoxLayout(cat_box)
        self.lst_mm_categories = QListWidget()
        cat_lay.addWidget(self.lst_mm_categories, 1)
        cat_btns = QHBoxLayout()
        btn_cat_add = QPushButton("+ Añadir")
        btn_cat_add.clicked.connect(self._mainmenu_add_category)
        btn_cat_del = QPushButton("− Quitar")
        btn_cat_del.setObjectName("btn_danger")
        btn_cat_del.clicked.connect(self._mainmenu_remove_category)
        btn_cat_up = QPushButton("↑")
        btn_cat_up.clicked.connect(lambda: self._mainmenu_reorder_categories(-1))
        btn_cat_down = QPushButton("↓")
        btn_cat_down.clicked.connect(lambda: self._mainmenu_reorder_categories(1))
        for b in [btn_cat_add, btn_cat_del, btn_cat_up, btn_cat_down]:
            cat_btns.addWidget(b)
        cat_btns.addStretch()
        cat_lay.addLayout(cat_btns)

        sw_box = QGroupBox("Sub-wheels detectados")
        sw_lay = QVBoxLayout(sw_box)
        self.lst_mm_subwheels = QListWidget()
        sw_lay.addWidget(self.lst_mm_subwheels, 1)

        split.addWidget(cat_box)
        split.addWidget(sw_box)
        split.setSizes([520, 420])

        lay.addWidget(self.lbl_mainmenu_status)
        lay.addLayout(btn_row)
        lay.addWidget(split, 1)
        QTimer.singleShot(0, self._mainmenu_refresh)
        return w

    def _mainmenu_get_info(self):
        hs_dir = self._config.get("hyperspin_dir", "")
        mmc_dir = self._config.get("mainmenuchanger_dir", "")
        return mainmenu_utils.detect_mainmenu(hs_dir, mmc_dir)

    def _mainmenu_refresh(self):
        if not hasattr(self, "lst_mm_categories"):
            return
        info = self._mainmenu_get_info()
        if not info.hs_dir or not os.path.isdir(info.hs_dir):
            self.lbl_mainmenu_status.setText("HyperSpin no configurado.")
            return

        self.lbl_mainmenu_status.setText(info.summary())
        self.lst_mm_categories.clear()
        self.lst_mm_subwheels.clear()

        if info.has_categories_xml:
            _, categories = mainmenu_utils.parse_hyperspin_xml(info.categories_xml)
            for cat in categories:
                self.lst_mm_categories.addItem(cat.get("name", ""))

        for sw in mainmenu_utils.list_subwheels(info):
            self.lst_mm_subwheels.addItem(f"{sw.get('name','')} ({sw.get('count',0)})")

    def _mainmenu_add_category(self):
        info = self._mainmenu_get_info()
        name, ok = QInputDialog.getText(self.parent, "Nueva categoría", "Nombre de la categoría:")
        if not ok or not name.strip():
            return
        name = name.strip()
        genre, _ = QInputDialog.getText(self.parent, "Nueva categoría", "Valor de género (opcional):")
        if mainmenu_utils.add_category(info, name, genre.strip()):
            self._mainmenu_refresh()
        else:
            QMessageBox.warning(self.parent, "Error", "No se pudo crear la categoría.")

    def _mainmenu_remove_category(self):
        current = self.lst_mm_categories.currentItem()
        if not current:
            return
        name = current.text()
        ok = QMessageBox.question(
            self.parent, "Quitar categoría",
            f"¿Eliminar categoría '{name}' de Categories.xml?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if ok != QMessageBox.Yes:
            return
        info = self._mainmenu_get_info()
        if mainmenu_utils.remove_category(info, name):
            self._mainmenu_refresh()
        else:
            QMessageBox.warning(self.parent, "Error", f"No se pudo eliminar '{name}'.")

    def _mainmenu_reorder_categories(self, delta: int):
        row = self.lst_mm_categories.currentRow()
        if row < 0:
            return
        target = row + delta
        if target < 0 or target >= self.lst_mm_categories.count():
            return
        item = self.lst_mm_categories.takeItem(row)
        self.lst_mm_categories.insertItem(target, item)
        self.lst_mm_categories.setCurrentRow(target)
        names = [self.lst_mm_categories.item(i).text() for i in range(self.lst_mm_categories.count())]
        info = self._mainmenu_get_info()
        if not mainmenu_utils.reorder_categories(info, names):
            QMessageBox.warning(self.parent, "Error", "No se pudo guardar el nuevo orden.")

    def _mainmenu_convert_to_mmc(self):
        info = self._mainmenu_get_info()
        result = mainmenu_utils.main_menu_xml_to_all_and_categories(info, overwrite=False)
        if result.success:
            QMessageBox.information(self.parent, "Conversión completada", result.summary())
            self._mainmenu_refresh()
        else:
            QMessageBox.warning(self.parent, "Error", result.error or "Falló la conversión.")

    def _mainmenu_convert_to_classic(self):
        info = self._mainmenu_get_info()
        result = mainmenu_utils.all_and_categories_to_main_menu_xml(info, use_all_xml=True, overwrite=True)
        if result.success:
            QMessageBox.information(self.parent, "Conversión completada", result.summary())
            self._mainmenu_refresh()
        else:
            QMessageBox.warning(self.parent, "Error", result.error or "Falló la conversión.")

    def _mainmenu_sync_categories(self):
        info = self._mainmenu_get_info()
        sync = mainmenu_utils.sync_categories_with_all(info)
        if "error" in sync:
            QMessageBox.warning(self.parent, "Error", sync["error"])
            return
        created = 0
        for genre in sync.get("genres_without_category", []):
            if mainmenu_utils.add_category(info, genre, genre):
                created += 1
        msg = (
            f"Categorías creadas: {created}\n"
            f"Categorías huérfanas: {len(sync.get('orphan_categories', []))}"
        )
        QMessageBox.information(self.parent, "Sincronización", msg)
        self._mainmenu_refresh()

    # ═══════════════════════════════════════════════════════════════════════════
    # INI AUDIT TAB — Auditor y clasificador de HyperSpin/Settings
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_ini_audit_tab(self) -> QWidget:
        """
        Pestaña de auditoría de INI de HyperSpin/Settings.
        Clasifica automáticamente cada .ini como:
          MAINMENUCHANGER_ENTRY | REAL_SYSTEM | EXTERNAL_APP | UNKNOWN
        """
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Barra de controles ───────────────────────────────────────────────
        ctrl = QWidget()
        ctrl.setFixedHeight(48)
        ctrl.setStyleSheet("background:#080a0f; border-bottom:1px solid #1e2330;")
        ctrl_lay = QHBoxLayout(ctrl)
        ctrl_lay.setContentsMargins(14, 0, 14, 0)
        ctrl_lay.setSpacing(10)

        self.btn_ini_refresh = QPushButton("⟳  REFRESH SYSTEMS")
        self.btn_ini_refresh.setObjectName("btn_primary")
        self.btn_ini_refresh.setFixedHeight(30)
        self.btn_ini_refresh.setMinimumWidth(175)
        self.btn_ini_refresh.setStyleSheet(
            "QPushButton#btn_primary{font-weight:800;font-size:12px;letter-spacing:0.5px;}")
        self.btn_ini_refresh.clicked.connect(self._ini_on_refresh)
        self.btn_ini_import = QPushButton("⤓ Importar RL Settings")
        self.btn_ini_import.setFixedHeight(30)
        self.btn_ini_import.clicked.connect(self._ini_on_import_rl)

        self.inp_ini_search = QLineEdit()
        self.inp_ini_search.setPlaceholderText("Buscar sistema…")
        self.inp_ini_search.setFixedWidth(180)
        self.inp_ini_search.textChanged.connect(self._ini_populate_tree)

        lbl_f = QLabel("Tipo:")
        lbl_f.setStyleSheet("color:#5a6278;font-size:12px;")
        self.cmb_ini_filter = QComboBox()
        self.cmb_ini_filter.addItems([
            "Todos", "Sistemas reales", "MainMenuChanger",
            "Apps externas", "Desconocidos", "Con errores", "Ocultos",
        ])
        self.cmb_ini_filter.setFixedWidth(150)
        self.cmb_ini_filter.currentIndexChanged.connect(self._ini_populate_tree)

        self.chk_ini_hidden = QCheckBox("Mostrar ocultos")
        self.chk_ini_hidden.setStyleSheet("color:#5a6278;font-size:12px;")
        self.chk_ini_hidden.toggled.connect(self._ini_populate_tree)

        ctrl_lay.addWidget(self.btn_ini_refresh)
        ctrl_lay.addWidget(self.btn_ini_import)
        ctrl_lay.addWidget(self.inp_ini_search)
        ctrl_lay.addWidget(lbl_f)
        ctrl_lay.addWidget(self.cmb_ini_filter)
        ctrl_lay.addWidget(self.chk_ini_hidden)
        ctrl_lay.addStretch()

        # ── Chips de resumen ─────────────────────────────────────────────────
        chips_bar = QWidget()
        chips_bar.setFixedHeight(36)
        chips_bar.setStyleSheet("background:#080a0f;border-bottom:1px solid #1e2330;")
        chips_lay = QHBoxLayout(chips_bar)
        chips_lay.setContentsMargins(14, 0, 14, 0)
        chips_lay.setSpacing(6)

        self._ini_chips = {}
        chip_defs = [
            ("total",          "Total",      "#8892a4"),
            (INI_TYPE_REAL,    "Reales",     "#69f0ae"),
            (INI_TYPE_MMC,     "MMC",        "#4fc3f7"),
            (INI_TYPE_EXTERNAL,"Apps",       "#ffb74d"),
            (INI_TYPE_UNKNOWN, "?",          "#ef9a9a"),
            ("errors",         "Errores",    "#ef9a9a"),
            ("warnings",       "Avisos",     "#ffb74d"),
        ]
        for key, label, color in chip_defs:
            lbl = QLabel(label + ":")
            lbl.setStyleSheet(f"color:#3a4560;font-size:11px;")
            chip = QLabel("—")
            chip.setStyleSheet(
                f"color:{color};background:#12151c;border:1px solid #1e2330;"
                f"border-radius:9px;padding:1px 8px;font-size:11px;font-weight:700;")
            self._ini_chips[key] = chip
            chips_lay.addWidget(lbl)
            chips_lay.addWidget(chip)
            if key != "warnings":
                sep = QFrame()
                sep.setFrameShape(QFrame.VLine)
                sep.setFixedWidth(1)
                sep.setStyleSheet("background:#1e2330;")
                chips_lay.addWidget(sep)
        chips_lay.addStretch()

        # ── Barra de progreso ────────────────────────────────────────────────
        self.ini_progress = QProgressBar()
        self.ini_progress.setFixedHeight(4)
        self.ini_progress.hide()
        self.ini_progress.setStyleSheet(
            "QProgressBar{background:#0d0f14;border:none;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0d4f7a,stop:1 #4fc3f7);}")

        # ── Splitter: árbol + detalle ────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle{background:#1e2330;}")

        # Árbol de sistemas
        self.ini_tree = QTreeWidget()
        self.ini_tree.setColumnCount(7)
        self.ini_tree.setHeaderLabels([
            "👁", "Sistema", "Tipo", "EXE", "Audit", "HL", "Filtro / Parámetros"
        ])
        hdr = self.ini_tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.ini_tree.setColumnWidth(1, 200)
        self.ini_tree.setColumnWidth(3, 160)
        self.ini_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ini_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ini_tree.itemClicked.connect(self._ini_on_item_clicked)
        self.ini_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ini_tree.customContextMenuRequested.connect(self._ini_context_menu)
        self.ini_tree.setStyleSheet("""
            QTreeWidget{background:#0a0d12;border:none;outline:none;font-size:12px;}
            QTreeWidget::item{padding:4px 6px;border-bottom:1px solid #0d0f14;}
            QTreeWidget::item:selected{background:#0d3a5e;color:#4fc3f7;}
            QTreeWidget::item:hover{background:#12151c;}
            QHeaderView::section{
                background:#080a0f;color:#3a4560;border:none;
                border-right:1px solid #1e2330;border-bottom:1px solid #1e2330;
                padding:4px 8px;font-weight:700;font-size:10px;
                letter-spacing:0.5px;text-transform:uppercase;}
        """)

        # Panel de detalle
        self.ini_detail = QTextEdit()
        self.ini_detail.setReadOnly(True)
        self.ini_detail.setMinimumWidth(300)
        self.ini_detail.setPlaceholderText(
            "Pulsa REFRESH SYSTEMS y selecciona un sistema para ver sus detalles.")
        self.ini_detail.setStyleSheet(
            "QTextEdit{background:#080a0f;border:none;border-left:1px solid #1e2330;"
            "color:#6878a0;font-family:Consolas,monospace;font-size:11px;padding:12px;}")

        splitter.addWidget(self.ini_tree)
        splitter.addWidget(self.ini_detail)
        splitter.setSizes([620, 320])

        # ── Barra de acciones ────────────────────────────────────────────────
        act_bar = QWidget()
        act_bar.setFixedHeight(40)
        act_bar.setStyleSheet("background:#080a0f;border-top:1px solid #1e2330;")
        act_lay = QHBoxLayout(act_bar)
        act_lay.setContentsMargins(12, 0, 12, 0)
        act_lay.setSpacing(8)

        self.btn_ini_hide    = QPushButton("Ocultar en app")
        self.btn_ini_restore = QPushButton("Restaurar")
        self.btn_ini_delete  = QPushButton("Eliminar…")
        self.btn_ini_reaudit = QPushButton("Re-auditar")
        self.btn_ini_delete.setObjectName("btn_danger")
        self.btn_ini_reaudit.setObjectName("btn_primary")

        for b in [self.btn_ini_hide, self.btn_ini_restore,
                  self.btn_ini_delete, self.btn_ini_reaudit]:
            b.setFixedHeight(26)
            b.setEnabled(False)
            act_lay.addWidget(b)

        self.btn_ini_hide.clicked.connect(self._ini_on_hide)
        self.btn_ini_restore.clicked.connect(self._ini_on_restore)
        self.btn_ini_delete.clicked.connect(self._ini_on_delete)
        self.btn_ini_reaudit.clicked.connect(self._ini_on_reaudit)

        self.lbl_ini_status = QLabel("Pulsa REFRESH SYSTEMS para escanear")
        self.lbl_ini_status.setStyleSheet("color:#3a4560;font-size:11px;")
        act_lay.addStretch()
        act_lay.addWidget(self.lbl_ini_status)

        lay.addWidget(ctrl)
        lay.addWidget(chips_bar)
        lay.addWidget(self.ini_progress)
        lay.addWidget(splitter, 1)
        lay.addWidget(act_bar)
        return w

    # ── Lógica de refresco INI ────────────────────────────────────────────────

    def _ini_on_refresh(self):
        if not self._ini_service:
            QMessageBox.warning(self.parent, "Sin configuración",
                                "Configura el directorio de HyperSpin primero.")
            return
        if not self._config.get("hyperspin_dir"):
            QMessageBox.warning(self.parent, "Sin configuración",
                                "El directorio de HyperSpin no está configurado.")
            return

        self.btn_ini_refresh.setEnabled(False)
        self.btn_ini_import.setEnabled(False)
        self.btn_ini_refresh.setText("Escaneando…")
        self.ini_progress.show()
        self.ini_progress.setValue(0)
        self.ini_tree.clear()
        self.lbl_ini_status.setText("Escaneando HyperSpin/Settings…")

        self._ini_worker = IniRefreshWorker(self._ini_service)
        self._ini_worker.progress.connect(
            lambda pct, name: (self.ini_progress.setValue(pct),
                               self.lbl_ini_status.setText(name)))
        self._ini_worker.finished.connect(self._ini_on_refresh_done)
        self._ini_worker.start()

    def _ini_on_refresh_done(self, stats: dict):
        self.btn_ini_refresh.setEnabled(True)
        self.btn_ini_import.setEnabled(True)
        self.btn_ini_refresh.setText("⟳  REFRESH SYSTEMS")
        self.ini_progress.hide()

        if "error" in stats:
            self.lbl_ini_status.setText(f"✗  {stats['error']}")
            return

        self._ini_update_chips(stats)
        self._ini_populate_tree()
        self.lbl_ini_status.setText(
            f"✓  {stats.get('total',0)} sistemas  ·  "
            f"{stats.get('with_errors',0)} errores  ·  "
            f"{stats.get('with_warnings',0)} avisos")
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ INI Audit: {stats.get('total',0)} sistemas clasificados", 5000)

    def _ini_on_import_rl(self):
        if not self._ini_service:
            QMessageBox.warning(self.parent, "Sin configuración", "Primero configura RocketLauncher.")
            return
        if not self._config.get("rocketlauncher_dir"):
            QMessageBox.warning(self.parent, "Sin configuración",
                                "El directorio de RocketLauncher no está configurado.")
            return

        self.btn_ini_refresh.setEnabled(False)
        self.btn_ini_import.setEnabled(False)
        self.btn_ini_import.setText("Importando…")
        self.ini_progress.show()
        self.ini_progress.setValue(0)
        self.lbl_ini_status.setText("Escaneando RocketLauncher/Settings…")

        self._import_worker = ImportWorker(self._ini_service)
        self._import_worker.progress.connect(
            lambda pct, name: (self.ini_progress.setValue(pct),
                               self.lbl_ini_status.setText(f"Importando: {name}")))
        self._import_worker.finished.connect(self._ini_on_import_done)
        self._import_worker.start()

    def _ini_on_import_done(self, stats: dict):
        self.btn_ini_refresh.setEnabled(True)
        self.btn_ini_import.setEnabled(True)
        self.btn_ini_import.setText("⤓ Importar RL Settings")
        self.ini_progress.hide()
        if "error" in stats:
            self.lbl_ini_status.setText(f"✗ {stats['error']}")
            return
        self._ini_update_chips(stats)
        self._ini_populate_tree()
        self.lbl_ini_status.setText(
            f"Importados {stats.get('imported', 0)} · "
            f"omitidos {stats.get('skipped', 0)} · "
            f"total {stats.get('total', 0)}")
        if self.parent:
            self.parent.statusBar().showMessage(
                f"Importación RL: {stats.get('imported', 0)} nuevos sistemas.", 6000)

    def _ini_update_chips(self, stats: dict):
        by_type = stats.get("by_type", {})
        mapping = {
            "total":          stats.get("total", 0),
            INI_TYPE_REAL:    by_type.get(INI_TYPE_REAL, 0),
            INI_TYPE_MMC:     by_type.get(INI_TYPE_MMC, 0),
            INI_TYPE_EXTERNAL:by_type.get(INI_TYPE_EXTERNAL, 0),
            INI_TYPE_UNKNOWN: by_type.get(INI_TYPE_UNKNOWN, 0),
            "errors":         stats.get("with_errors", 0),
            "warnings":       stats.get("with_warnings", 0),
        }
        for key, chip in self._ini_chips.items():
            chip.setText(str(mapping.get(key, 0)))

    # ── Árbol de sistemas INI ─────────────────────────────────────────────────

    def _ini_populate_tree(self):
        if not self._ini_service:
            return

        filter_idx_map = {
            0: "ALL", 1: INI_TYPE_REAL, 2: INI_TYPE_MMC,
            3: INI_TYPE_EXTERNAL, 4: INI_TYPE_UNKNOWN,
            5: "__ERRORS__", 6: "__HIDDEN__",
        }
        type_filter = filter_idx_map.get(self.cmb_ini_filter.currentIndex(), "ALL")
        search      = self.inp_ini_search.text().strip().lower()
        show_hidden = self.chk_ini_hidden.isChecked()

        # Filtrar registros
        filtered = []
        for rec in self._ini_service.records.values():
            if not show_hidden and rec.hidden_in_app:
                continue
            if type_filter == "__ERRORS__"  and not rec.audit.errors:   continue
            if type_filter == "__HIDDEN__"  and not rec.hidden_in_app:  continue
            if type_filter not in ("ALL", "__ERRORS__", "__HIDDEN__") \
               and rec.type != type_filter:                              continue
            if search and search not in rec.name.lower():               continue
            filtered.append(rec)

        filtered.sort(key=lambda r: (r.type, r.name.lower()))

        self.ini_tree.clear()

        # Agrupar por tipo
        groups: dict = {}
        for rec in filtered:
            groups.setdefault(rec.type, []).append(rec)

        for t in [INI_TYPE_MMC, INI_TYPE_REAL, INI_TYPE_EXTERNAL, INI_TYPE_UNKNOWN]:
            recs = groups.get(t, [])
            if not recs:
                continue
            bg, fg = INI_TYPE_COLORS.get(t, ("#1e2330", "#c8cdd8"))

            # Cabecera de grupo
            grp = QTreeWidgetItem(self.ini_tree)
            grp.setText(1, f"{INI_TYPE_LABELS.get(t, t)}  ({len(recs)})")
            grp.setForeground(1, QBrush(QColor(fg)))
            for col in range(7):
                grp.setBackground(col, QBrush(QColor(bg)))
            grp.setFlags(grp.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            f = grp.font(1)
            f.setBold(True)
            grp.setFont(1, f)

            for rec in recs:
                self._ini_add_item(grp, rec)
            grp.setExpanded(True)

    def _ini_add_item(self, parent: QTreeWidgetItem, rec: "SystemIniRecord"):
        d, a = rec.ini_data, rec.audit
        item = QTreeWidgetItem(parent)
        item.setData(0, Qt.ItemDataRole.UserRole, rec.name)

        # 👁 visibilidad
        item.setText(0, "👁" if not rec.hidden_in_app else "○")
        if rec.hidden_in_app:
            for col in range(7):
                item.setForeground(col, QBrush(QColor("#2a3a55")))

        # Nombre
        item.setText(1, rec.name)

        # Tipo
        _, fg = INI_TYPE_COLORS.get(rec.type, ("#1e2330", "#c8cdd8"))
        item.setText(2, INI_TYPE_LABELS.get(rec.type, rec.type))
        item.setForeground(2, QBrush(QColor(fg)))

        # EXE
        item.setText(3, d.exe or "(vacío)")
        if not d.exe:
            item.setForeground(3, QBrush(QColor("#3a4560")))

        # Audit status
        icons  = {"OK": "✓", "AVISO": "⚠", "ERROR": "✗"}
        colors = {"OK": "#69f0ae", "AVISO": "#ffb74d", "ERROR": "#ef9a9a"}
        status = a.status
        item.setText(4, icons.get(status, "?"))
        item.setForeground(4, QBrush(QColor(colors.get(status, "#8892a4"))))
        item.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)

        # HyperLaunch
        item.setText(5, "HL" if d.hyperlaunch else "—")
        item.setForeground(5, QBrush(QColor("#69f0ae" if d.hyperlaunch else "#3a4560")))
        item.setTextAlignment(5, Qt.AlignmentFlag.AlignCenter)

        # Filtro / parámetros
        if rec.type == INI_TYPE_MMC:
            txt = d.mmc_filter or d.parameters
            item.setForeground(6, QBrush(QColor("#4fc3f7")))
        elif rec.type == INI_TYPE_REAL:
            parts = []
            if d.romextension: parts.append(f"ext:{d.romextension}")
            if d.rompath:      parts.append("roms:✓")
            else:              parts.append("roms:✗")
            txt = "  ·  ".join(parts) if parts else ""
        else:
            txt = d.parameters
        item.setText(6, txt)

        # Tooltip
        tip = [
            f"INI:   {rec.paths.get('ini','')}",
            f"XML:   {rec.paths.get('xml','')}  {'[✓]' if a.has_xml else '[✗]'}",
            f"Media: {rec.paths.get('media','')}  {'[✓]' if a.has_media else '[✗]'}",
        ]
        if a.warnings: tip.append("Avisos: " + " | ".join(a.warnings[:3]))
        if a.errors:   tip.append("Errores: " + " | ".join(a.errors[:3]))
        item.setToolTip(1, "\n".join(tip))

    # ── Selección y detalle ───────────────────────────────────────────────────

    def _ini_on_item_clicked(self, item: QTreeWidgetItem, col: int):
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name or not self._ini_service:
            return
        rec = self._ini_service.records.get(name)
        if rec:
            self._ini_show_detail(rec)
            for b in [self.btn_ini_hide, self.btn_ini_restore,
                      self.btn_ini_delete, self.btn_ini_reaudit]:
                b.setEnabled(True)
            self.btn_ini_hide.setEnabled(not rec.hidden_in_app)
            self.btn_ini_restore.setEnabled(rec.hidden_in_app)

    def _ini_show_detail(self, rec: "SystemIniRecord"):
        d, a = rec.ini_data, rec.audit
        lines = [
            f"{'='*50}",
            f"  {rec.name}",
            f"  Tipo: {INI_TYPE_LABELS.get(rec.type, rec.type)}",
            f"{'='*50}",
            "",
            "=== [exe info] ===",
            f"  exe:           {d.exe or '(vacío)'}",
            f"  path:          {d.path or '(vacío)'}",
            f"  rompath:       {d.rompath or '(vacío)'}",
            f"  romextension:  {d.romextension or '(vacío)'}",
            f"  parameters:    {d.parameters or '(vacío)'}",
            f"  pcgame:        {d.pcgame}",
            f"  hyperlaunch:   {d.hyperlaunch}",
            f"  winstate:      {d.winstate}",
        ]

        if rec.type == INI_TYPE_MMC:
            lines.append(f"  mmc_filter:    {d.mmc_filter or '(sin filtro)'}")

        lines += [
            "",
            "=== Secciones detectadas ===",
        ]
        for s in d.sections:
            lines.append(f"  [{s}]")

        feats = []
        if d.has_wheel:       feats.append("wheel")
        if d.has_filters:     feats.append("filters")
        if d.has_navigation:  feats.append("navigation")
        if d.has_special_art: feats.append("special art")
        if d.has_game_text:   feats.append("game text")
        if d.has_themes:      feats.append("themes")
        lines.append(f"  Funciones: {', '.join(feats) or '(ninguna)'}")

        lines += [
            "",
            "=== Auditoría ===",
            f"  INI en disco:   {'✓' if a.has_ini else '✗'}",
            f"  XML database:   {'✓' if a.has_xml else '✗'}",
            f"  Media folder:   {'✓' if a.has_media else '✗'}",
            f"  RL Settings:    {'✓' if a.has_rl_settings else '✗'}",
            f"  Bezels:         {'✓' if a.has_bezels else '✗'}",
        ]
        if a.warnings:
            lines.append("")
            lines.append("  ⚠ AVISOS:")
            for w in a.warnings:
                lines.append(f"    · {w}")
        if a.errors:
            lines.append("")
            lines.append("  ✗ ERRORES:")
            for e in a.errors:
                lines.append(f"    · {e}")

        # Información del emulador (si es sistema real)
        if rec.type == INI_TYPE_REAL:
            rl_settings = rec.paths.get("rocketlauncher_settings", "")
            emulators_ini = os.path.join(rl_settings, "Emulators.ini") if rl_settings else ""
            emu_data = parse_rl_emulators_ini(emulators_ini)
            default_emu = emu_data.get("default_emulator", "")
            emulators   = emu_data.get("emulators", {})

            if default_emu or emulators:
                lines += ["", "=== Emulador (Emulators.ini) ==="]
                lines.append(f"  Default_Emulator: {default_emu or '(no configurado)'}")
                lines.append(f"  Rom_Path:         {emu_data.get('rom_path', '') or '(vacío)'}")
                if default_emu and default_emu in emulators:
                    emu = emulators[default_emu]
                    lines.append(f"  [{default_emu}]")
                    lines.append(f"    Emu_Path:      {emu.get('emu_path', '') or '(vacío)'}")
                    lines.append(f"    Rom_Extension: {emu.get('rom_extension', '') or '(vacío)'}")
                    lines.append(f"    Module:        {emu.get('module_raw', '') or '(vacío)'}")
                    if emu.get("virtual"):
                        lines.append(f"    Virtual_Emulator: true")

            # Módulo .ahk
            mod_path = rec.paths.get("module", "")
            mod_file = rec.paths.get("_module_file", "")
            lines += ["", "=== Módulo .ahk ==="]
            lines.append(f"  Archivo: {mod_file or '(no configurado)'}")
            if mod_path:
                lines.append(f"  Ruta:    {mod_path}  [✓]")
            elif mod_file:
                lines.append(f"  Ruta:    (no encontrado en Modules/)  [✗]")

            # Overrides de RocketLauncher.ini
            rl_ini_path = os.path.join(rl_settings, "RocketLauncher.ini") if rl_settings else ""
            rl_ini_data = parse_rl_rocketlauncher_ini(rl_ini_path)
            overrides   = rl_ini_data.get("overrides", {})
            if overrides:
                lines += ["", f"=== Overrides en RocketLauncher.ini ({len(overrides)}) ==="]
                for k, v in sorted(overrides.items()):
                    lines.append(f"  {k} = {v}")
            using_global = rl_ini_data.get("using_global", [])
            if using_global:
                lines.append(f"  ({len(using_global)} claves heredan use_global)")

        lines += [
            "",
            "=== Rutas ===",
        ]
        # Filtrar claves internas (empiezan con _)
        for k, v in rec.paths.items():
            if k.startswith("_"):
                continue
            if isinstance(v, str):
                exists = ""
                if v:
                    exists = " [✓]" if (os.path.isfile(v) or os.path.isdir(v)) else " [✗]"
                lines.append(f"  {k:<25} {v or '(no calculado)'}{exists}")

        lines += [
            "",
            "=== Estado en la app ===",
            f"  managed:       {rec.managed}",
            f"  hidden_in_app: {rec.hidden_in_app}",
        ]

        self.ini_detail.setPlainText("\n".join(lines))

    def _ini_get_selected_name(self) -> Optional[str]:
        items = self.ini_tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _ini_on_hide(self):
        name = self._ini_get_selected_name()
        if not name or not self._ini_service:
            return
        self._ini_service.hide_in_app(name)
        self.ini_detail.clear()
        self._ini_populate_tree()
        if self.parent:
            self.parent.statusBar().showMessage(
                f"Sistema '{name}' ocultado en la app (archivos intactos).", 5000)

    def _ini_on_restore(self):
        name = self._ini_get_selected_name()
        if not name or not self._ini_service:
            return
        self._ini_service.restore_in_app(name)
        self._ini_populate_tree()
        if self.parent:
            self.parent.statusBar().showMessage(f"Sistema '{name}' restaurado.", 4000)

    def _ini_on_delete(self):
        name = self._ini_get_selected_name()
        if not name or not self._ini_service:
            return
        rec = self._ini_service.records.get(name)
        if not rec:
            return
        dlg = DeleteSystemDialog(rec, parent=self.parent)
        if dlg.exec() != QDialog.Accepted:
            return
        if dlg.mode == DeleteSystemDialog.MODE_HIDE:
            self._ini_service.hide_in_app(name)
            msg = f"Sistema '{name}' ocultado en la app (sin borrar archivos)."
        else:
            actions = self._ini_service.delete_real(name, dlg.options)
            QMessageBox.information(
                self.parent, "Resultado del borrado",
                f"Acciones para '{name}':\n\n" + "\n".join(actions))
            msg = f"Sistema '{name}' eliminado."
        self.ini_detail.clear()
        self._ini_populate_tree()
        if self.parent:
            self.parent.statusBar().showMessage(msg, 6000)

    def _ini_on_reaudit(self):
        name = self._ini_get_selected_name()
        if not name or not self._ini_service:
            return
        self._ini_service.reaudit_one(name)
        rec = self._ini_service.records.get(name)
        if rec:
            self._ini_show_detail(rec)
        self._ini_populate_tree()
        if self.parent:
            self.parent.statusBar().showMessage(
                f"Re-auditado '{name}' → {rec.audit.status if rec else '?'}", 4000)

    def _ini_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        item = self.ini_tree.itemAt(pos)
        if not item:
            return
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name or not self._ini_service:
            return
        rec = self._ini_service.records.get(name)
        if not rec:
            return

        menu = QMenu(self.ini_tree)
        menu.setStyleSheet(
            "QMenu{background:#12151c;border:1px solid #1e2330;border-radius:6px;padding:4px;}"
            "QMenu::item{padding:6px 18px;color:#8892a4;border-radius:4px;}"
            "QMenu::item:selected{background:#1e2330;color:#e8ecf4;}")

        menu.addAction("Ver detalle").triggered.connect(
            lambda: self._ini_show_detail(rec))
        menu.addAction("Re-auditar").triggered.connect(self._ini_on_reaudit)
        menu.addSeparator()
        if rec.hidden_in_app:
            menu.addAction("Restaurar en app").triggered.connect(self._ini_on_restore)
        else:
            menu.addAction("Ocultar en app").triggered.connect(self._ini_on_hide)
        menu.addSeparator()
        menu.addAction("Eliminar…").triggered.connect(self._ini_on_delete)
        menu.exec(self.ini_tree.viewport().mapToGlobal(pos))
