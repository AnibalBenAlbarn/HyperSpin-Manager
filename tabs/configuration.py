"""
tabs/configuration.py
ConfigurationTab — Asistente de configuración inicial y pestaña de ajustes
"""

import os
import json
import shutil
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox,
    QFileDialog, QDialog, QDialogButtonBox,
    QScrollArea, QFrame, QSizePolicy, QSpacerItem,
    QStackedWidget, QProgressBar, QComboBox,
    QCheckBox, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

from core.rl_ini_helpers import read_rl_folder_from_rlui_ini

# Importar la clase base (se inyecta desde main)
try:
    from main import TabModule
except ImportError:
    # Fallback para imports directos
    class TabModule:
        tab_title = "Módulo"
        tab_icon  = ""
        def __init__(self, parent): self.parent = parent
        def widget(self): raise NotImplementedError
        def load_data(self, config): pass
        def save_data(self): return {}


# ─── Constantes de validación ─────────────────────────────────────────────────

HYPERSPIN_REQUIRED_DIRS    = ["Settings", "Media", "Databases"]
ROCKETLAUNCHER_REQUIRED    = ["Modules", "Settings", "Media"]


def _validate_hyperspin_dir(path: str) -> tuple[bool, str]:
    if not path or not os.path.isdir(path):
        return False, "La ruta no existe o no es un directorio."
    missing = [d for d in HYPERSPIN_REQUIRED_DIRS
               if not os.path.isdir(os.path.join(path, d))]
    if missing:
        return False, f"Faltan subcarpetas: {', '.join(missing)}"
    return True, "OK"


def _validate_rocketlauncher_dir(path: str) -> tuple[bool, str]:
    if not path or not os.path.isdir(path):
        return False, "La ruta no existe o no es un directorio."
    missing = [d for d in ROCKETLAUNCHER_REQUIRED
               if not os.path.isdir(os.path.join(path, d))]
    if missing:
        return False, f"Faltan subcarpetas: {', '.join(missing)}"
    return True, "OK"


def _validate_file(path: str, filename: str = "") -> tuple[bool, str]:
    if not path:
        return False, "Campo vacío."
    if not os.path.isfile(path):
        return False, "El archivo no existe."
    if filename and not path.lower().endswith(filename.lower()):
        return False, f"Se esperaba un archivo '{filename}'."
    return True, "OK"


def _detect_rocketlauncher_from_rlui(rlui_exe_or_ini: str, rlui_dir: str) -> dict:
    """
    Intenta detectar:
      - rocketlauncherui_dir
      - rocketlauncherui_exe
      - rocketlauncherui_ini
      - rocketlauncher_dir (desde RL_Folder)
    """
    result = {
        "rocketlauncherui_dir": "",
        "rocketlauncherui_exe": "",
        "rocketlauncherui_ini": "",
        "rocketlauncher_dir": "",
        "status": "",
    }

    hint = (rlui_exe_or_ini or "").strip()
    dir_hint = (rlui_dir or "").strip()

    if hint:
        if os.path.isdir(hint):
            dir_hint = hint
        elif os.path.isfile(hint):
            lower = hint.lower()
            if lower.endswith(".ini"):
                result["rocketlauncherui_ini"] = hint
                dir_hint = os.path.dirname(hint)
            else:
                result["rocketlauncherui_exe"] = hint
                dir_hint = os.path.dirname(hint)

    if dir_hint and os.path.isdir(dir_hint):
        result["rocketlauncherui_dir"] = dir_hint
        exe_candidate = os.path.join(dir_hint, "RocketLauncherUI.exe")
        ini_candidate = os.path.join(dir_hint, "RocketLauncherUI.ini")
        if not result["rocketlauncherui_exe"] and os.path.isfile(exe_candidate):
            result["rocketlauncherui_exe"] = exe_candidate
        if not result["rocketlauncherui_ini"] and os.path.isfile(ini_candidate):
            result["rocketlauncherui_ini"] = ini_candidate

    ini_path = result["rocketlauncherui_ini"]
    if ini_path:
        rl_folder = read_rl_folder_from_rlui_ini(ini_path)
        if rl_folder:
            if not os.path.isabs(rl_folder):
                rl_folder = os.path.abspath(os.path.join(os.path.dirname(ini_path), rl_folder))
            result["rocketlauncher_dir"] = rl_folder
            ok, _ = _validate_rocketlauncher_dir(rl_folder)
            if ok:
                result["status"] = "✓ RocketLauncher detectado desde RocketLauncherUI.ini"
            else:
                result["status"] = "⚠ RL_Folder detectado, pero la ruta no parece válida"
        else:
            result["status"] = "⚠ No se encontró RL_Folder en RocketLauncherUI.ini"
    elif result["rocketlauncherui_dir"]:
        result["status"] = "⚠ No se encontró RocketLauncherUI.ini para autodetección"

    return result


# ─── Hilo de escaneo ─────────────────────────────────────────────────────────

class ScanWorker(QThread):
    progress   = pyqtSignal(int, str)    # (porcentaje, mensaje)
    finished   = pyqtSignal(dict)        # resultado final

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def run(self):
        results = {
            "systems": [],
            "databases": [],
            "modules": [],
            "media_dirs": [],
        }
        steps = []

        hs_dir = self.config.get("hyperspin_dir", "")
        rl_dir = self.config.get("rocketlauncher_dir", "")

        # Paso 1: sistemas de HyperSpin (carpetas en Databases/)
        db_path = os.path.join(hs_dir, "Databases")
        if os.path.isdir(db_path):
            systems = [d for d in os.listdir(db_path)
                       if os.path.isdir(os.path.join(db_path, d))]
            results["systems"] = sorted(systems)
            steps.append((20, f"Encontrados {len(systems)} sistemas en HyperSpin"))
        self.progress.emit(20, steps[-1][1] if steps else "Escaneando HyperSpin…")

        # Paso 2: bases de datos XML
        xml_files = []
        if os.path.isdir(db_path):
            for root, _, files in os.walk(db_path):
                xml_files += [os.path.join(root, f) for f in files if f.endswith(".xml")]
        results["databases"] = xml_files
        self.progress.emit(40, f"Encontrados {len(xml_files)} archivos XML")

        # Paso 3: módulos RocketLauncher
        mod_path = os.path.join(rl_dir, "Modules")
        rl_modules = []
        if os.path.isdir(mod_path):
            for d in sorted(os.listdir(mod_path)):
                if os.path.isdir(os.path.join(mod_path, d)):
                    rl_modules.append(d)
        results["modules"] = rl_modules
        self.progress.emit(65, f"Encontrados {len(rl_modules)} módulos en RocketLauncher")

        # Paso 4: carpetas de media
        media_dirs = []
        for base, label in [(hs_dir, "HS"), (rl_dir, "RL")]:
            m = os.path.join(base, "Media")
            if os.path.isdir(m):
                media_dirs.append(f"[{label}] {m}")
        results["media_dirs"] = media_dirs
        self.progress.emit(90, "Finalizando escaneo…")

        self.progress.emit(100, "Escaneo completado.")
        self.finished.emit(results)



