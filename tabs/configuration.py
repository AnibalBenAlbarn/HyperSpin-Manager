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

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.setWindowTitle("Configuración inicial — HyperSpin Manager")
        self.setMinimumSize(680, 520)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)

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

        self._build_ui()
        self._show_step(0)

    # ── Construcción UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(90)
        header.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #0a1628, stop:1 #0d1f3c);
            border-bottom: 1px solid #1e2f50;
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(32, 14, 32, 14)

        self.lbl_step_title = QLabel()
        self.lbl_step_title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #e8ecf4; background: transparent;")

        self.lbl_step_hint = QLabel("Completa los pasos para comenzar a usar la aplicación.")
        self.lbl_step_hint.setStyleSheet(
            "font-size: 12px; color: #4a6080; background: transparent;")

        h_lay.addWidget(self.lbl_step_title)
        h_lay.addWidget(self.lbl_step_hint)

        # ── Indicador de pasos ───────────────────────────────────────────────
        steps_bar = QWidget()
        steps_bar.setFixedHeight(44)
        steps_bar.setStyleSheet("background: #0d0f14; border-bottom: 1px solid #1e2330;")
        s_lay = QHBoxLayout(steps_bar)
        s_lay.setContentsMargins(24, 0, 24, 0)
        s_lay.setSpacing(0)

        self._step_dots = []
        labels = ["1  HyperSpin", "2  RocketLauncher", "3  Ejecutables", "4  Confirmar"]
        for i, lbl in enumerate(labels):
            dot = QLabel(lbl)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet("font-size: 11px; font-weight: 600; color: #2a3a55; padding: 0 8px;")
            dot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._step_dots.append(dot)
            s_lay.addWidget(dot)

            if i < len(labels) - 1:
                sep = QLabel("›")
                sep.setStyleSheet("color: #1e2330; font-size: 14px;")
                s_lay.addWidget(sep)

        # ── Contenido ────────────────────────────────────────────────────────
        self.stack = QStackedWidget()

        # ── Footer ───────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet("background: #080a0f; border-top: 1px solid #1e2330;")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(24, 0, 24, 0)

        self.lbl_footer_msg = QLabel("")
        self.lbl_footer_msg.setStyleSheet("color: #ffb74d; font-size: 12px;")

        self.btn_back = QPushButton("← Anterior")
        self.btn_next = QPushButton("Siguiente →")
        self.btn_next.setObjectName("btn_primary")
        self.btn_finish = QPushButton("✓  Finalizar configuración")
        self.btn_finish.setObjectName("btn_success")
        self.btn_finish.hide()

        self.btn_back.setFixedWidth(130)
        self.btn_next.setFixedWidth(130)
        self.btn_finish.setFixedWidth(200)

        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.btn_finish.clicked.connect(self._on_finish)

        f_lay.addWidget(self.lbl_footer_msg, 1)
        f_lay.addWidget(self.btn_back)
        f_lay.addSpacing(8)
        f_lay.addWidget(self.btn_next)
        f_lay.addWidget(self.btn_finish)

        root.addWidget(header)
        root.addWidget(steps_bar)
        root.addWidget(self.stack, 1)
        root.addWidget(footer)

    # ── Pasos ──────────────────────────────────────────────────────────────────

    def _step_hyperspin(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 20)
        lay.setSpacing(16)

        desc = QLabel(
            "Selecciona el directorio raíz de HyperSpin.\n"
            "Debe contener las carpetas: <b>Settings</b>, <b>Media</b> y <b>Databases</b>."
        )
        desc.setTextFormat(Qt.TextFormat.RichText)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6878a0; font-size: 13px; line-height: 1.5;")

        row = QHBoxLayout()
        self.inp_hs = QLineEdit(self.config.get("hyperspin_dir", ""))
        self.inp_hs.setPlaceholderText("Ej: C:\\HyperSpin")
        self.inp_hs.textChanged.connect(lambda _: self._validate_step_hs())
        btn_hs = QPushButton("Examinar…")
        btn_hs.setFixedWidth(100)
        btn_hs.clicked.connect(lambda: self._browse_dir(self.inp_hs))
        row.addWidget(self.inp_hs)
        row.addWidget(btn_hs)

        self.lbl_hs_status = QLabel("")
        self.lbl_hs_status.setStyleSheet("font-size: 12px;")

        exe_lbl = QLabel("Ruta al ejecutable <b>HyperSpin.exe</b>:")
        exe_lbl.setTextFormat(Qt.TextFormat.RichText)
        exe_lbl.setStyleSheet("color: #6878a0; margin-top: 8px;")
        exe_row = QHBoxLayout()
        self.inp_hs_exe = QLineEdit(self.config.get("hyperspin_exe", ""))
        self.inp_hs_exe.setPlaceholderText("Ej: C:\\HyperSpin\\HyperSpin.exe")
        btn_exe = QPushButton("Examinar…")
        btn_exe.setFixedWidth(100)
        btn_exe.clicked.connect(
            lambda: self._browse_file(self.inp_hs_exe, "HyperSpin.exe",
                                      "Ejecutables (*.exe)"))
        self.lbl_exe_status = QLabel("")
        self.lbl_exe_status.setStyleSheet("font-size: 12px;")
        exe_row.addWidget(self.inp_hs_exe)
        exe_row.addWidget(btn_exe)

        tip = QLabel("💡 Tip: si tienes HyperSpin portable, selecciona la carpeta donde está HyperSpin.exe.")
        tip.setStyleSheet("color: #2a4a6e; font-size: 11px; margin-top: 16px;")
        tip.setWordWrap(True)

        lay.addWidget(desc)
        lay.addSpacing(4)
        lay.addLayout(row)
        lay.addWidget(self.lbl_hs_status)
        lay.addSpacing(12)
        lay.addWidget(exe_lbl)
        lay.addLayout(exe_row)
        lay.addWidget(self.lbl_exe_status)
        lay.addStretch()
        lay.addWidget(tip)
        return w

    def _step_rocketlauncher(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 20)
        lay.setSpacing(14)

        desc = QLabel(
            "Selecciona el directorio raíz de RocketLauncher.\n"
            "Debe contener las carpetas: <b>Modules</b>, <b>Settings</b> y <b>Media</b>."
        )
        desc.setTextFormat(Qt.TextFormat.RichText)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #6878a0; font-size: 13px;")

        row = QHBoxLayout()
        self.inp_rl = QLineEdit(self.config.get("rocketlauncher_dir", ""))
        self.inp_rl.setPlaceholderText("Ej: C:\\RocketLauncher")
        self.inp_rl.textChanged.connect(lambda _: self._validate_step_rl())
        btn = QPushButton("Examinar…")
        btn.setFixedWidth(100)
        btn.clicked.connect(lambda: self._browse_dir(self.inp_rl))
        row.addWidget(self.inp_rl)
        row.addWidget(btn)

        self.lbl_rl_status = QLabel("")
        self.lbl_rl_status.setStyleSheet("font-size: 12px;")

        tip = QLabel("💡 No confundir con RocketLauncherUI. Este es el directorio del motor principal.")
        tip.setStyleSheet("color: #2a4a6e; font-size: 11px; margin-top: 16px;")
        tip.setWordWrap(True)

        lay.addWidget(desc)
        lay.addLayout(row)
        lay.addWidget(self.lbl_rl_status)
        lay.addStretch()
        lay.addWidget(tip)
        return w

    def _step_rlui(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 20)
        lay.setSpacing(12)

        # ── RocketLauncherUI dir ─────────────────────────────────────────────
        lbl1 = QLabel("Directorio raíz de <b>RocketLauncherUI</b>:")
        lbl1.setTextFormat(Qt.TextFormat.RichText)
        lbl1.setStyleSheet("color: #6878a0;")

        row1 = QHBoxLayout()
        self.inp_rlui_dir = QLineEdit(self.config.get("rocketlauncherui_dir", ""))
        self.inp_rlui_dir.setPlaceholderText("Ej: C:\\RocketLauncherUI")
        self.inp_rlui_dir.textChanged.connect(self._autodetect_from_rlui_inputs)
        btn1 = QPushButton("Examinar…")
        btn1.setFixedWidth(100)
        btn1.clicked.connect(lambda: self._browse_dir(self.inp_rlui_dir))
        row1.addWidget(self.inp_rlui_dir)
        row1.addWidget(btn1)
        self.lbl_rlui_dir_status = QLabel("")
        self.lbl_rlui_dir_status.setStyleSheet("font-size: 12px;")

        # ── RocketLauncherUI exe ─────────────────────────────────────────────
        lbl2 = QLabel("Ruta al ejecutable <b>RocketLauncherUI.exe</b>:")
        lbl2.setTextFormat(Qt.TextFormat.RichText)
        lbl2.setStyleSheet("color: #6878a0; margin-top: 10px;")

        row2 = QHBoxLayout()
        self.inp_rlui_exe = QLineEdit(self.config.get("rocketlauncherui_exe", ""))
        self.inp_rlui_exe.setPlaceholderText("Ej: C:\\RocketLauncherUI\\RocketLauncherUI.exe o .ini")
        self.inp_rlui_exe.textChanged.connect(self._autodetect_from_rlui_inputs)
        btn2 = QPushButton("Examinar…")
        btn2.setFixedWidth(100)
        btn2.clicked.connect(
            lambda: self._browse_file(self.inp_rlui_exe, "RocketLauncherUI",
                                      "RocketLauncherUI (*.exe *.ini);;Ejecutables (*.exe);;INI (*.ini)"))
        row2.addWidget(self.inp_rlui_exe)
        row2.addWidget(btn2)
        self.lbl_rlui_exe_status = QLabel("")
        self.lbl_rlui_exe_status.setStyleSheet("font-size: 12px;")

        tip = QLabel("💡 RocketLauncherUI es la interfaz gráfica de configuración de RocketLauncher.")
        tip.setStyleSheet("color: #2a4a6e; font-size: 11px; margin-top: 14px;")
        tip.setWordWrap(True)

        lay.addWidget(lbl1)
        lay.addLayout(row1)
        lay.addWidget(self.lbl_rlui_dir_status)
        lay.addWidget(lbl2)
        lay.addLayout(row2)
        lay.addWidget(self.lbl_rlui_exe_status)
        lay.addStretch()
        lay.addWidget(tip)
        self._autodetect_from_rlui_inputs()
        return w

    def _step_summary(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 20)
        lay.setSpacing(10)

        intro = QLabel("Comprueba que todo está correcto antes de finalizar:")
        intro.setStyleSheet("color: #6878a0; margin-bottom: 8px;")

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 200)

        fields = [
            ("HyperSpin dir",       "hyperspin_dir"),
            ("HyperSpin exe",       "hyperspin_exe"),
            ("RocketLauncher dir",  "rocketlauncher_dir"),
            ("RLUI dir",            "rocketlauncherui_dir"),
            ("RLUI exe",            "rocketlauncherui_exe"),
        ]
        self._summary_labels = {}
        for row_i, (label, key) in enumerate(fields):
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("color: #4a6080; font-weight: 600; font-size: 12px;")
            val = QLabel(self.config.get(key, "<no configurado>"))
            val.setStyleSheet("color: #c8cdd8; font-size: 12px;")
            val.setWordWrap(True)
            grid.addWidget(lbl, row_i, 0)
            grid.addWidget(val, row_i, 1)
            self._summary_labels[key] = val

        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #0a0d12;
                border: 1px solid #1e2330;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        frame.setLayout(grid)

        note = QLabel(
            "Al finalizar se creará <b>config.json</b> con esta información.\n"
            "Podrás editar estos valores desde la pestaña <b>Configuración</b>."
        )
        note.setTextFormat(Qt.TextFormat.RichText)
        note.setWordWrap(True)
        note.setStyleSheet("color: #3a4a68; font-size: 12px; margin-top: 16px;")

        lay.addWidget(intro)
        lay.addWidget(frame)
        lay.addWidget(note)
        lay.addStretch()
        return w

    # ── Navegación ─────────────────────────────────────────────────────────────

    def _show_step(self, step: int):
        self._step = step

        # Reconstruye el widget del paso actual (para valores frescos en summary)
        while self.stack.count() <= step:
            self.stack.addWidget(QWidget())
        page = self._steps[step]()
        self.stack.removeWidget(self.stack.widget(step))
        self.stack.insertWidget(step, page)
        self.stack.setCurrentIndex(step)

        self.lbl_step_title.setText(self._step_titles[step])
        self.lbl_footer_msg.setText("")

        # Actualizar dots
        for i, dot in enumerate(self._step_dots):
            if i < step:
                dot.setStyleSheet("font-size: 11px; font-weight: 600; color: #1a5a30; padding: 0 8px;")
            elif i == step:
                dot.setStyleSheet("font-size: 11px; font-weight: 700; color: #4fc3f7; padding: 0 8px;")
            else:
                dot.setStyleSheet("font-size: 11px; font-weight: 600; color: #2a3a55; padding: 0 8px;")

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

    # ── Validación ─────────────────────────────────────────────────────────────

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
            current_rl = self.inp_rl.text().strip() if hasattr(self, "inp_rl") else ""
            if not current_rl:
                self.inp_rl.setText(detected["rocketlauncher_dir"])

        status_msg = detected.get("status", "")
        if status_msg:
            is_ok = status_msg.startswith("✓")
            self._set_status(self.lbl_rlui_exe_status, is_ok, status_msg[2:] if len(status_msg) > 2 else status_msg)
        elif self.inp_rlui_exe.text().strip() or self.inp_rlui_dir.text().strip():
            self._set_status(self.lbl_rlui_exe_status, False, "No se pudo autodetectar RocketLauncher desde RLUI.")

    def _set_status(self, lbl: QLabel, ok: bool, msg: str):
        if ok:
            lbl.setText("✓ " + msg)
            lbl.setStyleSheet("color: #69f0ae; font-size: 12px;")
        else:
            lbl.setText("✗ " + msg)
            lbl.setStyleSheet("color: #ef9a9a; font-size: 12px;")

    # ── Recopilación de datos ───────────────────────────────────────────────────

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
        """Actualiza las etiquetas del paso de resumen."""
        if not hasattr(self, "_summary_labels"):
            return
        for key, lbl in self._summary_labels.items():
            val = self.config.get(key, "")
            if val:
                lbl.setText(val)
                lbl.setStyleSheet("color: #69f0ae; font-size: 12px;")
            else:
                lbl.setText("⚠ No configurado")
                lbl.setStyleSheet("color: #ffb74d; font-size: 12px;")

    # ── Helpers de diálogo ──────────────────────────────────────────────────────

    def _browse_dir(self, inp: QLineEdit):
        start = inp.text() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Seleccionar directorio", start)
        if path:
            inp.setText(path)

    def _browse_file(self, inp: QLineEdit, hint: str, filt: str):
        start = os.path.dirname(inp.text()) if inp.text() else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, f"Seleccionar {hint}", start, filt)
        if path:
            inp.setText(path)

    def get_config(self) -> dict:
        return self.config


