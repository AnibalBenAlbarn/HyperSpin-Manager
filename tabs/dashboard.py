"""
tabs/dashboard.py
DashboardTab — Ejemplo de módulo de pestaña (plugin demo)
Muestra un resumen del estado del sistema.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

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


def _stat_card(value: str, label: str, color: str = "#4fc3f7") -> QFrame:
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: #0a0d12;
            border: 1px solid #1e2330;
            border-radius: 10px;
        }}
    """)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    card.setFixedHeight(90)

    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 14, 18, 14)
    lay.setSpacing(4)

    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {color};")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

    lbl_lbl = QLabel(label)
    lbl_lbl.setStyleSheet("font-size: 11px; color: #3a4a68; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;")

    lay.addWidget(val_lbl)
    lay.addWidget(lbl_lbl)
    return card


class DashboardTab(TabModule):
    tab_title = "🏠 Dashboard"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config = {}
        self._card_values = {}
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

    def _build(self) -> QWidget:
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(24)

        # Título
        title = QLabel("Dashboard")
        title.setObjectName("label_title")
        sub = QLabel("Estado general de tu configuración HyperSpin + RocketLauncher")
        sub.setObjectName("label_subtitle")

        # Cards de estado
        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        self._card_systems  = _stat_card("—", "Sistemas",  "#4fc3f7")
        self._card_games    = _stat_card("—", "Juegos", "#69f0ae")
        self._card_wheel    = _stat_card("—", "% Wheel", "#ffb74d")
        self._card_video    = _stat_card("—", "% Video", "#ef9a9a")
        self._card_theme    = _stat_card("—", "% Theme", "#ba68c8")
        self._card_bezel    = _stat_card("—", "% Bezel", "#80cbc4")

        for c in [self._card_systems, self._card_games, self._card_wheel,
                  self._card_video, self._card_theme, self._card_bezel]:
            cards_row.addWidget(c)

        # Sección de rutas configuradas
        self._info_lbl = QLabel("Configura las rutas en la pestaña ⚙ Configuración para ver el resumen aquí.")
        self._info_lbl.setStyleSheet("color: #3a4a68; font-size: 13px;")
        self._info_lbl.setWordWrap(True)
        self._scan_status = QLabel("")
        self._scan_status.setStyleSheet("color: #7185aa; font-size: 12px;")

        self._incomplete = QTextEdit()
        self._incomplete.setReadOnly(True)
        self._incomplete.setFixedHeight(170)
        self._incomplete.setStyleSheet("background:#0a0d12; border:1px solid #1e2330; border-radius:8px; color:#8ca0c8;")
        self._incomplete.setPlaceholderText("Aquí aparecerán los sistemas con media incompleta.")

        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(4)
        lay.addLayout(cards_row)
        lay.addWidget(self._scan_status)
        lay.addWidget(self._info_lbl)
        lay.addWidget(QLabel("Sistemas con media incompleta:"))
        lay.addWidget(self._incomplete)
        lay.addStretch()
        return root

    def _refresh(self):
        has_config = bool(
            self._config.get("hyperspin_dir") and
            self._config.get("rocketlauncher_dir")
        )

        if has_config:
            self._scan_status.setText("Escaneando Databases y media…")
            self._info_lbl.setText(
                f"HyperSpin: {self._config.get('hyperspin_dir', '')}\n"
                f"RocketLauncher: {self._config.get('rocketlauncher_dir', '')}"
            )
            self._info_lbl.setStyleSheet("color: #4a6080; font-size: 12px;")
            self._start_worker()
        else:
            self._scan_status.setText("Config incompleta: define rutas para calcular estadísticas.")
            self._incomplete.setPlainText("")

    def _update_card(self, card: QFrame, value: str, label: str, color: str):
        labels = card.findChildren(QLabel)
        if len(labels) >= 2:
            labels[0].setText(value)
            labels[0].setStyleSheet(f"font-size: 26px; font-weight: 800; color: {color};")
            labels[1].setText(label)

    def _start_worker(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = DashboardScanWorker(self._config)
        self._worker.progress.connect(self._on_scan_progress)
        self._worker.done.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_progress(self, pct: int, msg: str):
        self._scan_status.setText(f"{msg} ({pct}%)")

    def _on_scan_done(self, data: dict):
        self._update_card(self._card_systems, str(data.get("systems", 0)), "Sistemas", "#4fc3f7")
        self._update_card(self._card_games, str(data.get("games", 0)), "Juegos", "#69f0ae")
        self._update_card(self._card_wheel, f"{data.get('wheel_pct', 0.0):.1f}%", "% Wheel", "#ffb74d")
        self._update_card(self._card_video, f"{data.get('video_pct', 0.0):.1f}%", "% Video", "#ef9a9a")
        self._update_card(self._card_theme, f"{data.get('theme_pct', 0.0):.1f}%", "% Theme", "#ba68c8")
        self._update_card(self._card_bezel, f"{data.get('bezel_pct', 0.0):.1f}%", "% Bezel", "#80cbc4")

        incomplete = data.get("incomplete_systems", [])
        if incomplete:
            lines = [
                f"• {row['system']}: {row['missing_count']}/{row['total']} juegos con media crítica faltante"
                for row in incomplete[:30]
            ]
            self._incomplete.setPlainText("\n".join(lines))
        else:
            self._incomplete.setPlainText("No se detectaron sistemas con media crítica incompleta.")
        self._scan_status.setText("Dashboard actualizado.")


class DashboardScanWorker(QThread):
    progress = pyqtSignal(int, str)
    done = pyqtSignal(dict)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def run(self):
        data = collect_dashboard_stats(self.config, progress_cb=lambda pct, msg: self.progress.emit(pct, msg))
        self.done.emit(data)