# ─── Asistente Modal (wizard de 4 pasos) ──────────────────────────────────────

class SetupWizard(QDialog):
    """Diálogo modal de configuración inicial paso a paso."""

    _AMBER  = "#f5a623"
    _CYAN   = "#00c9e8"
    _GREEN  = "#00e599"
    _RED    = "#ff4d6a"
    _DEEP   = "#05070b"
    _BASE   = "#090c12"
    _RAISED = "#0d1018"
    _BORDER = "#1a2035"
    _MID    = "#243050"
    _TXT_HI = "#e8edf8"
    _TXT_MD = "#8a9ab8"
    _TXT_LO = "#4a5878"
    _TXT_GH = "#2a3450"
    _MONO   = "'Consolas', 'Courier New', monospace"

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.setWindowTitle("Configuración inicial — HyperSpin Manager")
        self.setMinimumSize(720, 560)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(f"""
            QDialog {{ background: {self._DEEP}; }}
            QWidget {{ background: {self._DEEP}; color: {self._TXT_MD}; font-size: 13px; }}
        """)

        self._step   = 0
        self._steps  = [
            self._step_hyperspin,
            self._step_rocketlauncher,
            self._step_rlui,
            self._step_summary,
        ]
        self._step_titles = [
            "Directorio de HyperSpin",
            "Directorio de RocketLauncher",
            "RocketLauncherUI y ejecutables",
            "Resumen y confirmación",
        ]
        self._step_subtitles = [
            "Carpeta raíz con Settings/, Media/ y Databases/",
            "Motor principal — Modules/, Settings/ y Media/",
            "Interfaz gráfica de RocketLauncher",
            "Comprueba los datos antes de finalizar",
        ]

        self._build_ui()
        self._show_step(0)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(f"""
            background: {self._RAISED};
            border-bottom: 1px solid {self._BORDER};
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(32, 14, 32, 14)
        h_lay.setSpacing(4)

        self.lbl_step_title = QLabel()
        self.lbl_step_title.setStyleSheet(
            f"font-size: 16px; font-weight: 800; color: {self._TXT_HI}; "
            f"background: transparent; letter-spacing: -0.2px;")

        self.lbl_step_hint = QLabel()
        self.lbl_step_hint.setStyleSheet(
            f"font-size: 11px; color: {self._TXT_GH}; background: transparent; "
            f"font-family: {self._MONO};")

        h_lay.addWidget(self.lbl_step_title)
        h_lay.addWidget(self.lbl_step_hint)

        # ── Steps indicator ────────────────────────────────────────────────
        steps_bar = QWidget()
        steps_bar.setFixedHeight(40)
        steps_bar.setStyleSheet(
            f"background: {self._DEEP}; border-bottom: 1px solid {self._BORDER};")
        s_lay = QHBoxLayout(steps_bar)
        s_lay.setContentsMargins(24, 0, 24, 0)
        s_lay.setSpacing(0)

        self._step_dots = []
        labels = ["1  HyperSpin", "2  RocketLauncher", "3  Ejecutables", "4  Confirmar"]
        for i, lbl_txt in enumerate(labels):
            dot = QLabel(lbl_txt)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(
                f"font-size: 10px; font-weight: 700; color: {self._TXT_GH}; "
                f"padding: 0 8px; letter-spacing: 0.8px; background: transparent;")
            dot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._step_dots.append(dot)
            s_lay.addWidget(dot)
            if i < len(labels) - 1:
                arr = QLabel("›")
                arr.setStyleSheet(f"color: {self._BORDER}; font-size: 16px; background: transparent;")
                s_lay.addWidget(arr)

        # Progress bar below steps
        self._step_bar = QProgressBar()
        self._step_bar.setFixedHeight(2)
        self._step_bar.setTextVisible(False)
        self._step_bar.setStyleSheet(f"""
            QProgressBar {{ background: {self._BORDER}; border: none; }}
            QProgressBar::chunk {{ background: {self._AMBER}; }}
        """)

        # ── Content ──────────────────────────────────────────────────────────
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {self._BASE};")

        # ── Footer ──────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet(
            f"background: {self._RAISED}; border-top: 1px solid {self._BORDER};")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(24, 0, 24, 0)
        f_lay.setSpacing(8)

        self.lbl_footer_msg = QLabel("")
        self.lbl_footer_msg.setStyleSheet(
            f"color: {self._AMBER}; font-size: 11px; background: transparent;")

        self.btn_back   = QPushButton("← Anterior")
        self.btn_next   = QPushButton("Siguiente →")
        self.btn_finish = QPushButton("✓  Guardar configuración")
        self.btn_next.setObjectName("btn_primary")
        self.btn_finish.setObjectName("btn_success")
        self.btn_finish.hide()

        for b in [self.btn_back, self.btn_next]:
            b.setFixedWidth(130)
            b.setFixedHeight(34)
        self.btn_finish.setFixedWidth(200)
        self.btn_finish.setFixedHeight(34)

        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_finish.clicked.connect(self._on_finish)

        f_lay.addWidget(self.lbl_footer_msg, 1)
        f_lay.addWidget(self.btn_back)
        f_lay.addWidget(self.btn_next)
        f_lay.addWidget(self.btn_finish)

        root.addWidget(header)
        root.addWidget(steps_bar)
        root.addWidget(self._step_bar)
        root.addWidget(self.stack, 1)
        root.addWidget(footer)

    # ── Helpers de estilo del wizard ─────────────────────────────────────────

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {self._TXT_LO}; "
            f"background: transparent; letter-spacing: 0.3px;")
        return lbl

    def _desc_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet(
            f"font-size: 12px; color: {self._TXT_GH}; background: transparent; "
            f"line-height: 1.5; padding: 12px; border-left: 2px solid {self._BORDER}; "
            f"border-radius: 0 4px 4px 0;")
        return lbl

    def _tip_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size: 11px; color: {self._TXT_GH}; background: transparent; "
            f"font-family: {self._MONO}; padding: 8px 12px; "
            f"border: 1px solid {self._BORDER}; border-radius: 6px;")
        return lbl

    def _status_label(self) -> QLabel:
        lbl = QLabel("")
        lbl.setStyleSheet(
            f"font-size: 12px; background: transparent; font-family: {self._MONO};")
        return lbl

    def _make_input_row(self, inp: QLineEdit, is_dir: bool = True,
                         file_filter: str = "", hint: str = "") -> QHBoxLayout:
        inp.setStyleSheet(f"""
            QLineEdit {{
                background: #07090f;
                border: 1px solid {self._BORDER};
                border-radius: 7px;
                padding: 8px 12px;
                color: #c8d4ec;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {self._AMBER}; color: {self._TXT_HI}; }}
        """)
        if hint:
            inp.setPlaceholderText(hint)
        btn = QPushButton("…")
        btn.setFixedWidth(36)
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._RAISED};
                border: 1px solid {self._BORDER};
                border-radius: 7px;
                color: {self._TXT_LO};
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #111520; color: {self._TXT_MD}; border-color: {self._MID}; }}
        """)
        if is_dir:
            btn.clicked.connect(lambda: self._browse_dir(inp))
        else:
            btn.clicked.connect(lambda: self._browse_file(inp, file_filter))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(inp)
        row.addWidget(btn)
        return row

    # ── Pasos ─────────────────────────────────────────────────────────────────

    def _step_hyperspin(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {self._BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 24)
        lay.setSpacing(16)

        lay.addWidget(self._desc_label(
            "Selecciona el directorio raíz de HyperSpin.<br>"
            "Debe contener las carpetas <b style='color:#f5a623'>Settings</b>, "
            "<b style='color:#f5a623'>Media</b> y "
            "<b style='color:#f5a623'>Databases</b>."))

        lay.addWidget(self._field_label("Directorio de HyperSpin *"))
        self.inp_hs = QLineEdit(self.config.get("hyperspin_dir", ""))
        self.inp_hs.textChanged.connect(lambda _: self._validate_step_hs())
        lay.addLayout(self._make_input_row(self.inp_hs, is_dir=True, hint="Ej: C:\HyperSpin"))
        self.lbl_hs_status = self._status_label()
        lay.addWidget(self.lbl_hs_status)

        lay.addWidget(self._field_label("HyperSpin.exe *"))
        self.inp_hs_exe = QLineEdit(self.config.get("hyperspin_exe", ""))
        self.inp_hs_exe.textChanged.connect(lambda _: self._validate_step_hs())
        lay.addLayout(self._make_input_row(
            self.inp_hs_exe, is_dir=False,
            file_filter="Ejecutables (*.exe)",
            hint="Ej: C:\HyperSpin\HyperSpin.exe"))
        self.lbl_exe_status = self._status_label()
        lay.addWidget(self.lbl_exe_status)

        lay.addStretch()
        lay.addWidget(self._tip_label(
            "Tip: en instalaciones portables, HyperSpin.exe está en la raíz del directorio."))
        return w

    def _step_rocketlauncher(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {self._BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 24)
        lay.setSpacing(16)

        lay.addWidget(self._desc_label(
            "Selecciona el directorio raíz de RocketLauncher.<br>"
            "Debe contener las carpetas <b style='color:#f5a623'>Modules</b>, "
            "<b style='color:#f5a623'>Settings</b> y "
            "<b style='color:#f5a623'>Media</b>."))

        lay.addWidget(self._field_label("Directorio de RocketLauncher *"))
        self.inp_rl = QLineEdit(self.config.get("rocketlauncher_dir", ""))
        self.inp_rl.textChanged.connect(lambda _: self._validate_step_rl())
        lay.addLayout(self._make_input_row(self.inp_rl, is_dir=True, hint="Ej: C:\RocketLauncher"))
        self.lbl_rl_status = self._status_label()
        lay.addWidget(self.lbl_rl_status)

        lay.addStretch()
        lay.addWidget(self._tip_label(
            "No confundir con RocketLauncherUI. Este es el motor principal (el .ahk o .exe core)."))
        return w

    def _step_rlui(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {self._BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 24)
        lay.setSpacing(14)

        lay.addWidget(self._desc_label(
            "Configura la interfaz gráfica de RocketLauncher.<br>"
            "Al indicar el <b style='color:#f5a623'>directorio RLUI</b> o su .exe, "
            "la app intentará detectar automáticamente la ruta de RocketLauncher."))

        lay.addWidget(self._field_label("Directorio de RocketLauncherUI"))
        self.inp_rlui_dir = QLineEdit(self.config.get("rocketlauncherui_dir", ""))
        self.inp_rlui_dir.textChanged.connect(self._autodetect_from_rlui_inputs)
        lay.addLayout(self._make_input_row(self.inp_rlui_dir, is_dir=True, hint="Ej: C:\RocketLauncherUI"))
        self.lbl_rlui_dir_status = self._status_label()
        lay.addWidget(self.lbl_rlui_dir_status)

        lay.addWidget(self._field_label("RocketLauncherUI.exe o .ini"))
        self.inp_rlui_exe = QLineEdit(self.config.get("rocketlauncherui_exe", ""))
        self.inp_rlui_exe.textChanged.connect(self._autodetect_from_rlui_inputs)
        lay.addLayout(self._make_input_row(
            self.inp_rlui_exe, is_dir=False,
            file_filter="RLUI (*.exe *.ini);;Ejecutables (*.exe);;INI (*.ini)",
            hint="Ej: C:\RocketLauncherUI\RocketLauncherUI.exe"))
        self.lbl_rlui_exe_status = self._status_label()
        lay.addWidget(self.lbl_rlui_exe_status)

        lay.addStretch()
        lay.addWidget(self._tip_label(
            "RocketLauncherUI es la interfaz gráfica de configuración — diferente del motor core."))
        self._autodetect_from_rlui_inputs()
        return w

    def _step_summary(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {self._BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 24)
        lay.setSpacing(12)

        intro = QLabel("Comprueba que todo es correcto antes de guardar:")
        intro.setStyleSheet(
            f"font-size: 12px; color: {self._TXT_LO}; background: transparent;")
        lay.addWidget(intro)

        fields = [
            ("HyperSpin dir",      "hyperspin_dir"),
            ("HyperSpin exe",      "hyperspin_exe"),
            ("RocketLauncher dir", "rocketlauncher_dir"),
            ("RLUI dir",           "rocketlauncherui_dir"),
            ("RLUI exe",           "rocketlauncherui_exe"),
        ]
        self._summary_labels = {}

        for key, cfg_key in fields:
            row = QWidget()
            row.setFixedHeight(38)
            row.setStyleSheet(
                f"background: #07090f; border: 1px solid {self._BORDER}; "
                f"border-radius: 6px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 0, 14, 0)
            rl.setSpacing(12)

            dot = QLabel("●")
            dot.setFixedWidth(10)
            dot.setStyleSheet(
                f"font-size: 8px; color: {self._TXT_GH}; background: transparent;")

            lbl_key = QLabel(key + ":")
            lbl_key.setFixedWidth(150)
            lbl_key.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {self._TXT_LO}; background: transparent;")

            val_lbl = QLabel(self.config.get(cfg_key, ""))
            val_lbl.setStyleSheet(
                f"font-size: 11px; font-family: 'Consolas', monospace; "
                f"color: {self._TXT_MD}; background: transparent;")
            val_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            rl.addWidget(dot)
            rl.addWidget(lbl_key)
            rl.addWidget(val_lbl, 1)
            lay.addWidget(row)
            self._summary_labels[cfg_key] = (dot, val_lbl)

        note = QLabel(
            "Se creará <b>config.json</b> con esta configuración. "
            "Puedes editarla después en la pestaña <b>⚙ Configuración</b>.")
        note.setTextFormat(Qt.TextFormat.RichText)
        note.setWordWrap(True)
        note.setStyleSheet(
            f"font-size: 11px; color: {self._TXT_GH}; background: transparent; "
            f"padding: 10px 14px; border: 1px solid {self._BORDER}; border-radius: 6px;")
        lay.addStretch()
        lay.addWidget(note)
        return w

    # ── Navegación ────────────────────────────────────────────────────────────

    def _show_step(self, step: int):
        self._step = step
        while self.stack.count() <= step:
            self.stack.addWidget(QWidget())
        page = self._steps[step]()
        old = self.stack.widget(step)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.stack.insertWidget(step, page)
        self.stack.setCurrentIndex(step)

        self.lbl_step_title.setText(self._step_titles[step])
        self.lbl_step_hint.setText(self._step_subtitles[step])
        self.lbl_footer_msg.setText("")
        n = len(self._steps)
        self._step_bar.setValue(int((step + 1) * 100 / n))

        for i, dot in enumerate(self._step_dots):
            if i < step:
                dot.setStyleSheet(
                    f"font-size: 10px; font-weight: 700; color: #00994d; "
                    f"padding: 0 8px; letter-spacing: 0.8px; background: transparent;")
            elif i == step:
                dot.setStyleSheet(
                    f"font-size: 10px; font-weight: 800; color: {self._AMBER}; "
                    f"padding: 0 8px; letter-spacing: 0.8px; background: transparent;")
            else:
                dot.setStyleSheet(
                    f"font-size: 10px; font-weight: 700; color: {self._TXT_GH}; "
                    f"padding: 0 8px; letter-spacing: 0.8px; background: transparent;")

        is_last = (step == len(self._steps) - 1)
        self.btn_next.setVisible(not is_last)
        self.btn_finish.setVisible(is_last)
        self.btn_back.setEnabled(step > 0)
        if step == 3:
            self._update_summary()

    def _go_next(self):
        if not self._validate_current():
            return
        self._collect_current()
        if self._step < len(self._steps) - 1:
            self._show_step(self._step + 1)

    def _go_back(self):
        if self._step > 0:
            self._collect_current()
            self._show_step(self._step - 1)

    def _on_finish(self):
        self._collect_current()
        self.accept()

    # ── Validación ────────────────────────────────────────────────────────────

    def _validate_current(self) -> bool:
        if self._step == 0:
            ok1, msg1 = _validate_hyperspin_dir(self.inp_hs.text())
            ok2, msg2 = _validate_file(self.inp_hs_exe.text(), "HyperSpin.exe")
            if not ok1:
                self.lbl_footer_msg.setText(f"HyperSpin dir: {msg1}")
                return False
            if not ok2:
                self.lbl_footer_msg.setText(f"HyperSpin.exe: {msg2}")
                return False
        elif self._step == 1:
            ok, msg = _validate_rocketlauncher_dir(self.inp_rl.text())
            if not ok:
                self.lbl_footer_msg.setText(f"RocketLauncher dir: {msg}")
                return False
        elif self._step == 2:
            rlui_val = self.inp_rlui_exe.text().strip()
            if rlui_val.lower().endswith(".ini"):
                ok1, msg1 = _validate_file(rlui_val, "RocketLauncherUI.ini")
            else:
                ok1, msg1 = _validate_file(rlui_val, "RocketLauncherUI.exe")
            if not ok1:
                self.lbl_footer_msg.setText(f"RLUI exe/ini: {msg1}")
                return False
        return True

    def _validate_step_hs(self):
        ok, msg = _validate_hyperspin_dir(self.inp_hs.text())
        self._set_status(self.lbl_hs_status, ok, msg)
        ok2, msg2 = _validate_file(self.inp_hs_exe.text(), "HyperSpin.exe")
        self._set_status(self.lbl_exe_status, ok2, msg2)

    def _validate_step_rl(self):
        ok, msg = _validate_rocketlauncher_dir(self.inp_rl.text())
        self._set_status(self.lbl_rl_status, ok, msg)

    def _autodetect_from_rlui_inputs(self):
        if not hasattr(self, "inp_rlui_exe") or not hasattr(self, "inp_rlui_dir"):
            return
        detected = _detect_rocketlauncher_from_rlui(
            self.inp_rlui_exe.text().strip(),
            self.inp_rlui_dir.text().strip(),
        )
        if detected.get("rocketlauncherui_dir") and not self.inp_rlui_dir.text().strip():
            self.inp_rlui_dir.setText(detected["rocketlauncherui_dir"])
        if detected.get("rocketlauncherui_exe") and (
            not self.inp_rlui_exe.text().strip()
            or self.inp_rlui_exe.text().strip().lower().endswith(".ini")
        ):
            self.inp_rlui_exe.setText(detected["rocketlauncherui_exe"])
        if detected.get("rocketlauncher_dir"):
            if hasattr(self, "inp_rl") and not self.inp_rl.text().strip():
                self.inp_rl.setText(detected["rocketlauncher_dir"])
        status_msg = detected.get("status", "")
        if status_msg:
            is_ok = status_msg.startswith("✓")
            self._set_status(self.lbl_rlui_exe_status, is_ok, status_msg)

    def _set_status(self, lbl: QLabel, ok: bool, msg: str):
        if ok:
            lbl.setText(f"✓  {msg}")
            lbl.setStyleSheet(
                f"font-size: 11px; background: transparent; "
                f"font-family: {self._MONO}; color: {self._GREEN};")
        else:
            lbl.setText(f"✗  {msg}")
            lbl.setStyleSheet(
                f"font-size: 11px; background: transparent; "
                f"font-family: {self._MONO}; color: {self._RED};")

    def _collect_current(self):
        if self._step == 0:
            self.config["hyperspin_dir"] = self.inp_hs.text().strip()
            self.config["hyperspin_exe"] = self.inp_hs_exe.text().strip()
        elif self._step == 1:
            self.config["rocketlauncher_dir"] = self.inp_rl.text().strip()
        elif self._step == 2:
            self.config["rocketlauncherui_dir"] = self.inp_rlui_dir.text().strip()
            self.config["rocketlauncherui_exe"] = self.inp_rlui_exe.text().strip()
            detected = _detect_rocketlauncher_from_rlui(
                self.inp_rlui_exe.text().strip(),
                self.inp_rlui_dir.text().strip(),
            )
            self.config["rocketlauncherui_ini"] = detected.get("rocketlauncherui_ini", "")

    def _update_summary(self):
        if not hasattr(self, "_summary_labels"):
            return
        for cfg_key, (dot, val_lbl) in self._summary_labels.items():
            val = self.config.get(cfg_key, "")
            if val and os.path.exists(val):
                val_lbl.setText(val)
                val_lbl.setStyleSheet(
                    f"font-size: 11px; font-family: 'Consolas', monospace; "
                    f"color: {self._GREEN}; background: transparent;")
                dot.setStyleSheet(
                    f"font-size: 8px; color: {self._GREEN}; background: transparent;")
            elif val:
                val_lbl.setText(val + "  (no encontrado)")
                val_lbl.setStyleSheet(
                    f"font-size: 11px; font-family: 'Consolas', monospace; "
                    f"color: {self._RED}; background: transparent;")
                dot.setStyleSheet(
                    f"font-size: 8px; color: {self._RED}; background: transparent;")
            else:
                val_lbl.setText("(no configurado)")
                val_lbl.setStyleSheet(
                    f"font-size: 11px; font-family: 'Consolas', monospace; "
                    f"color: {self._TXT_GH}; background: transparent;")
                dot.setStyleSheet(
                    f"font-size: 8px; color: {self._TXT_GH}; background: transparent;")

    def _browse_dir(self, inp: QLineEdit):
        start = inp.text() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Seleccionar directorio", start)
        if path:
            inp.setText(path)

    def _browse_file(self, inp: QLineEdit, filt: str):
        start = os.path.dirname(inp.text()) if inp.text() else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", start, filt)
        if path:
            inp.setText(path)

    def get_config(self) -> dict:
        return self.config



# ─── Pestaña de configuración ─────────────────────────────────────────────────

class ConfigurationTab(TabModule):
    tab_title = "⚙ Configuración"
    tab_icon  = ""

    _AMBER  = "#f5a623"
    _CYAN   = "#00c9e8"
    _GREEN  = "#00e599"
    _RED    = "#ff4d6a"
    _DEEP   = "#05070b"
    _BASE   = "#090c12"
    _RAISED = "#0d1018"
    _BORDER = "#1a2035"
    _MID    = "#243050"
    _TXT_HI = "#e8edf8"
    _TXT_MD = "#8a9ab8"
    _TXT_LO = "#4a5878"
    _TXT_GH = "#2a3450"
    _MONO   = "'Consolas', 'Courier New', monospace"

    def __init__(self, parent):
        super().__init__(parent)
        self._config: dict         = {}
        self._scan_worker = None
        self._on_complete_cb       = None
        self._main_widget          = None
        self._path_inputs: dict    = {}

    # ── API pública ────────────────────────────────────────────────────────────

    def run_setup_wizard(self, config: dict, on_complete=None):
        self._config = dict(config)
        self._on_complete_cb = on_complete
        wizard = SetupWizard(self._config, parent=self.parent)
        result = wizard.exec()
        if result == QDialog.Accepted:
            self._config = wizard.get_config()
            if self._on_complete_cb:
                self._on_complete_cb(self._config)
        else:
            if self.parent:
                self.parent.statusBar().showMessage(
                    "⚠ Configuración incompleta — algunas funciones estarán limitadas.", 8000)

    def widget(self) -> QWidget:
        if self._main_widget is None:
            self._main_widget = self._build_widget()
        return self._main_widget

    def load_data(self, config: dict):
        self._config = dict(config)
        if self._main_widget:
            self._refresh_fields()

    def save_data(self) -> dict:
        if self._main_widget:
            self._collect_fields()
        return self._config

    # ── Construcción del widget principal ──────────────────────────────────────

    def _build_widget(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(f"background: {self._DEEP};")
        main_lay = QVBoxLayout(root)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        main_lay.addWidget(self._build_topbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {self._DEEP}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background: {self._DEEP};")
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(24, 24, 24, 28)
        c_lay.setSpacing(18)

        c_lay.addWidget(self._build_paths_panel())
        c_lay.addWidget(self._build_appearance_panel())
        c_lay.addWidget(self._build_scan_panel())
        c_lay.addStretch()

        scroll.setWidget(content)
        main_lay.addWidget(scroll)
        return root

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(
            f"background: {self._DEEP}; border-bottom: 1px solid {self._BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"font-size: 10px; color: {self._AMBER}; background: transparent;")
        title = QLabel("Configuración")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: 800; color: {self._TXT_HI}; "
            f"background: transparent; letter-spacing: -0.2px;")
        sub = QLabel("Rutas, apariencia y escaneo")
        sub.setStyleSheet(
            f"font-size: 11px; color: {self._TXT_GH}; "
            f"background: transparent; font-family: {self._MONO};")

        btn_wizard = QPushButton("↺  Asistente inicial")
        btn_wizard.setObjectName("btn_primary")
        btn_wizard.setFixedHeight(32)
        btn_wizard.setFixedWidth(158)
        btn_wizard.setToolTip("Relanzar el wizard de configuración inicial")
        btn_wizard.clicked.connect(self._relaunch_wizard)

        lay.addWidget(dot)
        lay.addWidget(title)
        lay.addSpacing(10)
        lay.addWidget(sub)
        lay.addStretch()
        lay.addWidget(btn_wizard)
        return bar

    # ── Panel: Rutas ──────────────────────────────────────────────────────────

    def _build_paths_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: #0a0d14; border: 1px solid {self._BORDER}; border-radius: 10px; }}")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header del panel
        hdr = self._panel_header("RUTAS DEL SISTEMA")
        lay.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_lay = QGridLayout(body)
        b_lay.setContentsMargins(20, 16, 20, 16)
        b_lay.setSpacing(10)
        b_lay.setColumnStretch(1, 1)

        defs = [
            ("hyperspin_dir",        "HyperSpin",          True,  ""),
            ("hyperspin_exe",        "HyperSpin.exe",       False, "Ejecutables (*.exe)"),
            ("rocketlauncher_dir",   "RocketLauncher",      True,  ""),
            ("rocketlauncherui_dir", "RLUI Directorio",     True,  ""),
            ("rocketlauncherui_exe", "RLUI / .exe o .ini",  False, "RLUI (*.exe *.ini);;Ejecutables (*.exe);;INI (*.ini)"),
        ]

        self._path_inputs = {}
        self._path_dots   = {}

        for row_i, (key, label, is_dir, filt) in enumerate(defs):
            # Dot indicador
            dot = QLabel("●")
            dot.setFixedWidth(14)
            dot.setStyleSheet(
                f"font-size: 8px; color: {self._TXT_GH}; background: transparent;")
            self._path_dots[key] = dot

            lbl = QLabel(label + ":")
            lbl.setFixedWidth(140)
            lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {self._TXT_LO}; background: transparent;")

            inp = QLineEdit(self._config.get(key, ""))
            inp.setPlaceholderText("(no configurado)")
            inp.textChanged.connect(lambda text, k=key: self._on_path_changed(k, text))
            self._path_inputs[key] = inp

            if key in ("rocketlauncherui_dir", "rocketlauncherui_exe"):
                inp.textChanged.connect(self._autodetect_paths_from_rlui_fields)

            btn = QPushButton("…")
            btn.setFixedWidth(32)
            btn.setFixedHeight(32)
            btn.setStyleSheet(
                f"QPushButton {{ background: {self._RAISED}; border: 1px solid {self._BORDER}; "
                f"border-radius: 6px; color: {self._TXT_LO}; font-size: 13px; font-weight: 700; }}"
                f"QPushButton:hover {{ background: #111520; color: {self._TXT_MD}; border-color: {self._MID}; }}")

            if is_dir:
                btn.clicked.connect(lambda _, i=inp: self._browse_dir(i))
            else:
                btn.clicked.connect(lambda _, i=inp, f=filt: self._browse_file(i, f))

            b_lay.addWidget(dot, row_i, 0, Qt.AlignmentFlag.AlignVCenter)
            b_lay.addWidget(lbl, row_i, 1, Qt.AlignmentFlag.AlignVCenter)
            b_lay.addWidget(inp, row_i, 2)
            b_lay.addWidget(btn, row_i, 3)

        # Autodetect status
        self.lbl_rlui_autodetect = QLabel("")
        self.lbl_rlui_autodetect.setWordWrap(True)
        self.lbl_rlui_autodetect.setStyleSheet(
            f"font-size: 11px; font-family: {self._MONO}; color: {self._TXT_GH}; "
            f"background: transparent; padding: 4px 0;")

        # Validate button + result
        btn_validate = QPushButton("✓  Validar rutas")
        btn_validate.setObjectName("btn_primary")
        btn_validate.setFixedWidth(140)
        btn_validate.setFixedHeight(30)
        btn_validate.clicked.connect(self._validate_paths)

        self.lbl_validate_result = QLabel("")
        self.lbl_validate_result.setWordWrap(True)
        self.lbl_validate_result.setStyleSheet(
            f"font-size: 11px; font-family: {self._MONO}; color: {self._TXT_GH}; background: transparent;")

        n = len(defs)
        b_lay.addWidget(self.lbl_rlui_autodetect, n,     0, 1, 4)
        b_lay.addWidget(btn_validate,              n + 1, 2, 1, 2)
        b_lay.addWidget(self.lbl_validate_result,  n + 2, 0, 1, 4)

        lay.addWidget(body)
        self._autodetect_paths_from_rlui_fields()
        return panel

    # ── Panel: Apariencia ─────────────────────────────────────────────────────

    def _build_appearance_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: #0a0d14; border: 1px solid {self._BORDER}; border-radius: 10px; }}")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = self._panel_header("APARIENCIA")
        lay.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_lay = QGridLayout(body)
        b_lay.setContentsMargins(20, 16, 20, 16)
        b_lay.setSpacing(10)
        b_lay.setColumnStretch(1, 1)

        def lbl_s(text):
            l = QLabel(text + ":")
            l.setFixedWidth(140)
            l.setStyleSheet(
                f"font-size: 11px; font-weight: 700; color: {self._TXT_LO}; background: transparent;")
            return l

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems(["Oscuro (dark)", "Claro (light)"])
        saved_theme = self._config.get("theme", "dark")
        self.cmb_theme.setCurrentIndex(0 if saved_theme == "dark" else 1)

        self.cmb_fontsize = QComboBox()
        for sz in ["11", "12", "13", "14", "15"]:
            self.cmb_fontsize.addItem(sz + " px", sz)
        saved_fs = str(self.config_val("font_size", "13"))
        idx = self.cmb_fontsize.findData(saved_fs)
        if idx >= 0:
            self.cmb_fontsize.setCurrentIndex(idx)

        self.cmb_accent = QComboBox()
        accents = [
            ("Ámbar dorado (predeterminado)", "#f5a623"),
            ("Cian eléctrico",                "#00c9e8"),
            ("Verde neón",                    "#00e599"),
            ("Magenta",                       "#f472b6"),
            ("Violeta",                       "#a78bfa"),
        ]
        for name, val in accents:
            self.cmb_accent.addItem(name, val)
        saved_ac = self.config_val("accent_color", "#f5a623")
        idx_ac = self.cmb_accent.findData(saved_ac)
        if idx_ac >= 0:
            self.cmb_accent.setCurrentIndex(idx_ac)

        btn_apply = QPushButton("Aplicar apariencia")
        btn_apply.setObjectName("btn_primary")
        btn_apply.setFixedWidth(160)
        btn_apply.setFixedHeight(30)
        btn_apply.clicked.connect(self._apply_appearance)

        b_lay.addWidget(lbl_s("Tema"),          0, 0)
        b_lay.addWidget(self.cmb_theme,          0, 1)
        b_lay.addWidget(lbl_s("Tamaño fuente"),  1, 0)
        b_lay.addWidget(self.cmb_fontsize,        1, 1)
        b_lay.addWidget(lbl_s("Color acento"),   2, 0)
        b_lay.addWidget(self.cmb_accent,          2, 1)
        b_lay.addWidget(btn_apply,               3, 1)

        lay.addWidget(body)
        return panel

    # ── Panel: Escaneo ────────────────────────────────────────────────────────

    def _build_scan_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: #0a0d14; border: 1px solid {self._BORDER}; border-radius: 10px; }}")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = self._panel_header("ESCANEO DE DIRECTORIOS")
        lay.addWidget(hdr)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(20, 14, 20, 16)
        b_lay.setSpacing(12)

        desc = QLabel("Detecta sistemas, XML, módulos y carpetas de media en los directorios configurados.")
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-size: 12px; color: {self._TXT_GH}; background: transparent;")

        btn_row = QHBoxLayout()
        self.btn_scan = QPushButton("▶  Iniciar escaneo")
        self.btn_scan.setObjectName("btn_primary")
        self.btn_scan.setFixedWidth(160)
        self.btn_scan.setFixedHeight(32)
        self.btn_scan.clicked.connect(self._start_scan)
        btn_row.addWidget(self.btn_scan)
        btn_row.addStretch()

        self.scan_progress = QProgressBar()
        self.scan_progress.setValue(0)
        self.scan_progress.setFixedHeight(3)
        self.scan_progress.setTextVisible(False)
        self.scan_progress.hide()

        self.lbl_scan_status = QLabel("")
        self.lbl_scan_status.setStyleSheet(
            f"font-size: 11px; font-family: {self._MONO}; color: {self._AMBER}; background: transparent;")

        # Resultado en cards de stats
        self.scan_results_row = QWidget()
        self.scan_results_row.setStyleSheet("background: transparent;")
        self.scan_results_row.hide()
        rr_lay = QHBoxLayout(self.scan_results_row)
        rr_lay.setContentsMargins(0, 0, 0, 0)
        rr_lay.setSpacing(10)

        self._scan_stat_lbls = {}
        for key, label, color in [
            ("systems", "Sistemas",  self._AMBER),
            ("dbs",     "XML",       self._CYAN),
            ("modules", "Módulos",   self._GREEN),
            ("media",   "Media",     "#a78bfa"),
        ]:
            card = QFrame()
            card.setFixedHeight(64)
            card.setStyleSheet(
                f"QFrame {{ background: #07090f; border: 1px solid {self._BORDER}; "
                f"border-left: 3px solid {color}; border-radius: 6px; }}")
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 8, 12, 8)
            cl.setSpacing(2)
            v = QLabel("—")
            v.setStyleSheet(
                f"font-size: 20px; font-weight: 800; color: {color}; background: transparent;")
            l = QLabel(label.upper())
            l.setStyleSheet(
                f"font-size: 9px; font-weight: 800; letter-spacing: 1.2px; "
                f"color: {self._TXT_GH}; font-family: {self._MONO}; background: transparent;")
            cl.addWidget(v)
            cl.addWidget(l)
            rr_lay.addWidget(card)
            self._scan_stat_lbls[key] = v

        b_lay.addWidget(desc)
        b_lay.addLayout(btn_row)
        b_lay.addWidget(self.scan_progress)
        b_lay.addWidget(self.lbl_scan_status)
        b_lay.addWidget(self.scan_results_row)

        lay.addWidget(body)
        return panel

    def _panel_header(self, title: str) -> QWidget:
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background: {self._RAISED}; border-radius: 10px 10px 0 0; "
            f"border-bottom: 1px solid {self._BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(18, 0, 18, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 800; letter-spacing: 1.6px; "
            f"color: {self._TXT_GH}; font-family: {self._MONO}; background: transparent;")
        hl.addWidget(lbl)
        hl.addStretch()
        return hdr

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _refresh_fields(self):
        for key, inp in self._path_inputs.items():
            inp.setText(self._config.get(key, ""))
        self._update_all_path_dots()

    def _collect_fields(self):
        for key, inp in self._path_inputs.items():
            self._config[key] = inp.text().strip()
        detected = _detect_rocketlauncher_from_rlui(
            self._config.get("rocketlauncherui_exe", ""),
            self._config.get("rocketlauncherui_dir", ""),
        )
        self._config["rocketlauncherui_ini"] = detected.get("rocketlauncherui_ini", "")

    def _on_path_changed(self, key: str, text: str):
        dot = self._path_dots.get(key)
        if not dot:
            return
        path = text.strip()
        if not path:
            dot.setStyleSheet(
                f"font-size: 8px; color: {self._TXT_GH}; background: transparent;")
        elif os.path.exists(path):
            dot.setStyleSheet(
                f"font-size: 8px; color: {self._GREEN}; background: transparent;")
        else:
            dot.setStyleSheet(
                f"font-size: 8px; color: {self._RED}; background: transparent;")

    def _update_all_path_dots(self):
        for key, inp in self._path_inputs.items():
            self._on_path_changed(key, inp.text())

    def _autodetect_paths_from_rlui_fields(self):
        if not hasattr(self, "_path_inputs"):
            return
        inp_rlui     = self._path_inputs.get("rocketlauncherui_exe")
        inp_rlui_dir = self._path_inputs.get("rocketlauncherui_dir")
        inp_rl       = self._path_inputs.get("rocketlauncher_dir")
        if not inp_rlui or not inp_rlui_dir or not inp_rl:
            return
        detected = _detect_rocketlauncher_from_rlui(inp_rlui.text().strip(), inp_rlui_dir.text().strip())
        if detected.get("rocketlauncherui_dir") and not inp_rlui_dir.text().strip():
            inp_rlui_dir.setText(detected["rocketlauncherui_dir"])
        if detected.get("rocketlauncherui_exe") and (
            not inp_rlui.text().strip() or inp_rlui.text().strip().lower().endswith(".ini")
        ):
            inp_rlui.setText(detected["rocketlauncherui_exe"])
        if detected.get("rocketlauncher_dir") and not inp_rl.text().strip():
            inp_rl.setText(detected["rocketlauncher_dir"])
        msg = detected.get("status", "")
        if msg:
            ok = msg.startswith("✓")
            self.lbl_rlui_autodetect.setText(msg)
            self.lbl_rlui_autodetect.setStyleSheet(
                f"font-size: 11px; font-family: {self._MONO}; "
                f"color: {self._GREEN if ok else self._AMBER}; background: transparent;")
        else:
            self.lbl_rlui_autodetect.setText("")

    def config_val(self, key: str, default=None):
        return self._config.get(key, default)

    def _relaunch_wizard(self):
        reply = QMessageBox.question(
            self.parent, "Relanzar asistente",
            "¿Volver a ejecutar el asistente de configuración inicial?\n"
            "Los valores actuales se usarán como punto de partida.",
            QMessageBox.Yes | QMessageBox.Cancel
        )
        if reply == QMessageBox.Yes:
            self._collect_fields()
            self.run_setup_wizard(self._config, on_complete=self._on_wizard_done)

    def _on_wizard_done(self, new_cfg: dict):
        self._config.update(new_cfg)
        self._refresh_fields()
        if self.parent:
            self.parent.statusBar().showMessage("✓ Configuración actualizada.", 5000)

    def _validate_paths(self):
        self._collect_fields()
        errors = []
        ok, msg = _validate_hyperspin_dir(self._config.get("hyperspin_dir", ""))
        if not ok: errors.append(f"HyperSpin dir: {msg}")
        ok, msg = _validate_file(self._config.get("hyperspin_exe", ""), "HyperSpin.exe")
        if not ok: errors.append(f"HyperSpin.exe: {msg}")
        ok, msg = _validate_rocketlauncher_dir(self._config.get("rocketlauncher_dir", ""))
        if not ok: errors.append(f"RocketLauncher dir: {msg}")
        rlui_entry = self._config.get("rocketlauncherui_exe", "")
        if rlui_entry.lower().endswith(".ini"):
            ok, msg = _validate_file(rlui_entry, "RocketLauncherUI.ini")
        else:
            ok, msg = _validate_file(rlui_entry, "RocketLauncherUI.exe")
        if not ok: errors.append(f"RLUI exe/ini: {msg}")
        if errors:
            self.lbl_validate_result.setText("✗  " + "  ·  ".join(errors))
            self.lbl_validate_result.setStyleSheet(
                f"font-size: 11px; font-family: {self._MONO}; color: {self._RED}; background: transparent;")
        else:
            self.lbl_validate_result.setText("✓  Todas las rutas son válidas")
            self.lbl_validate_result.setStyleSheet(
                f"font-size: 11px; font-family: {self._MONO}; color: {self._GREEN}; background: transparent;")

    def _apply_appearance(self):
        fs     = self.cmb_fontsize.currentData()
        accent = self.cmb_accent.currentData()
        theme  = "dark" if self.cmb_theme.currentIndex() == 0 else "light"
        self._config["font_size"]    = fs
        self._config["accent_color"] = accent
        self._config["theme"]        = theme
        try:
            from main import load_theme_stylesheet
            qss = load_theme_stylesheet(theme)
            if accent != "#f5a623":
                qss = qss.replace("#f5a623", accent).replace("#c4841a", accent).replace("#ffbe4d", accent)
            if fs != "13":
                qss = qss.replace("font-size: 13px;", f"font-size: {fs}px;")
            QApplication.instance().setStyleSheet(qss)
            if self.parent:
                self.parent.statusBar().showMessage(
                    f"✓ Apariencia aplicada — tema {theme}, acento {accent}, fuente {fs}px", 5000)
        except Exception as e:
            print(f"[WARN] No se pudo aplicar apariencia: {e}")

    def _start_scan(self):
        self._collect_fields()
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("Escaneando…")
        self.scan_progress.show()
        self.scan_progress.setValue(0)
        self.scan_results_row.hide()
        self.lbl_scan_status.setText("Iniciando escaneo…")

        self._scan_worker = ScanWorker(self._config)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_progress(self, pct: int, msg: str):
        self.scan_progress.setValue(pct)
        self.lbl_scan_status.setText(msg[:80])

    def _on_scan_finished(self, results: dict):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("▶  Iniciar escaneo")
        self.scan_progress.hide()
        self.lbl_scan_status.setText(
            f"✓  Escaneo completado — {len(results.get('systems', []))} sistemas detectados")
        self.lbl_scan_status.setStyleSheet(
            f"font-size: 11px; font-family: {self._MONO}; color: {self._GREEN}; background: transparent;")

        self._scan_stat_lbls["systems"].setText(str(len(results.get("systems", []))))
        self._scan_stat_lbls["dbs"].setText(str(len(results.get("databases", []))))
        self._scan_stat_lbls["modules"].setText(str(len(results.get("modules", []))))
        self._scan_stat_lbls["media"].setText(str(len(results.get("media_dirs", []))))
        self.scan_results_row.show()

        self._config["scan_results"] = results
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ Escaneo completado — {len(results.get('systems', []))} sistemas, "
                f"{len(results.get('modules', []))} módulos", 5000)

    def _browse_dir(self, inp: QLineEdit):
        start = inp.text() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self.parent, "Seleccionar directorio", start)
        if path:
            inp.setText(path)

    def _browse_file(self, inp: QLineEdit, filt: str):
        start = os.path.dirname(inp.text()) if inp.text() else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self.parent, "Seleccionar archivo", start, filt)
        if path:
            inp.setText(path)
