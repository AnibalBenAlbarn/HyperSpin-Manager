"""
tabs/dashboard.py
DashboardTab — Ejemplo de módulo de pestaña (plugin demo)
Muestra un resumen del estado del sistema.
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QSizePolicy, QPushButton
)
from PyQt5.QtCore import Qt

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
    val_lbl.setAlignment(Qt.AlignLeft)

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
        self._card_modules  = _stat_card("—", "Módulos RL","#69f0ae")
        self._card_dbs      = _stat_card("—", "Bases de datos", "#ffb74d")
        self._card_status   = _stat_card("⚠", "Estado config", "#ef9a9a")

        for c in [self._card_systems, self._card_modules, self._card_dbs, self._card_status]:
            cards_row.addWidget(c)

        # Sección de rutas configuradas
        self._info_lbl = QLabel("Configura las rutas en la pestaña ⚙ Configuración para ver el resumen aquí.")
        self._info_lbl.setStyleSheet("color: #3a4a68; font-size: 13px;")
        self._info_lbl.setWordWrap(True)

        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(4)
        lay.addLayout(cards_row)
        lay.addWidget(self._info_lbl)
        lay.addStretch()
        return root

    def _refresh(self):
        results = self._config.get("scan_results", {})
        systems = len(results.get("systems", []))
        modules = len(results.get("modules", []))
        dbs     = len(results.get("databases", []))

        has_config = bool(
            self._config.get("hyperspin_dir") and
            self._config.get("rocketlauncher_dir")
        )

        self._update_card(self._card_systems, str(systems) if systems else "—", "Sistemas", "#4fc3f7")
        self._update_card(self._card_modules, str(modules) if modules else "—", "Módulos RL", "#69f0ae")
        self._update_card(self._card_dbs,     str(dbs)     if dbs     else "—", "Bases de datos", "#ffb74d")

        if has_config:
            self._update_card(self._card_status, "✓", "Config OK", "#69f0ae")
            self._info_lbl.setText(
                f"HyperSpin: {self._config.get('hyperspin_dir', '')}\n"
                f"RocketLauncher: {self._config.get('rocketlauncher_dir', '')}"
            )
            self._info_lbl.setStyleSheet("color: #4a6080; font-size: 12px;")
        else:
            self._update_card(self._card_status, "⚠", "Config incompleta", "#ef9a9a")

    def _update_card(self, card: QFrame, value: str, label: str, color: str):
        labels = card.findChildren(QLabel)
        if len(labels) >= 2:
            labels[0].setText(value)
            labels[0].setStyleSheet(f"font-size: 26px; font-weight: 800; color: {color};")
