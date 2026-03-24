"""
HyperSpin & RocketLauncher Manager
main.py — Punto de entrada y orquestador de pestañas

PESTAÑAS DE LA APLICACIÓN (en orden de aparición):
────────────────────────────────────────────────────
  1. 🏠 Dashboard       — Estado general, resumen de configuración y escaneo
  2. ⚙ Configuración   — Asistente inicial + rutas + apariencia + escaneo
  3. 🗂 Sistemas        — Gestor, auditor, diff XML, juegos + ⚙ INI Audit integrado
  4. ➕ Crear sistema   — Asistente para añadir nuevos sistemas completos
  5. 🎮 Controles       — Editor visual de perfiles arcade/gamepad (drag & drop)

FLUJO DE INICIO:
  - Si config.json no existe o está incompleto → wizard modal antes de mostrar pestañas
  - Si config.json está completo → carga directa de todas las pestañas
  - Cada pestaña recibe load_data(config) al iniciar y al recargar
  - closeEvent recoge save_data() de cada pestaña y guarda config.json
"""

import sys
import os
import json
import traceback
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QLabel, QMessageBox, QStatusBar,
    QAction, QMenu, QMenuBar
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

# ─── Constantes ───────────────────────────────────────────────────────────────
APP_NAME    = "HyperSpin Manager"
APP_VERSION = "1.0.0"
CONFIG_FILE = "config.json"
TABS_DIR    = Path(__file__).parent / "tabs"
ASSETS_DIR  = Path(__file__).parent / "assets"
QSS_DIR     = ASSETS_DIR / "qss"
LOG_FILE    = Path(__file__).parent / "hyperspin_manager.log"

# Orden explícito de carga de módulos — (archivo, clase)
TAB_MANIFEST = [
    ("dashboard.py",         "DashboardTab"),
    ("system_manager_ui.py", "SystemManagerTab"),
    ("mainmenu_tab.py",      "MainMenuTab"),
    ("create_system.py",     "CreateSystemTab"),
    ("controls.py",          "ControlsTab"),
    ("configuration.py",     "ConfigurationTab"),
]

# Claves obligatorias para considerar la config completa
CONFIG_REQUIRED_KEYS = [
    "hyperspin_dir",
    "rocketlauncher_dir",
    "rocketlauncherui_dir",
    "hyperspin_exe",
]
DEFAULT_UI_STATE = {
    "window_width": 1280,
    "window_height": 800,
    "window_x": None,
    "window_y": None,
    "active_tab": 0,
}