# ─── Pestaña de configuración ─────────────────────────────────────────────────

class ConfigurationTab(TabModule):
    tab_title = "⚙ Configuración"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config: dict         = {}
        self._scan_worker: Optional[ScanWorker] = None
        self._on_complete_cb: Optional[Callable] = None
        self._main_widget: Optional[QWidget] = None

    # ── API pública ────────────────────────────────────────────────────────────

    def run_setup_wizard(self, config: dict, on_complete: Optional[Callable] = None):
        """Lanza el asistente modal si la configuración está incompleta."""
        self._config = dict(config)
        self._on_complete_cb = on_complete

        wizard = SetupWizard(self._config, parent=self.parent)
        result = wizard.exec()

        if result == QDialog.DialogCode.Accepted:
            self._config = wizard.get_config()
            if self._on_complete_cb:
                self._on_complete_cb(self._config)
        else:
            # El usuario cerró sin completar → aviso pero no bloquea
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
        main_lay = QVBoxLayout(root)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # ── Top bar ─────────────────────────────────────────────────────────
        top = QWidget()
        top.setFixedHeight(56)
        top.setStyleSheet("background: #080a0f; border-bottom: 1px solid #1e2330;")
        t_lay = QHBoxLayout(top)
        t_lay.setContentsMargins(24, 0, 24, 0)

        title_lbl = QLabel("Configuración de rutas y apariencia")
        title_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #c8cdd8;")

        btn_wizard = QPushButton("↺  Lanzar asistente")
        btn_wizard.setObjectName("btn_primary")
        btn_wizard.setFixedWidth(160)
        btn_wizard.setToolTip("Volver a ejecutar el asistente de configuración inicial")
        btn_wizard.clicked.connect(self._relaunch_wizard)

        t_lay.addWidget(title_lbl, 1)
        t_lay.addWidget(btn_wizard)

        # ── Scroll area ──────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(28, 24, 28, 28)
        c_lay.setSpacing(20)

        c_lay.addWidget(self._build_paths_group())
        c_lay.addWidget(self._build_appearance_group())
        c_lay.addWidget(self._build_scan_group())
        c_lay.addStretch()

        scroll.setWidget(content)
        main_lay.addWidget(top)
        main_lay.addWidget(scroll)
        return root

    # ── Grupo: rutas ──────────────────────────────────────────────────────────

    def _build_paths_group(self) -> QGroupBox:
        gb = QGroupBox("Rutas del sistema")
        lay = QGridLayout(gb)
        lay.setSpacing(10)
        lay.setColumnMinimumWidth(0, 180)
        lay.setColumnStretch(1, 1)

        defs = [
            ("hyperspin_dir",       "Directorio HyperSpin",       True,  ""),
            ("hyperspin_exe",       "HyperSpin.exe",               False, "Ejecutables (*.exe)"),
            ("rocketlauncher_dir",  "Directorio RocketLauncher",   True,  ""),
            ("rocketlauncherui_dir","Directorio RLUI",             True,  ""),
            ("rocketlauncherui_exe","RocketLauncherUI.exe",        False, "Ejecutables (*.exe)"),
        ]

        self._path_inputs: dict[str, QLineEdit] = {}
        for row_i, (key, label, is_dir, filt) in enumerate(defs):
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("color: #5a6278; font-size: 12px; font-weight: 600;")

            inp = QLineEdit(self._config.get(key, ""))
            inp.setPlaceholderText("(no configurado)")
            self._path_inputs[key] = inp
            if key in ("rocketlauncherui_dir", "rocketlauncherui_exe"):
                inp.textChanged.connect(self._autodetect_paths_from_rlui_fields)

            btn = QPushButton("…")
            btn.setFixedWidth(32)
            btn.setFixedHeight(32)
            btn.setToolTip("Examinar")
            if is_dir:
                btn.clicked.connect(lambda _, i=inp: self._browse_dir(i))
            else:
                btn.clicked.connect(lambda _, i=inp, f=filt: self._browse_file(i, f))

            lay.addWidget(lbl, row_i, 0, Qt.AlignmentFlag.AlignVCenter)
            lay.addWidget(inp, row_i, 1)
            lay.addWidget(btn, row_i, 2)

        btn_validate = QPushButton("Validar rutas")
        btn_validate.clicked.connect(self._validate_paths)
        self.lbl_rlui_autodetect = QLabel("")
        self.lbl_rlui_autodetect.setWordWrap(True)
        self.lbl_rlui_autodetect.setStyleSheet("color: #4a6080; font-size: 12px;")
        self.lbl_validate_result = QLabel("")
        self.lbl_validate_result.setWordWrap(True)

        lay.addWidget(self.lbl_rlui_autodetect, len(defs), 0, 1, 3)
        lay.addWidget(btn_validate, len(defs) + 1, 1, 1, 2)
        lay.addWidget(self.lbl_validate_result, len(defs) + 2, 0, 1, 3)
        self._autodetect_paths_from_rlui_fields()
        return gb

    # ── Grupo: apariencia ─────────────────────────────────────────────────────

    def _build_appearance_group(self) -> QGroupBox:
        gb = QGroupBox("Apariencia")
        lay = QGridLayout(gb)
        lay.setSpacing(10)
        lay.setColumnMinimumWidth(0, 180)
        lay.setColumnStretch(1, 1)

        # Tamaño de fuente
        lbl_fs = QLabel("Tamaño de fuente:")
        lbl_fs.setStyleSheet("color: #5a6278; font-size: 12px; font-weight: 600;")
        self.cmb_fontsize = QComboBox()
        for sz in ["11", "12", "13", "14", "15"]:
            self.cmb_fontsize.addItem(sz + " px", sz)
        saved_fs = str(self.config_val("font_size", "13"))
        idx = self.cmb_fontsize.findData(saved_fs)
        if idx >= 0:
            self.cmb_fontsize.setCurrentIndex(idx)

        # Color de acento
        lbl_accent = QLabel("Color de acento:")
        lbl_accent.setStyleSheet("color: #5a6278; font-size: 12px; font-weight: 600;")
        self.cmb_accent = QComboBox()
        accents = [
            ("Azul cian (por defecto)", "#4fc3f7"),
            ("Verde lima",              "#69f0ae"),
            ("Naranja ámbar",           "#ffb74d"),
            ("Magenta",                 "#f48fb1"),
            ("Violeta",                 "#b39ddb"),
        ]
        for name, val in accents:
            self.cmb_accent.addItem(name, val)
        saved_ac = self.config_val("accent_color", "#4fc3f7")
        idx_ac = self.cmb_accent.findData(saved_ac)
        if idx_ac >= 0:
            self.cmb_accent.setCurrentIndex(idx_ac)

        btn_apply = QPushButton("Aplicar apariencia")
        btn_apply.setObjectName("btn_primary")
        btn_apply.clicked.connect(self._apply_appearance)

        lay.addWidget(lbl_fs,             0, 0)
        lay.addWidget(self.cmb_fontsize,  0, 1)
        lay.addWidget(lbl_accent,         1, 0)
        lay.addWidget(self.cmb_accent,    1, 1)
        lay.addWidget(btn_apply,          2, 1)
        return gb

    # ── Grupo: escaneo ────────────────────────────────────────────────────────

    def _build_scan_group(self) -> QGroupBox:
        gb = QGroupBox("Escaneo de directorios")
        lay = QVBoxLayout(gb)
        lay.setSpacing(10)

        desc = QLabel(
            "Escanea recursivamente los directorios configurados para detectar "
            "sistemas, bases de datos XML, módulos y carpetas de media."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #5a6278; font-size: 12px;")

        self.btn_scan = QPushButton("▶  Iniciar escaneo")
        self.btn_scan.setObjectName("btn_primary")
        self.btn_scan.setFixedWidth(160)
        self.btn_scan.clicked.connect(self._start_scan)

        self.scan_progress = QProgressBar()
        self.scan_progress.setValue(0)
        self.scan_progress.setFixedHeight(6)
        self.scan_progress.hide()

        self.lbl_scan_status = QLabel("")
        self.lbl_scan_status.setStyleSheet("color: #4a6080; font-size: 12px;")

        self.lbl_scan_results = QLabel("")
        self.lbl_scan_results.setWordWrap(True)
        self.lbl_scan_results.setStyleSheet(
            "color: #3a4a68; font-size: 12px; "
            "background: #0a0d12; border: 1px solid #1e2330; "
            "border-radius: 6px; padding: 10px;"
        )
        self.lbl_scan_results.hide()

        lay.addWidget(desc)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_scan)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addWidget(self.scan_progress)
        lay.addWidget(self.lbl_scan_status)
        lay.addWidget(self.lbl_scan_results)
        return gb

    # ── Lógica de la pestaña ──────────────────────────────────────────────────

    def _refresh_fields(self):
        for key, inp in self._path_inputs.items():
            inp.setText(self._config.get(key, ""))

    def _collect_fields(self):
        for key, inp in self._path_inputs.items():
            self._config[key] = inp.text().strip()
        detected = _detect_rocketlauncher_from_rlui(
            self._config.get("rocketlauncherui_exe", ""),
            self._config.get("rocketlauncherui_dir", ""),
        )
        self._config["rocketlauncherui_ini"] = detected.get("rocketlauncherui_ini", "")

    def _autodetect_paths_from_rlui_fields(self):
        if not hasattr(self, "_path_inputs"):
            return
        inp_rlui = self._path_inputs.get("rocketlauncherui_exe")
        inp_rlui_dir = self._path_inputs.get("rocketlauncherui_dir")
        inp_rl = self._path_inputs.get("rocketlauncher_dir")
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
            self.lbl_rlui_autodetect.setText(msg)
            self.lbl_rlui_autodetect.setStyleSheet(
                f"color: {'#69f0ae' if msg.startswith('✓') else '#ffb74d'}; font-size: 12px;")
        elif inp_rlui.text().strip() or inp_rlui_dir.text().strip():
            self.lbl_rlui_autodetect.setText("⚠ No se pudo autodetectar RocketLauncher desde RLUI.")
            self.lbl_rlui_autodetect.setStyleSheet("color: #ffb74d; font-size: 12px;")
        else:
            self.lbl_rlui_autodetect.setText("")

    def config_val(self, key: str, default=None):
        return self._config.get(key, default)

    def _relaunch_wizard(self):
        """Permite al usuario volver a ejecutar el asistente de configuración."""
        reply = QMessageBox.question(
            self.parent, "Relanzar asistente",
            "¿Deseas volver a ejecutar el asistente de configuración inicial?\n"
            "Los valores actuales se usarán como punto de partida.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._collect_fields()
            self.run_setup_wizard(self._config, on_complete=self._on_wizard_done)

    def _on_wizard_done(self, new_cfg: dict):
        self._config.update(new_cfg)
        self._refresh_fields()
        if self.parent:
            self.parent.statusBar().showMessage(
                "✓ Configuración actualizada mediante asistente.", 5000)

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
            self.lbl_validate_result.setText("✗ " + "  |  ".join(errors))
            self.lbl_validate_result.setStyleSheet("color: #ef9a9a; font-size: 12px;")
        else:
            self.lbl_validate_result.setText("✓ Todas las rutas son válidas.")
            self.lbl_validate_result.setStyleSheet("color: #69f0ae; font-size: 12px;")

    def _apply_appearance(self):
        fs = self.cmb_fontsize.currentData()
        accent = self.cmb_accent.currentData()
        self._config["font_size"]    = fs
        self._config["accent_color"] = accent

        # Modificar QSS base con el color de acento y tamaño de fuente elegidos
        try:
            from main import BASE_QSS
            custom_qss = BASE_QSS.replace("#4fc3f7", accent).replace(
                "font-size: 13px;", f"font-size: {fs}px;")
            QApplication.instance().setStyleSheet(custom_qss)
            if self.parent:
                self.parent.statusBar().showMessage(
                    f"✓ Apariencia aplicada — acento {accent}, fuente {fs}px", 4000)
        except Exception as e:
            print(f"[WARN] No se pudo aplicar apariencia: {e}")

    def _start_scan(self):
        self._collect_fields()
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("Escaneando…")
        self.scan_progress.show()
        self.scan_progress.setValue(0)
        self.lbl_scan_results.hide()
        self.lbl_scan_status.setText("Iniciando escaneo…")

        self._scan_worker = ScanWorker(self._config)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_progress(self, pct: int, msg: str):
        self.scan_progress.setValue(pct)
        self.lbl_scan_status.setText(msg)

    def _on_scan_finished(self, results: dict):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("▶  Iniciar escaneo")
        self.scan_progress.hide()
        self.lbl_scan_status.setText("")

        systems  = len(results.get("systems", []))
        dbs      = len(results.get("databases", []))
        modules  = len(results.get("modules", []))
        media    = len(results.get("media_dirs", []))

        text = (
            f"<b>Resultado del escaneo:</b><br><br>"
            f"🎮  <b>{systems}</b> sistemas encontrados en HyperSpin<br>"
            f"🗃  <b>{dbs}</b> bases de datos XML<br>"
            f"⚙  <b>{modules}</b> módulos de RocketLauncher<br>"
            f"🖼  <b>{media}</b> carpetas de media<br>"
        )
        if results.get("systems"):
            preview = ", ".join(results["systems"][:8])
            if systems > 8:
                preview += f" … (+{systems-8} más)"
            text += f"<br><span style='color:#3a4a68;'>Sistemas: {preview}</span>"

        self.lbl_scan_results.setText(text)
        self.lbl_scan_results.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_scan_results.show()

        # Guardar resultados del escaneo en config
        self._config["scan_results"] = results
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ Escaneo completado — {systems} sistemas, {modules} módulos", 5000)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse_dir(self, inp: QLineEdit):
        start = inp.text() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self.parent, "Seleccionar directorio", start)
        if path:
            inp.setText(path)

    def _browse_file(self, inp: QLineEdit, filt: str):
        start = os.path.dirname(inp.text()) if inp.text() else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Seleccionar archivo", start, filt)
        if path:
            inp.setText(path)
