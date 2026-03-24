"""
tabs/dashboard.py
DashboardTab — Panel de estado general con diseño premium.
"""

import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QPushButton, QScrollArea,
    QGridLayout, QProgressBar, QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

from core.dashboard_stats import collect_dashboard_stats

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


# ─── Paleta de colores ────────────────────────────────────────────────────────
_AMBER  = "#f5a623"
_CYAN   = "#00c9e8"
_GREEN  = "#00e599"
_RED    = "#ff4d6a"
_PURPLE = "#a78bfa"

_CARD_BG     = "#07090f"
_CARD_BORDER = "#1a2035"
_PANEL_BG    = "#0a0d14"
_DEEP        = "#05070b"
_TEXT_HI     = "#e8edf8"
_TEXT_MID    = "#8a9ab8"
_TEXT_LOW    = "#4a5878"
_TEXT_GHOST  = "#2a3450"
_MONO        = "'Consolas', 'Courier New', monospace"


# ─── Helpers de estilo ────────────────────────────────────────────────────────

def _css_card(border_accent: str = "") -> str:
    border = f"border-left: 3px solid {border_accent}; border-top: 1px solid {_CARD_BORDER}; border-right: 1px solid {_CARD_BORDER}; border-bottom: 1px solid {_CARD_BORDER};" if border_accent else f"border: 1px solid {_CARD_BORDER};"
    return f"""
        QFrame {{
            background: {_CARD_BG};
            {border}
            border-radius: 8px;
        }}
    """


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {_CARD_BORDER}; border: none;")
    return f


# ─── Componente: StatCard ─────────────────────────────────────────────────────

class StatCard(QFrame):
    """Tarjeta de estadística con valor grande, label y barra de progreso opcional."""

    def __init__(self, label: str, value: str = "—",
                 color: str = _AMBER, icon: str = "",
                 show_bar: bool = False, parent=None):
        super().__init__(parent)
        self._color = color
        self._show_bar = show_bar
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(100)
        self.setStyleSheet(_css_card(border_accent=color))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(4)

        # Fila superior: icono + label
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        if icon:
            ico = QLabel(icon)
            ico.setFixedSize(16, 16)
            ico.setStyleSheet(f"font-size: 14px; color: {color}; background: transparent;")
            top_row.addWidget(ico)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 800; letter-spacing: 1.4px; "
            f"color: {_TEXT_GHOST}; font-family: {_MONO}; background: transparent;")
        top_row.addWidget(lbl)
        top_row.addStretch()

        # Valor
        self._val_lbl = QLabel(value)
        self._val_lbl.setStyleSheet(
            f"font-size: 28px; font-weight: 800; color: {color}; "
            f"letter-spacing: -0.5px; background: transparent;")

        lay.addLayout(top_row)
        lay.addWidget(self._val_lbl)

        if show_bar:
            self._bar = QProgressBar()
            self._bar.setValue(0)
            self._bar.setFixedHeight(3)
            self._bar.setTextVisible(False)
            self._bar.setStyleSheet(f"""
                QProgressBar {{
                    background: {_CARD_BORDER};
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 2px;
                }}
            """)
            lay.addWidget(self._bar)

    def set_value(self, value: str, pct: float = 0.0):
        self._val_lbl.setText(value)
        if self._show_bar and hasattr(self, "_bar"):
            self._bar.setValue(int(min(100, max(0, pct))))


# ─── Componente: PathIndicator ────────────────────────────────────────────────