# ─── QSS Global (tema oscuro) ──────────────────────────────────────────────────
BASE_QSS = """
QWidget {
    background-color: #0d0f14;
    color: #c8cdd8;
    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
    font-size: 13px;
}
QMainWindow { background-color: #0d0f14; }

/* ── MENÚ ── */
QMenuBar {
    background-color: #12151c;
    border-bottom: 1px solid #1e2330;
    padding: 2px 6px;
    spacing: 4px;
}
QMenuBar::item {
    background: transparent;
    padding: 5px 12px;
    border-radius: 4px;
    color: #8892a4;
}
QMenuBar::item:selected, QMenuBar::item:pressed {
    background-color: #1e2330;
    color: #e8ecf4;
}
QMenu {
    background-color: #12151c;
    border: 1px solid #1e2330;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
    color: #8892a4;
}
QMenu::item:selected { background-color: #1e2330; color: #e8ecf4; }
QMenu::separator { height: 1px; background: #1e2330; margin: 3px 8px; }

/* ── TAB WIDGET ── */
QTabWidget::pane { border: none; background-color: #0d0f14; }
QTabWidget::tab-bar { alignment: left; }
QTabBar { background: #12151c; border-bottom: 2px solid #1e2330; }
QTabBar::tab {
    background: transparent;
    color: #5a6278;
    padding: 10px 22px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
}
QTabBar::tab:hover { color: #a0aabb; background-color: #161922; }
QTabBar::tab:selected {
    color: #4fc3f7;
    border-bottom: 2px solid #4fc3f7;
    background-color: #0d0f14;
}

/* ── GROUPBOX ── */
QGroupBox {
    border: 1px solid #1e2330;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: #6878a0;
    font-size: 11px;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 14px;
}

/* ── INPUTS ── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #161922;
    border: 1px solid #1e2330;
    border-radius: 6px;
    padding: 7px 10px;
    color: #c8cdd8;
    selection-background-color: #1a4a6e;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #4fc3f7;
    background-color: #12151c;
}
QLineEdit:read-only { background-color: #0d0f14; color: #5a6278; }

/* ── BOTONES ── */
QPushButton {
    background-color: #1e2330;
    color: #8892a4;
    border: 1px solid #2a3045;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton:hover { background-color: #252b3d; color: #c8cdd8; border-color: #3a4560; }
QPushButton:pressed { background-color: #161922; }
QPushButton:disabled { background-color: #12151c; color: #2a3045; border-color: #1e2330; }
QPushButton#btn_primary {
    background-color: #0d4f7a; color: #4fc3f7; border: 1px solid #1a6fa0;
}
QPushButton#btn_primary:hover { background-color: #115e8f; color: #80d8ff; }
QPushButton#btn_primary:disabled { background-color: #0a2a3e; color: #1e4a6e; }
QPushButton#btn_danger {
    background-color: #4a1520; color: #f48fb1; border: 1px solid #6a2535;
}
QPushButton#btn_danger:hover { background-color: #5a1f2a; color: #ff80ab; }
QPushButton#btn_success {
    background-color: #0d4a2e; color: #69f0ae; border: 1px solid #1a6a40;
}
QPushButton#btn_success:hover { background-color: #115a38; }

/* ── COMBO BOX ── */
QComboBox {
    background-color: #161922;
    border: 1px solid #1e2330;
    border-radius: 6px;
    padding: 6px 10px;
    color: #c8cdd8;
    min-width: 120px;
}
QComboBox:focus { border-color: #4fc3f7; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #5a6278;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #12151c;
    border: 1px solid #1e2330;
    selection-background-color: #1a4a6e;
    outline: none;
    padding: 4px;
}

/* ── CHECKBOXES Y RADIO ── */
QCheckBox, QRadioButton { spacing: 8px; color: #8892a4; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px;
    border: 1px solid #2a3045;
    border-radius: 3px;
    background: #161922;
}
QCheckBox::indicator:checked { background: #0d4f7a; border-color: #4fc3f7; }
QRadioButton::indicator { border-radius: 8px; }
QRadioButton::indicator:checked { background: #4fc3f7; border-color: #4fc3f7; }

/* ── SCROLLBARS ── */
QScrollBar:vertical { width: 8px; background: #0d0f14; border-radius: 4px; }
QScrollBar::handle:vertical {
    background: #1e2330; border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: #2a3045; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal { height: 8px; background: #0d0f14; border-radius: 4px; }
QScrollBar::handle:horizontal {
    background: #1e2330; border-radius: 4px; min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: #2a3045; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }

/* ── TABLES ── */
QTableWidget, QTreeWidget, QListWidget {
    background-color: #0d0f14;
    border: 1px solid #1e2330;
    border-radius: 6px;
    gridline-color: #161922;
    outline: none;
}
QTableWidget::item, QTreeWidget::item, QListWidget::item {
    padding: 5px 8px; border: none;
}
QTableWidget::item:selected,
QTreeWidget::item:selected,
QListWidget::item:selected {
    background-color: #0d3a5e; color: #4fc3f7;
}
QHeaderView::section {
    background-color: #12151c;
    border: none;
    border-right: 1px solid #1e2330;
    border-bottom: 1px solid #1e2330;
    padding: 6px 10px;
    color: #5a6278;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── STATUS BAR ── */
QStatusBar {
    background-color: #080a0f;
    color: #3a4560;
    font-size: 11px;
    border-top: 1px solid #1e2330;
    padding: 0 8px;
}
QStatusBar::item { border: none; }

/* ── SPLITTER ── */
QSplitter::handle { background: #1e2330; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical   { height: 1px; }

/* ── TOOLTIPS ── */
QToolTip {
    background-color: #12151c;
    border: 1px solid #2a3045;
    color: #c8cdd8;
    padding: 5px 8px;
    border-radius: 4px;
}

/* ── PROGRESS BAR ── */
QProgressBar {
    background-color: #161922;
    border: 1px solid #1e2330;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #0d4f7a, stop:1 #4fc3f7);
    border-radius: 4px;
}

/* ── LABELS especiales ── */
QLabel#label_title  { font-size: 22px; font-weight: 700; color: #e8ecf4; letter-spacing: -0.5px; }
QLabel#label_subtitle { font-size: 13px; color: #3a4a68; }
QLabel#label_section  { font-size: 11px; font-weight: 700; color: #4fc3f7; letter-spacing: 1.2px; text-transform: uppercase; }
QLabel#label_warning  { color: #ffb74d; font-weight: 600; }
QLabel#label_error    { color: #ef9a9a; font-weight: 600; }
QLabel#label_ok       { color: #69f0ae; font-weight: 600; }

/* ── DIALOG ── */
QDialog { background-color: #0d0f14; }
"""

