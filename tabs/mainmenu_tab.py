"""
tabs/mainmenu_tab.py
MainMenuTab — Pestaña independiente para gestión del Main Menu de HyperSpin.
Extraído de SystemManagerTab para tener acceso directo desde la barra principal.
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QSplitter, QGroupBox,
    QInputDialog, QMessageBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush

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

_AMBER  = "#f5a623"
_CYAN   = "#00c9e8"
_GREEN  = "#00e599"
_RED    = "#ff4d6a"
_DEEP   = "#05070b"
_BASE   = "#090c12"
_RAISED = "#0d1018"
_CARD   = "#0a0d14"
_BORDER = "#1a2035"
_TXT_HI = "#e8edf8"
_TXT_MD = "#8a9ab8"
_TXT_LO = "#4a5878"
_TXT_GH = "#2a3450"
_MONO   = "'Consolas', 'Courier New', monospace"


class MainMenuTab(TabModule):
    tab_title = "📚 Main Menu"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config = {}
        self._main_widget = None

    def widget(self) -> QWidget:
        if self._main_widget is None:
            self._main_widget = self._build()
        return self._main_widget

    def load_data(self, config: dict):
        self._config = config
        if self._main_widget:
            QTimer.singleShot(0, self._refresh)

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
        root_lay.addWidget(self._build_status_bar())
        root_lay.addWidget(self._build_body(), 1)
        return root

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet(
            f"background: {_DEEP}; border-bottom: 1px solid {_BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet(
            f"font-size: 10px; color: {_AMBER}; background: transparent;")
        title = QLabel("Main Menu")
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_TXT_HI}; "
            f"background: transparent; letter-spacing: -0.2px;")
        sub = QLabel("Categorías, sub-wheels y conversión de XMLs")
        sub.setStyleSheet(
            f"font-size: 11px; color: {_TXT_GH}; "
            f"background: transparent; font-family: {_MONO};")

        self.btn_mm_refresh = QPushButton("⟳  Recargar")
        self.btn_mm_refresh.setObjectName("btn_primary")
        self.btn_mm_refresh.setFixedHeight(32)
        self.btn_mm_refresh.clicked.connect(self._refresh)

        lay.addWidget(dot)
        lay.addWidget(title)
        lay.addSpacing(10)
        lay.addWidget(sub)
        lay.addStretch()
        lay.addWidget(self.btn_mm_refresh)
        return bar

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            f"background: {_RAISED}; border-bottom: 1px solid {_BORDER};")
        bar.setFixedHeight(40)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(20)

        self.lbl_mm_status = QLabel("Sin datos — pulsa Recargar")
        self.lbl_mm_status.setWordWrap(True)
        self.lbl_mm_status.setStyleSheet(
            f"font-size: 11px; color: {_TXT_LO}; background: transparent; "
            f"font-family: {_MONO};")

        self.btn_mm_to_mmc = QPushButton("Main Menu.xml → All/Categories")
        self.btn_mm_to_classic = QPushButton("All/Categories → Main Menu.xml")
        self.btn_mm_sync = QPushButton("Sincronizar categorías")

        for b in [self.btn_mm_to_mmc, self.btn_mm_to_classic, self.btn_mm_sync]:
            b.setFixedHeight(28)
            b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.btn_mm_to_mmc.clicked.connect(self._mainmenu_convert_to_mmc)
        self.btn_mm_to_classic.clicked.connect(self._mainmenu_convert_to_classic)
        self.btn_mm_sync.clicked.connect(self._mainmenu_sync_categories)

        lay.addWidget(self.lbl_mm_status, 1)
        lay.addWidget(self.btn_mm_to_mmc)
        lay.addWidget(self.btn_mm_to_classic)
        lay.addWidget(self.btn_mm_sync)
        return bar

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet(f"background: {_BASE};")
        lay = QHBoxLayout(body)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(16)

        # ── Panel categorías ──────────────────────────────────────────────────
        cat_panel = QFrame()
        cat_panel.setStyleSheet(
            f"QFrame {{ background: {_CARD}; border: 1px solid {_BORDER}; "
            f"border-radius: 10px; }}")
        cat_lay = QVBoxLayout(cat_panel)
        cat_lay.setContentsMargins(0, 0, 0, 0)
        cat_lay.setSpacing(0)

        cat_hdr = self._panel_header("CATEGORÍAS (CATEGORIES.XML)")
        cat_lay.addWidget(cat_hdr)

        self.lst_mm_categories = QListWidget()
        self.lst_mm_categories.setStyleSheet(
            f"QListWidget {{ background: {_CARD}; border: none; border-radius: 0 0 10px 10px; "
            f"outline: none; }}"
            f"QListWidget::item {{ padding: 6px 14px; color: {_TXT_MD}; "
            f"border-bottom: 1px solid {_BORDER}; }}"
            f"QListWidget::item:hover {{ background: {_RAISED}; color: {_TXT_HI}; }}"
            f"QListWidget::item:selected {{ background: #0d1a2a; color: {_AMBER}; }}")
        cat_lay.addWidget(self.lst_mm_categories, 1)

        # Botones de categorías
        cat_btns = QWidget()
        cat_btns.setStyleSheet(
            f"background: {_RAISED}; border-top: 1px solid {_BORDER}; "
            f"border-radius: 0 0 10px 10px;")
        cb_lay = QHBoxLayout(cat_btns)
        cb_lay.setContentsMargins(12, 8, 12, 8)
        cb_lay.setSpacing(8)

        btn_cat_add = QPushButton("+ Añadir")
        btn_cat_add.setObjectName("btn_success")
        btn_cat_add.clicked.connect(self._mainmenu_add_category)
        btn_cat_del = QPushButton("− Quitar")
        btn_cat_del.setObjectName("btn_danger")
        btn_cat_del.clicked.connect(self._mainmenu_remove_category)
        btn_cat_up = QPushButton("↑")
        btn_cat_up.setFixedWidth(36)
        btn_cat_up.clicked.connect(lambda: self._mainmenu_reorder_categories(-1))
        btn_cat_down = QPushButton("↓")
        btn_cat_down.setFixedWidth(36)
        btn_cat_down.clicked.connect(lambda: self._mainmenu_reorder_categories(1))

        for b in [btn_cat_add, btn_cat_del, btn_cat_up, btn_cat_down]:
            b.setFixedHeight(28)
            cb_lay.addWidget(b)
        cb_lay.addStretch()
        cat_lay.addWidget(cat_btns)

        # ── Panel sub-wheels ──────────────────────────────────────────────────
        sw_panel = QFrame()
        sw_panel.setStyleSheet(
            f"QFrame {{ background: {_CARD}; border: 1px solid {_BORDER}; "
            f"border-radius: 10px; }}")
        sw_lay = QVBoxLayout(sw_panel)
        sw_lay.setContentsMargins(0, 0, 0, 0)
        sw_lay.setSpacing(0)

        sw_hdr = self._panel_header("SUB-WHEELS DETECTADOS")
        sw_lay.addWidget(sw_hdr)

        self.lst_mm_subwheels = QListWidget()
        self.lst_mm_subwheels.setStyleSheet(
            f"QListWidget {{ background: {_CARD}; border: none; border-radius: 0 0 10px 10px; "
            f"outline: none; }}"
            f"QListWidget::item {{ padding: 6px 14px; color: {_TXT_MD}; "
            f"border-bottom: 1px solid {_BORDER}; }}"
            f"QListWidget::item:hover {{ background: {_RAISED}; color: {_TXT_HI}; }}"
            f"QListWidget::item:selected {{ background: #0d1a2a; color: {_CYAN}; }}")
        sw_lay.addWidget(self.lst_mm_subwheels, 1)

        lay.addWidget(cat_panel, 3)
        lay.addWidget(sw_panel, 2)
        return body

    def _panel_header(self, title: str) -> QWidget:
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background: {_RAISED}; border-radius: 10px 10px 0 0; "
            f"border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 800; letter-spacing: 1.6px; "
            f"color: {_TXT_GH}; font-family: {_MONO}; background: transparent;")
        hl.addWidget(lbl)
        hl.addStretch()
        return hdr

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _get_info(self):
        hs_dir  = self._config.get("hyperspin_dir", "")
        mmc_dir = self._config.get("mainmenuchanger_dir", "")
        return mainmenu_utils.detect_mainmenu(hs_dir, mmc_dir)

    def _refresh(self):
        if not hasattr(self, "lst_mm_categories"):
            return
        info = self._get_info()
        if not info.hs_dir or not os.path.isdir(info.hs_dir):
            self.lbl_mm_status.setText("HyperSpin no configurado — ve a ⚙ Configuración")
            self.lbl_mm_status.setStyleSheet(
                f"font-size: 11px; color: {_RED}; background: transparent; "
                f"font-family: {_MONO};")
            return

        summary = info.summary() if hasattr(info, "summary") else str(info)
        self.lbl_mm_status.setText(summary)
        self.lbl_mm_status.setStyleSheet(
            f"font-size: 11px; color: {_TXT_LO}; background: transparent; "
            f"font-family: {_MONO};")

        self.lst_mm_categories.clear()
        self.lst_mm_subwheels.clear()

        if info.has_categories_xml:
            _, categories = mainmenu_utils.parse_hyperspin_xml(info.categories_xml)
            for cat in categories:
                self.lst_mm_categories.addItem(cat.get("name", ""))

        for sw in mainmenu_utils.list_subwheels(info):
            name  = sw.get("name", "")
            count = sw.get("count", 0)
            item_text = f"{name}  ({count} sistemas)"
            self.lst_mm_subwheels.addItem(item_text)

        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ Main Menu actualizado — {self.lst_mm_categories.count()} categorías, "
                f"{self.lst_mm_subwheels.count()} sub-wheels", 5000)

    def _mainmenu_add_category(self):
        info = self._get_info()
        name, ok = QInputDialog.getText(
            self.parent, "Nueva categoría", "Nombre de la categoría:")
        if not ok or not name.strip():
            return
        name = name.strip()
        genre, _ = QInputDialog.getText(
            self.parent, "Nueva categoría", "Valor de género (opcional):")
        if mainmenu_utils.add_category(info, name, genre.strip()):
            self._refresh()
        else:
            QMessageBox.warning(self.parent, "Error",
                                "No se pudo crear la categoría.")

    def _mainmenu_remove_category(self):
        current = self.lst_mm_categories.currentItem()
        if not current:
            return
        name = current.text()
        ok = QMessageBox.question(
            self.parent, "Quitar categoría",
            f"¿Eliminar la categoría '{name}' de Categories.xml?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if ok != QMessageBox.Yes:
            return
        info = self._get_info()
        if mainmenu_utils.remove_category(info, name):
            self._refresh()
        else:
            QMessageBox.warning(self.parent, "Error",
                                f"No se pudo eliminar '{name}'.")

    def _mainmenu_reorder_categories(self, delta: int):
        row    = self.lst_mm_categories.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.lst_mm_categories.count():
            return
        item = self.lst_mm_categories.takeItem(row)
        self.lst_mm_categories.insertItem(target, item)
        self.lst_mm_categories.setCurrentRow(target)
        names = [
            self.lst_mm_categories.item(i).text()
            for i in range(self.lst_mm_categories.count())
        ]
        info = self._get_info()
        if not mainmenu_utils.reorder_categories(info, names):
            QMessageBox.warning(self.parent, "Error",
                                "No se pudo guardar el nuevo orden.")

    def _mainmenu_convert_to_mmc(self):
        info   = self._get_info()
        result = mainmenu_utils.main_menu_xml_to_all_and_categories(
            info, overwrite=False)
        if result.success:
            QMessageBox.information(self.parent, "Conversión completada",
                                    result.summary())
            self._refresh()
        else:
            QMessageBox.warning(self.parent, "Error",
                                result.error or "Falló la conversión.")

    def _mainmenu_convert_to_classic(self):
        info   = self._get_info()
        result = mainmenu_utils.all_and_categories_to_main_menu_xml(
            info, use_all_xml=True, overwrite=True)
        if result.success:
            QMessageBox.information(self.parent, "Conversión completada",
                                    result.summary())
            self._refresh()
        else:
            QMessageBox.warning(self.parent, "Error",
                                result.error or "Falló la conversión.")

    def _mainmenu_sync_categories(self):
        info = self._get_info()
        sync = mainmenu_utils.sync_categories_with_all(info)
        if "error" in sync:
            QMessageBox.warning(self.parent, "Error", sync["error"])
            return
        created = 0
        for genre in sync.get("genres_without_category", []):
            if mainmenu_utils.add_category(info, genre, genre):
                created += 1
        orphans = len(sync.get("orphan_categories", []))
        QMessageBox.information(
            self.parent, "Sincronización completada",
            f"Categorías creadas: {created}\n"
            f"Categorías huérfanas (sin sistemas): {orphans}")
        self._refresh()