class PathIndicator(QWidget):
    """Fila que muestra una ruta con icono de estado."""

    def __init__(self, label: str, path: str = "", parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(12)
        self._dot.setStyleSheet(f"font-size: 8px; color: {_TEXT_GHOST}; background: transparent;")

        lbl = QLabel(label)
        lbl.setFixedWidth(160)
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {_TEXT_LOW}; background: transparent;")

        self._path_lbl = QLabel(path or "(no configurado)")
        self._path_lbl.setStyleSheet(
            f"font-size: 11px; font-family: {_MONO}; color: {_TEXT_LOW}; background: transparent;")
        self._path_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._path_lbl.setWordWrap(False)

        lay.addWidget(self._dot)
        lay.addWidget(lbl)
        lay.addWidget(self._path_lbl, 1)

        self.set_path(path)

    def set_path(self, path: str):
        if not path:
            self._path_lbl.setText("(no configurado)")
            self._dot.setStyleSheet(f"font-size: 8px; color: {_TEXT_GHOST}; background: transparent;")
            self._path_lbl.setStyleSheet(
                f"font-size: 11px; font-family: {_MONO}; color: {_TEXT_GHOST}; background: transparent;")
        elif os.path.exists(path):
            short = path if len(path) <= 60 else "…" + path[-57:]
            self._path_lbl.setText(short)
            self._path_lbl.setToolTip(path)
            self._dot.setStyleSheet(f"font-size: 8px; color: {_GREEN}; background: transparent;")
            self._path_lbl.setStyleSheet(
                f"font-size: 11px; font-family: {_MONO}; color: {_TEXT_MID}; background: transparent;")
        else:
            short = path if len(path) <= 60 else "…" + path[-57:]
            self._path_lbl.setText(short)
            self._path_lbl.setToolTip(path)
            self._dot.setStyleSheet(f"font-size: 8px; color: {_RED}; background: transparent;")
            self._path_lbl.setStyleSheet(
                f"font-size: 11px; font-family: {_MONO}; color: {_RED}; background: transparent;")


# ─── Componente: IncompleteRow ────────────────────────────────────────────────

class IncompleteRow(QWidget):
    """Fila de sistema incompleto con mini-barra de progreso."""

    def __init__(self, system: str, missing: int, total: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(10)

        pct = int((total - missing) * 100 / max(total, 1))
        color = _RED if pct < 50 else (_AMBER if pct < 80 else _GREEN)

        name_lbl = QLabel(system)
        name_lbl.setFixedWidth(200)
        name_lbl.setStyleSheet(
            f"font-size: 11px; color: {_TEXT_MID}; background: transparent;")

        bar = QProgressBar()
        bar.setValue(pct)
        bar.setFixedHeight(4)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background: {_CARD_BORDER};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 2px;
            }}
        """)

        pct_lbl = QLabel(f"{pct}%")
        pct_lbl.setFixedWidth(40)
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pct_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; font-family: {_MONO}; "
            f"color: {color}; background: transparent;")

        miss_lbl = QLabel(f"{missing}/{total} faltante{'s' if missing != 1 else ''}")
        miss_lbl.setFixedWidth(100)
        miss_lbl.setStyleSheet(
            f"font-size: 10px; color: {_TEXT_GHOST}; font-family: {_MONO}; background: transparent;")

        lay.addWidget(name_lbl)
        lay.addWidget(bar, 1)
        lay.addWidget(pct_lbl)
        lay.addWidget(miss_lbl)


# ─── DashboardTab ─────────────────────────────────────────────────────────────

class DashboardTab(TabModule):
    tab_title = "🏠 Dashboard"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config = {}
        self._main_widget = None
        self._worker = None

    def widget(self) -> QWidget:
        if self._main_widget is None:
            self._main_widget = self._build()
        return self._main_widget

    def load_data(self, config: dict):
        self._config = config
        if self._main_widget:
            self._refresh()

    def save_data(self) -> dict:
        return {}

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(f"background: {_DEEP};")
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        root_lay.addWidget(self._build_topbar())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {_DEEP}; border: none;")

        body = QWidget()
        body.setStyleSheet(f"background: {_DEEP};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 24, 24, 28)
        body_lay.setSpacing(20)

        body_lay.addLayout(self._build_stat_cards())
        body_lay.addWidget(self._build_progress_row())
        body_lay.addWidget(self._build_paths_panel())
        body_lay.addWidget(self._build_incomplete_panel())
        body_lay.addStretch()

        scroll.setWidget(body)
        root_lay.addWidget(scroll, 1)
        root_lay.addWidget(self._build_statusbar_widget())
        return root

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(64)
        bar.setStyleSheet(f"background: {_DEEP}; border-bottom: 1px solid {_CARD_BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(16)

        # Título con punto de acento
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        dot = QLabel("●")
        dot.setStyleSheet(f"font-size: 10px; color: {_AMBER}; background: transparent;")
        title = QLabel("Dashboard")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {_TEXT_HI}; "
            f"letter-spacing: -0.3px; background: transparent;")
        sub = QLabel("Estado general del sistema")
        sub.setStyleSheet(
            f"font-size: 12px; color: {_TEXT_GHOST}; background: transparent;")
        title_row.addWidget(dot)
        title_row.addWidget(title)
        title_row.addSpacing(8)
        title_row.addWidget(sub)
        title_row.addStretch()

        # Botón refresh
        btn_refresh = QPushButton("⟳  Actualizar")
        btn_refresh.setObjectName("btn_primary")
        btn_refresh.setFixedHeight(32)
        btn_refresh.setFixedWidth(130)
        btn_refresh.clicked.connect(self._on_refresh_click)

        lay.addLayout(title_row, 1)
        lay.addWidget(btn_refresh)
        return bar

    def _build_stat_cards(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._card_systems = StatCard("Sistemas",  "—", _CYAN,   icon="", show_bar=False)
        self._card_games   = StatCard("Juegos",    "—", _AMBER,  icon="", show_bar=False)
        self._card_wheel   = StatCard("Wheel",     "—", _GREEN,  icon="", show_bar=True)
        self._card_video   = StatCard("Video",     "—", _RED,    icon="", show_bar=True)
        self._card_theme   = StatCard("Themes",    "—", _PURPLE, icon="", show_bar=True)
        self._card_bezel   = StatCard("Bezels RL", "—", _AMBER,  icon="", show_bar=True)

        for c in [self._card_systems, self._card_games, self._card_wheel,
                  self._card_video, self._card_theme, self._card_bezel]:
            row.addWidget(c)
        return row

    def _build_progress_row(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._scan_lbl = QLabel("Sin escanear")
        self._scan_lbl.setStyleSheet(
            f"font-size: 11px; font-family: {_MONO}; color: {_TEXT_GHOST}; background: transparent;")

        self._scan_bar = QProgressBar()
        self._scan_bar.setValue(0)
        self._scan_bar.setFixedHeight(3)
        self._scan_bar.setTextVisible(False)
        self._scan_bar.hide()
        self._scan_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {_CARD_BORDER};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #c4841a, stop:0.5 {_AMBER}, stop:1 #ffbe4d);
                border-radius: 2px;
            }}
        """)

        lay.addWidget(self._scan_bar, 1)
        lay.addWidget(self._scan_lbl)
        return w

    def _build_paths_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(_css_card())
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background: {_PANEL_BG}; border-radius: 8px 8px 0 0; border-bottom: 1px solid {_CARD_BORDER};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        hdr_lbl = QLabel("RUTAS CONFIGURADAS")
        hdr_lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 800; letter-spacing: 1.6px; "
            f"color: {_TEXT_GHOST}; font-family: {_MONO}; background: transparent;")
        hdr_lay.addWidget(hdr_lbl)
        hdr_lay.addStretch()

        paths_w = QWidget()
        paths_w.setStyleSheet("background: transparent;")
        paths_lay = QVBoxLayout(paths_w)
        paths_lay.setContentsMargins(4, 8, 4, 8)
        paths_lay.setSpacing(0)

        self._pi_hs   = PathIndicator("HyperSpin")
        self._pi_rl   = PathIndicator("RocketLauncher")
        self._pi_rlui = PathIndicator("RocketLauncherUI")
        self._pi_exe  = PathIndicator("HyperSpin.exe")

        for pi in [self._pi_hs, self._pi_rl, self._pi_rlui, self._pi_exe]:
            paths_lay.addWidget(pi)

        lay.addWidget(hdr)
        lay.addWidget(paths_w)
        return panel

    def _build_incomplete_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(_css_card())
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background: {_PANEL_BG}; border-radius: 8px 8px 0 0; border-bottom: 1px solid {_CARD_BORDER};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        hdr_lbl = QLabel("SISTEMAS CON MEDIA INCOMPLETA")
        hdr_lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 800; letter-spacing: 1.6px; "
            f"color: {_TEXT_GHOST}; font-family: {_MONO}; background: transparent;")
        self._incomplete_count = QLabel("")
        self._incomplete_count.setStyleSheet(
            f"font-size: 10px; font-family: {_MONO}; color: {_AMBER}; background: transparent;")
        hdr_lay.addWidget(hdr_lbl)
        hdr_lay.addStretch()
        hdr_lay.addWidget(self._incomplete_count)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFixedHeight(200)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._incomplete_w = QWidget()
        self._incomplete_w.setStyleSheet("background: transparent;")
        self._incomplete_lay = QVBoxLayout(self._incomplete_w)
        self._incomplete_lay.setContentsMargins(0, 4, 0, 4)
        self._incomplete_lay.setSpacing(0)

        placeholder = QLabel("Sin datos — pulsa Actualizar para escanear.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"font-size: 12px; color: {_TEXT_GHOST}; padding: 24px; background: transparent;")
        self._incomplete_lay.addWidget(placeholder)
        self._incomplete_placeholder = placeholder

        scroll.setWidget(self._incomplete_w)
        lay.addWidget(hdr)
        lay.addWidget(scroll)
        return panel

    def _build_statusbar_widget(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(
            f"background: #03050a; border-top: 1px solid #111520;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(20)

        self._status_items = []
        for _ in range(4):
            lbl = QLabel("")
            lbl.setStyleSheet(
                f"font-size: 10px; font-family: {_MONO}; "
                f"color: {_TEXT_GHOST}; background: transparent;")
            lay.addWidget(lbl)
            self._status_items.append(lbl)
        lay.addStretch()
        return bar

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _refresh(self):
        cfg = self._config
        # Actualizar indicadores de ruta
        self._pi_hs.set_path(cfg.get("hyperspin_dir", ""))
        self._pi_rl.set_path(cfg.get("rocketlauncher_dir", ""))
        self._pi_rlui.set_path(cfg.get("rocketlauncherui_dir", ""))
        self._pi_exe.set_path(cfg.get("hyperspin_exe", ""))

        has_config = bool(cfg.get("hyperspin_dir") and cfg.get("rocketlauncher_dir"))
        if has_config:
            self._scan_bar.show()
            self._scan_bar.setValue(0)
            self._scan_lbl.setText("Iniciando escaneo…")
            self._scan_lbl.setStyleSheet(
                f"font-size: 11px; font-family: {_MONO}; color: {_AMBER}; background: transparent;")
            self._start_worker()
        else:
            self._scan_lbl.setText("Config incompleta — configura las rutas en ⚙ Configuración")
            self._scan_lbl.setStyleSheet(
                f"font-size: 11px; font-family: {_MONO}; color: {_RED}; background: transparent;")

    def _on_refresh_click(self):
        self._refresh()

    def _start_worker(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = DashboardScanWorker(self._config)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.done.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_progress(self, pct: int, msg: str):
        self._scan_bar.setValue(pct)
        short = msg[:60] + "…" if len(msg) > 60 else msg
        self._scan_lbl.setText(short)

    def _on_scan_done(self, data: dict):
        self._scan_bar.hide()
        systems = data.get("systems", 0)
        games   = data.get("games",   0)
        w_pct   = data.get("wheel_pct", 0.0)
        v_pct   = data.get("video_pct", 0.0)
        t_pct   = data.get("theme_pct", 0.0)
        b_pct   = data.get("bezel_pct", 0.0)

        self._card_systems.set_value(str(systems))
        self._card_games.set_value(str(games))
        self._card_wheel.set_value(f"{w_pct:.1f}%", w_pct)
        self._card_video.set_value(f"{v_pct:.1f}%", v_pct)
        self._card_theme.set_value(f"{t_pct:.1f}%", t_pct)
        self._card_bezel.set_value(f"{b_pct:.1f}%", b_pct)

        # Status bar inferior
        status_vals = [
            f"{systems} sistemas",
            f"{games:,} juegos",
            f"Wheel {w_pct:.1f}%",
            f"Video {v_pct:.1f}%",
        ]
        for lbl, txt in zip(self._status_items, status_vals):
            lbl.setText(txt)

        self._scan_lbl.setText("Escaneo completado")
        self._scan_lbl.setStyleSheet(
            f"font-size: 11px; font-family: {_MONO}; color: {_GREEN}; background: transparent;")

        # Panel incompletos
        incomplete = data.get("incomplete_systems", [])
        self._incomplete_count.setText(f"{len(incomplete)} sistema{'s' if len(incomplete) != 1 else ''}")

        # Limpiar panel
        while self._incomplete_lay.count():
            item = self._incomplete_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if incomplete:
            for row in incomplete[:40]:
                r = IncompleteRow(row["system"], row["missing_count"], row["total"])
                self._incomplete_lay.addWidget(r)
                # separador
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {_CARD_BORDER}; border: none;")
                self._incomplete_lay.addWidget(sep)
        else:
            ok_lbl = QLabel("✓  Todos los sistemas tienen media completa")
            ok_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ok_lbl.setStyleSheet(
                f"font-size: 13px; font-weight: 600; color: {_GREEN}; "
                f"padding: 32px; background: transparent;")
            self._incomplete_lay.addWidget(ok_lbl)

        self._incomplete_lay.addStretch()

        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓  Dashboard actualizado — {systems} sistemas, {games:,} juegos", 6000)


# ─── Worker ───────────────────────────────────────────────────────────────────

class DashboardScanWorker(QThread):
    progress = pyqtSignal(int, str)
    done     = pyqtSignal(dict)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def run(self):
        data = collect_dashboard_stats(
            self.config,
            progress_cb=lambda pct, msg: self.progress.emit(pct, msg)
        )
        self.done.emit(data)