logger = logging.getLogger("hyperspin_manager")


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


def load_theme_stylesheet(theme: str, custom_qss: str = "") -> str:
    qss_path = QSS_DIR / f"{theme}.qss"
    if qss_path.is_file():
        try:
            content = qss_path.read_text(encoding="utf-8")
            return f"{content}\n{custom_qss}".strip()
        except OSError:
            logger.warning("No se pudo leer QSS '%s'. Usando fallback.", qss_path)
    if theme == "dark":
        return f"{BASE_QSS}\n{custom_qss}".strip()
    return custom_qss or ""


# ─── Utilidades de configuración ──────────────────────────────────────────────

def load_config() -> dict:
    if not Path(CONFIG_FILE).exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except OSError as e:
        logger.error("No se pudo guardar config.json: %s", e)
        return False


def config_is_complete(cfg: dict) -> bool:
    return all(cfg.get(k) for k in CONFIG_REQUIRED_KEYS)


# ─── Clase base TabModule ──────────────────────────────────────────────────────

class TabModule:
    """
    Clase base que deben heredar todos los módulos de pestaña.

    Implementar:
        tab_title: str           — Texto de la pestaña
        widget() → QWidget       — Contenido de la pestaña
        load_data(cfg: dict)     — Recibe config actualizado
        save_data() → dict       — Devuelve cambios a persistir (o {})
    """
    tab_title: str = "Módulo"
    tab_icon:  str = ""

    def __init__(self, parent: "MainWindow"):
        self.parent = parent

    def widget(self) -> QWidget:
        raise NotImplementedError

    def load_data(self, config: dict):
        pass

    def save_data(self) -> dict:
        return {}


# ─── Cargador de módulos ──────────────────────────────────────────────────────

def load_tab_module(filename: str, classname: str) -> type:
    """
    Importa una clase de módulo desde tabs/<filename>.
    Lanza ImportError si no se puede cargar.
    """
    import importlib.util
    py_file = TABS_DIR / filename
    if not py_file.exists():
        raise ImportError(f"Archivo no encontrado: {py_file}")

    spec = importlib.util.spec_from_file_location(
        f"tabs.{py_file.stem}", py_file)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cls = getattr(mod, classname, None)
    if cls is None:
        raise ImportError(f"Clase '{classname}' no encontrada en {filename}")
    return cls


# ─── Ventana principal ────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.config:   dict  = {}
        self.modules:  list  = []   # instancias de TabModule, en orden
        self._widgets: dict  = {}   # tab_title → QWidget

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(QSize(1100, 720))
        self.resize(1280, 800)

        self._build_menu()
        self._build_tabs()
        self._build_statusbar()
        self._load_and_distribute()

    # ── Construcción UI ────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = QMenuBar(self)

        # — Archivo —
        m_file = QMenu("&Archivo", self)

        act_save = QAction("Guardar configuración", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._on_save)

        act_reload = QAction("Recargar configuración", self)
        act_reload.setShortcut("F5")
        act_reload.triggered.connect(self._on_reload)

        act_exit = QAction("Salir", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)

        m_file.addAction(act_save)
        m_file.addAction(act_reload)
        m_file.addSeparator()
        m_file.addAction(act_exit)

        # — Vista —
        m_view = QMenu("&Vista", self)

        act_dark = QAction("Tema oscuro", self)
        act_dark.triggered.connect(lambda: self._apply_theme("dark"))
        act_light = QAction("Tema claro", self)
        act_light.triggered.connect(lambda: self._apply_theme("light"))

        act_goto = QMenu("Ir a pestaña", self)
        # Las acciones se añaden dinámicamente tras cargar módulos
        self._menu_goto = act_goto

        m_view.addAction(act_dark)
        m_view.addAction(act_light)
        m_view.addMenu(act_goto)

        # — Herramientas —
        m_tools = QMenu("&Herramientas", self)

        act_open_hs = QAction("Abrir directorio HyperSpin", self)
        act_open_hs.triggered.connect(lambda: self._open_dir("hyperspin_dir"))
        act_open_rl = QAction("Abrir directorio RocketLauncher", self)
        act_open_rl.triggered.connect(lambda: self._open_dir("rocketlauncher_dir"))

        act_edit_cfg = QAction("Editar config.json", self)
        act_edit_cfg.triggered.connect(self._edit_config_json)

        m_tools.addAction(act_open_hs)
        m_tools.addAction(act_open_rl)
        m_tools.addSeparator()
        m_tools.addAction(act_edit_cfg)

        # — Ayuda —
        m_help = QMenu("A&yuda", self)

        act_about = QAction(f"Acerca de {APP_NAME}", self)
        act_about.triggered.connect(self._on_about)
        act_tabs  = QAction("Lista de pestañas", self)
        act_tabs.triggered.connect(self._on_list_tabs)

        m_help.addAction(act_tabs)
        m_help.addSeparator()
        m_help.addAction(act_about)

        mb.addMenu(m_file)
        mb.addMenu(m_view)
        mb.addMenu(m_tools)
        mb.addMenu(m_help)
        self.setMenuBar(mb)

    def _build_tabs(self):
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setDocumentMode(True)
        self.setCentralWidget(self.tab_widget)

    def _build_statusbar(self):
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        sb.showMessage(f"{APP_NAME} v{APP_VERSION}  —  Iniciando…", 5000)

    # ── Carga de módulos ───────────────────────────────────────────────────────

    def _load_and_distribute(self):
        """
        Flujo de inicio:
          1. Leer config.json
          2. Si incompleto → wizard modal (solo ConfigurationTab)
          3. Cargar todos los módulos del TAB_MANIFEST en orden
          4. Distribuir config a todos
        """
        self.config = load_config()
        config_ok   = config_is_complete(self.config)

        # Si la config no está completa, lanzar el wizard ANTES de cargar el resto
        wizard_done = False
        if not config_ok:
            wizard_done = self._run_setup_wizard()

        # Cargar todos los módulos del manifest
        self._load_all_modules()

        # Distribuir config a todos los módulos
        self._distribute_config()

        # Añadir accesos rápidos en menú Vista → Ir a pestaña
        self._populate_goto_menu()
        self._restore_ui_state()

        if config_ok or wizard_done:
            self.statusBar().showMessage(
                f"✓ {APP_NAME} v{APP_VERSION}  —  {len(self.modules)} módulos cargados", 6000)
        else:
            self.statusBar().showMessage(
                f"⚠ Configuración incompleta — ve a ⚙ Configuración", 8000)

    def _run_setup_wizard(self) -> bool:
        """
        Carga ConfigurationTab y lanza el wizard modal.
        Devuelve True si el usuario completó la configuración.
        """
        try:
            CfgClass = load_tab_module("configuration.py", "ConfigurationTab")
            instance = CfgClass(parent=self)
            # El wizard modifica self.config directamente vía callback
            instance.run_setup_wizard(self.config, on_complete=self._on_wizard_complete)
            return config_is_complete(self.config)
        except Exception as e:
            QMessageBox.critical(
                self, "Error en configuración inicial",
                f"No se pudo cargar el asistente de configuración:\n{e}")
            return False

    def _on_wizard_complete(self, new_cfg: dict):
        """Callback del wizard — actualiza config y lo persiste."""
        self.config.update(new_cfg)
        save_config(self.config)
        self.statusBar().showMessage("✓ Configuración inicial guardada.", 5000)

    def _load_all_modules(self):
        """
        Carga todos los módulos del TAB_MANIFEST en el orden definido.
        Si un módulo falla → pestaña de error pero continúa.
        Evita duplicados por tab_title.
        """
        loaded_titles = {m.tab_title for m in self.modules}

        for filename, classname in TAB_MANIFEST:
            try:
                cls      = load_tab_module(filename, classname)
                instance = cls(parent=self)

                if instance.tab_title in loaded_titles:
                    continue  # ya cargado (p.ej. ConfigurationTab desde wizard)

                loaded_titles.add(instance.tab_title)
                self.modules.append(instance)
                self._register_tab(instance)

            except Exception as e:
                tb = traceback.format_exc()
                logger.error("Error cargando %s/%s:\n%s", filename, classname, tb)
                self._register_error_tab(
                    f"{classname} ({filename})", str(e))

    def _register_tab(self, instance: TabModule):
        """Crea el widget y lo añade al QTabWidget."""
        try:
            w = instance.widget()
            self._widgets[instance.tab_title] = w
            self.tab_widget.addTab(w, instance.tab_title)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("Error en widget() de '%s':\n%s", instance.tab_title, tb)
            self._register_error_tab(instance.tab_title, str(e))

    def _register_error_tab(self, name: str, error: str):
        """Pestaña de error visible al usuario cuando un módulo falla."""
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)

        lbl_icon  = QLabel("⚠")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("font-size:42px; color:#ffb74d;")

        lbl_title = QLabel(f"Error al cargar: {name}")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("font-size:15px; font-weight:700; color:#ffb74d;")

        lbl_err   = QLabel(error[:300])
        lbl_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_err.setStyleSheet("color:#5a6278; font-size:11px; padding:0 60px;")
        lbl_err.setWordWrap(True)

        lbl_hint  = QLabel(
            "Revisa la consola para el traceback completo.\n"
            "El resto de la aplicación sigue funcionando.")
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_hint.setStyleSheet("color:#3a4560; font-size:11px;")

        lay.addWidget(lbl_icon)
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_err)
        lay.addWidget(lbl_hint)
        self.tab_widget.addTab(w, f"⚠ {name[:20]}")

    # ── Distribución de configuración ─────────────────────────────────────────

    def _distribute_config(self):
        """Envía el config actual a cada módulo."""
        for module in self.modules:
            try:
                module.load_data(self.config)
            except Exception as e:
                logger.warning("load_data en '%s': %s", module.tab_title, e)

    # ── Menú → Ir a pestaña ───────────────────────────────────────────────────

    def _populate_goto_menu(self):
        self._menu_goto.clear()
        for i, module in enumerate(self.modules):
            act = QAction(f"  {module.tab_title}", self)
            act.setShortcut(f"Ctrl+{i+1}") if i < 9 else None
            idx = i  # captura por valor
            act.triggered.connect(lambda _, n=idx: self.tab_widget.setCurrentIndex(n))
            self._menu_goto.addAction(act)

    # ── Acciones de menú ──────────────────────────────────────────────────────

    def _on_save(self):
        self._capture_ui_state()
        for module in self.modules:
            try:
                partial = module.save_data()
                if partial:
                    self.config.update(partial)
            except Exception as e:
                logger.warning("save_data en '%s': %s", module.tab_title, e)

        if save_config(self.config):
            self.statusBar().showMessage("✓ Configuración guardada en config.json", 4000)
        else:
            self.statusBar().showMessage("✗ Error al guardar config.json", 4000)

    def _on_reload(self):
        self.config = load_config()
        self._distribute_config()
        self.statusBar().showMessage("↻ Configuración recargada desde disco.", 3000)

    def _apply_theme(self, theme: str):
        custom = self.config.get("theme_qss", "")
        app = QApplication.instance()
        app.setStyleSheet(load_theme_stylesheet(theme, custom))
        self.config["theme"] = theme
        self.statusBar().showMessage(f"Tema {theme} aplicado.", 3000)

    def _open_dir(self, config_key: str):
        """Abre el explorador de archivos en el directorio configurado."""
        path = self.config.get(config_key, "")
        if not path or not os.path.isdir(path):
            self.statusBar().showMessage(
                f"Directorio '{config_key}' no configurado o no existe.", 4000)
            return
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.statusBar().showMessage(f"No se pudo abrir: {e}", 4000)

    def _edit_config_json(self):
        """Abre config.json en el editor por defecto del sistema."""
        cfg_path = Path(CONFIG_FILE).absolute()
        if not cfg_path.exists():
            self.statusBar().showMessage("config.json no existe todavía.", 4000)
            return
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(str(cfg_path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(cfg_path)])
            else:
                subprocess.Popen(["xdg-open", str(cfg_path)])
        except Exception as e:
            self.statusBar().showMessage(f"No se pudo abrir config.json: {e}", 4000)

    def _on_about(self):
        pestanas = "\n".join(
            f"  {i+1}. {m.tab_title}"
            for i, m in enumerate(self.modules)
        )
        QMessageBox.about(
            self, f"Acerca de {APP_NAME}",
            f"<b>{APP_NAME}</b> v{APP_VERSION}<br><br>"
            f"Gestor modular para HyperSpin y RocketLauncher.<br><br>"
            f"<b>Pestañas cargadas:</b><br>"
            f"<pre>{pestanas}</pre>"
        )

    def _on_list_tabs(self):
        """Muestra la lista completa de pestañas activas."""
        lines = [f"<b>Pestañas de {APP_NAME} v{APP_VERSION}</b><br>"]
        for i, m in enumerate(self.modules):
            lines.append(
                f"<b>{i+1}.</b> {m.tab_title}"
                f"  <span style='color:#3a4560;font-size:11px;'>"
                f"← {m.__class__.__name__} ({m.__class__.__module__})"
                f"</span>"
            )
        msg = QMessageBox(self)
        msg.setWindowTitle("Pestañas activas")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText("<br>".join(lines))
        msg.exec()

    # ── Cierre ────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._on_save()
        event.accept()

    # ── Estado de UI persistente ─────────────────────────────────────────────

    def _capture_ui_state(self):
        self.config["window_width"] = max(self.width(), 800)
        self.config["window_height"] = max(self.height(), 600)
        self.config["window_x"] = self.x()
        self.config["window_y"] = self.y()
        self.config["active_tab"] = self.tab_widget.currentIndex()

    def _restore_ui_state(self):
        state = dict(DEFAULT_UI_STATE)
        state.update({k: self.config.get(k) for k in DEFAULT_UI_STATE.keys() if k in self.config})

        width = int(state.get("window_width") or DEFAULT_UI_STATE["window_width"])
        height = int(state.get("window_height") or DEFAULT_UI_STATE["window_height"])
        self.resize(max(width, 1100), max(height, 720))

        pos_x = state.get("window_x")
        pos_y = state.get("window_y")
        if isinstance(pos_x, int) and isinstance(pos_y, int):
            self.move(pos_x, pos_y)

        active_tab = state.get("active_tab", 0)
        if isinstance(active_tab, int) and 0 <= active_tab < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(active_tab)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    cfg = load_config()
    setup_logging(bool(cfg.get("debug_logging", False)))

    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(load_theme_stylesheet(cfg.get("theme", "dark"), cfg.get("theme_qss", "")))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
