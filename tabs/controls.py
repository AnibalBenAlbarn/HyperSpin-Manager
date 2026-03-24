"""
tabs/controls.py
ControlsTab — Editor visual de perfiles de control para HyperSpin Manager
"""

import os
import json
import configparser
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QGroupBox, QScrollArea, QFrame, QSplitter,
    QListWidget, QFileDialog, QMessageBox, QInputDialog,
    QSizePolicy, QAbstractItemView, QDialog,
    QDialogButtonBox, QCheckBox, QTextEdit, QButtonGroup,
    QRadioButton, QApplication
)
from PyQt6.QtCore import (
    Qt, QMimeData, QPoint, QRect, QSize,
    pyqtSignal, QTimer
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont,
    QFontMetrics, QDrag, QPainterPath, QPixmap,
    QLinearGradient, QRadialGradient, QPalette,
    QPolygon
)
from tabs.create_system import make_joytokey_cfg

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
_DEEP   = "#05070b"
_BASE   = "#090c12"
_RAISED = "#0d1018"
_CARD   = "#0a0d14"
_BORDER = "#1a2035"
_MID    = "#243050"
_TXT_HI = "#e8edf8"
_TXT_MD = "#b7c5de"
_TXT_LO = "#8fa2c8"
_TXT_GH = "#5e7199"
_MONO   = "'Consolas', 'Courier New', monospace"

# ─── Acciones predefinidas ────────────────────────────────────────────────────

ARCADE_ACTIONS = [
    "Start P1", "Start P2", "Coin P1", "Coin P2",
    "Pause", "Exit", "Config",
    "Button 1", "Button 2", "Button 3", "Button 4",
    "Button 5", "Button 6", "Button 7", "Button 8",
    "Up", "Down", "Left", "Right",
    "Service", "Test", "---",
]

GAMEPAD_ACTIONS = [
    "A / Cross", "B / Circle", "X / Square", "Y / Triangle",
    "L1 / LB", "R1 / RB", "L2 / LT", "R2 / RT",
    "L3 (Stick L)", "R3 (Stick R)",
    "Start", "Select / Back",
    "D-Up", "D-Down", "D-Left", "D-Right",
    "Pause", "Exit", "---",
]

# Colores por acción
ACTION_COLORS = {
    "Start P1": "#1565c0", "Start P2": "#1565c0",
    "Coin P1":  "#4a148c", "Coin P2":  "#4a148c",
    "Pause":    "#1b5e20", "Exit":     "#b71c1c",
    "Config":   "#e65100",
    "Button 1": "#c62828", "Button 2": "#283593",
    "Button 3": "#1b5e20", "Button 4": "#f9a825",
    "Button 5": "#880e4f", "Button 6": "#006064",
    "Button 7": "#37474f", "Button 8": "#4e342e",
    "---":      "#1e2330",
}
DEFAULT_ACTION_COLOR = "#1e3a5f"


def action_color(action: str) -> str:
    if not action or action == "---":
        return "#1e2330"
    return ACTION_COLORS.get(action, DEFAULT_ACTION_COLOR)


# ─── ButtonSlot ───────────────────────────────────────────────────────────────

class ButtonSlot(QWidget):
    assignment_changed = pyqtSignal(str, str)
    CIRCLE = "circle"
    RECT   = "rect"

    def __init__(self, slot_id: str, label: str = "", shape: str = "circle",
                 size: int = 48, parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.label   = label
        self.shape   = shape
        self._size   = size
        self.action  = ""
        self._hover  = False
        self._actions = ARCADE_ACTIONS
        self._custom_fill: Optional[str] = None
        pad = 14 if shape == self.CIRCLE else 8
        self.setFixedSize(size + pad, size + pad)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Slot: {slot_id}\nDoble clic para asignar · Clic derecho para borrar")

    def set_actions(self, actions: list):
        self._actions = actions

    def set_action(self, action: str):
        self.action = action
        self.update()

    def set_custom_fill(self, color: Optional[str]):
        self._custom_fill = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r = self._size // 2

        color_str = self._custom_fill or (action_color(self.action) if self.action else "#182238")
        base = QColor(color_str).lighter(140) if self._hover else QColor(color_str)

        # Sombra
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 100)))
        if self.shape == self.CIRCLE:
            p.drawEllipse(cx - r + 2, cy - r + 2, r * 2, r * 2)
        else:
            p.drawRoundedRect(3, 3, w - 3, h - 3, 6, 6)

        # Cuerpo
        grad = QRadialGradient(cx - r // 3, cy - r // 3, r * 2)
        grad.setColorAt(0, base.lighter(120))
        grad.setColorAt(1, base)
        p.setBrush(QBrush(grad))
        border_color = QColor(_AMBER) if self._hover else QColor(_BORDER)
        p.setPen(QPen(border_color, 1.5))
        if self.shape == self.CIRCLE:
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        else:
            p.drawRoundedRect(2, 2, w - 4, h - 4, 6, 6)

        # Label del slot (esquina superior)
        if self.label:
            p.setFont(QFont("Consolas", 8, QFont.Bold))
            p.setPen(QPen(QColor(_TXT_MD)))
            p.drawText(QRect(0, 2, w, 12), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self.label)

        # Acción asignada
        if self.action and self.action != "---":
            p.setFont(QFont("Segoe UI", 8, QFont.Bold))
            p.setPen(QPen(QColor(_TXT_HI)))
            rect = QRect(cx - r + 3, cy - 11, r * 2 - 6, 22)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.action[:14])
        else:
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QPen(QColor(_TXT_LO)))
            p.drawText(QRect(cx - r, cy - 8, r * 2, 16), Qt.AlignmentFlag.AlignCenter, "—")

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self._hover = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._hover = False
        self.update()

    def dropEvent(self, event):
        self._hover = False
        self.set_action(event.mimeData().text())
        self.assignment_changed.emit(self.slot_id, self.action)
        event.acceptProposedAction()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            action, ok = QInputDialog.getItem(
                self, f"Asignar — {self.slot_id}", "Acción:",
                [a for a in self._actions], 0, False)
            if ok and action:
                self.set_action(action)
                self.assignment_changed.emit(self.slot_id, action)

    def contextMenuEvent(self, event):
        self.set_action("")
        self.assignment_changed.emit(self.slot_id, "")


# ─── DraggableActionItem ──────────────────────────────────────────────────────

class DraggableActionItem(QWidget):
    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(8)

        dot = QLabel("●")
        dot.setFixedWidth(10)
        dot.setStyleSheet(
            f"font-size: 8px; color: {action_color(action)}; background: transparent;")

        lbl = QLabel(action)
        lbl.setStyleSheet(
            f"font-size: 12px; color: {_TXT_MD}; background: transparent;")

        lay.addWidget(dot)
        lay.addWidget(lbl)
        lay.addStretch()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.action)
            drag.setMimeData(mime)
            pix = QPixmap(170, 30)
            pix.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(QColor(action_color(self.action))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 170, 30, 5, 5)
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QPen(QColor(_TXT_HI)))
            painter.drawText(QRect(0, 0, 170, 30), Qt.AlignmentFlag.AlignCenter, self.action)
            painter.end()
            drag.setPixmap(pix)
            drag.setHotSpot(event.pos())
            drag.exec(Qt.DropAction.CopyAction)


# ─── ActionPalette ────────────────────────────────────────────────────────────

class ActionPalette(QWidget):
    def __init__(self, actions: list, parent=None):
        super().__init__(parent)
        self.setFixedWidth(170)
        self._build(actions)

    def _build(self, actions: list):
        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QWidget()
        hdr.setFixedHeight(32)
        hdr.setStyleSheet(
            f"background: {_DEEP}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        hdr_lbl = QLabel("ACCIONES")
        hdr_lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; "
            f"color: {_TXT_GH}; font-family: {_MONO}; background: transparent;")
        hl.addWidget(hdr_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {_CARD};")

        content = QWidget()
        content.setStyleSheet(f"background: {_CARD};")
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(4, 4, 4, 4)
        c_lay.setSpacing(2)
        for action in actions:
            c_lay.addWidget(DraggableActionItem(action))
        c_lay.addStretch()
        scroll.setWidget(content)

        lay.addWidget(hdr)
        lay.addWidget(scroll, 1)


# ─── StickCanvas ─────────────────────────────────────────────────────────────

class StickCanvas(QWidget):
    """Canvas dibujado del joystick arcade con gate configurable."""

    GATE_OCTAGONAL = "octagonal"
    GATE_SQUARE    = "square"
    GATE_CIRCULAR  = "circular"

    def __init__(self, accent_color: str = _AMBER, gate: str = GATE_OCTAGONAL, parent=None):
        super().__init__(parent)
        self.accent = QColor(accent_color)
        self._gate = gate
        self.setFixedSize(100, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Clic derecho para cambiar el restrictor de la palanca")

    def set_gate(self, gate: str):
        self._gate = gate
        self.update()

    def set_accent(self, color: str):
        self.accent = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r = 50, 50, 44

        # Gate
        p.setPen(QPen(QColor("#2a2a2a"), 1.5))
        p.setBrush(QBrush(QColor("#0a0a0a")))

        if self._gate == self.GATE_OCTAGONAL:
            gs = 30
            pts = [
                QPoint(cx - gs // 2, cy - gs), QPoint(cx + gs // 2, cy - gs),
                QPoint(cx + gs, cy - gs // 2), QPoint(cx + gs, cy + gs // 2),
                QPoint(cx + gs // 2, cy + gs), QPoint(cx - gs // 2, cy + gs),
                QPoint(cx - gs, cy + gs // 2), QPoint(cx - gs, cy - gs // 2),
            ]
            p.drawPolygon(QPolygon(pts))
        elif self._gate == self.GATE_SQUARE:
            gs = 30
            p.drawRect(cx - gs, cy - gs, gs * 2, gs * 2)
        else:  # circular
            p.drawEllipse(cx - 30, cy - 30, 60, 60)

        # Base del stick
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#1a1a1a")))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Anillo de acento
        p.setPen(QPen(self.accent, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Líneas de dirección
        p.setPen(QPen(QColor("#2a2a2a"), 1))
        p.drawLine(cx, cy - r + 4, cx, cy + r - 4)
        p.drawLine(cx - r + 4, cy, cx + r - 4, cy)

        # Bola
        br = 16
        grad = QRadialGradient(cx - 4, cy - 4, br * 2)
        grad.setColorAt(0, QColor("#555555"))
        grad.setColorAt(1, QColor("#1a1a1a"))
        p.setPen(QPen(QColor("#444444"), 1))
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - br, cy - br, br * 2, br * 2)

        # Label del gate
        p.setFont(QFont("Consolas", 7))
        p.setPen(QPen(QColor(_TXT_GH)))
        gate_txt = {"octagonal": "OCT", "square": "SQR", "circular": "CIR"}.get(self._gate, "")
        p.drawText(QRect(cx - 20, cy + r - 14, 40, 12), Qt.AlignmentFlag.AlignCenter, gate_txt)


# ─── ArcadeLayout ────────────────────────────────────────────────────────────

class ArcadeLayout(QWidget):
    """
    Panel de control arcade para P1 y P2.
    Soporta botonera de 6 (3+3) u 8 (4+4) botones configurables.
    La palanca tiene selector de gate.
    """
    slot_changed = pyqtSignal(str, str)

    MODE_6BTN = 6
    MODE_8BTN = 8

    def __init__(self, btn_mode: int = 8, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._slots:      dict = {}
        self._btn_mode = btn_mode
        self._gate_p1 = StickCanvas.GATE_OCTAGONAL
        self._gate_p2 = StickCanvas.GATE_OCTAGONAL
        self._build()

    def set_btn_mode(self, mode: int):
        """Cambia entre 6 y 8 botones y reconstruye el layout."""
        if mode == self._btn_mode:
            return
        old_assignments = dict(self.assignments)
        self._btn_mode = mode
        # Limpiar layout actual
        lay = self.layout()
        if lay:
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    self._clear_layout(item.layout())
        self._slots = {}
        self.assignments = {}
        self._build()
        # Restaurar assignments compatibles
        for sid, act in old_assignments.items():
            if sid in self._slots:
                self._slots[sid].set_action(act)
                self.assignments[sid] = act

    def _clear_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _build(self):
        self.setStyleSheet(
            f"ArcadeLayout {{ "
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 #161a24,stop:1 #0a0d14); "
            f"border: 2px solid #1e2535; border-radius: 14px; }}")
        self.setMinimumSize(980, 360)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(18, 12, 18, 12)
        main_lay.setSpacing(6)

        # ── Header ────────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(0)

        p1_lbl = QLabel("● PLAYER 1")
        p1_lbl.setStyleSheet(
            f"color: {_AMBER}; font-size: 11px; font-weight: 800; "
            f"letter-spacing: 1.8px; font-family: {_MONO}; background: transparent;")

        mode_lbl = QLabel(f"{'6 BTN' if self._btn_mode == 6 else '8 BTN'} MODE")
        mode_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_lbl.setStyleSheet(
            f"color: {_TXT_GH}; font-size: 9px; font-weight: 700; "
            f"letter-spacing: 1px; font-family: {_MONO}; background: transparent;")

        p2_lbl = QLabel("PLAYER 2 ●")
        p2_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        p2_lbl.setStyleSheet(
            f"color: {_CYAN}; font-size: 11px; font-weight: 800; "
            f"letter-spacing: 1.8px; font-family: {_MONO}; background: transparent;")

        hdr_row.addWidget(p1_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(mode_lbl)
        hdr_row.addStretch()
        hdr_row.addWidget(p2_lbl)

        # ── Contenido ─────────────────────────────────────────────────────────
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        mid_row.addWidget(self._build_player_panel("p1", _AMBER))
        mid_row.addStretch(1)
        mid_row.addWidget(self._build_center_panel())
        mid_row.addStretch(1)
        mid_row.addWidget(self._build_player_panel("p2", _CYAN))

        main_lay.addLayout(hdr_row)
        main_lay.addLayout(mid_row, 1)

    def _build_player_panel(self, player: str, accent: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setSpacing(14)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── Palanca ───────────────────────────────────────────────────────────
        stick_w = QWidget()
        stick_w.setStyleSheet("background: transparent;")
        stick_lay = QVBoxLayout(stick_w)
        stick_lay.setContentsMargins(0, 0, 0, 0)
        stick_lay.setSpacing(4)

        gate_attr = f"_stick_{player}"
        stick = StickCanvas(accent_color=accent, gate=StickCanvas.GATE_OCTAGONAL)
        stick.setObjectName(f"stick_{player}")
        setattr(self, gate_attr, stick)

        # Selector de gate
        gate_cmb = QComboBox()
        gate_cmb.setFixedWidth(100)
        gate_cmb.setFixedHeight(24)
        gate_cmb.addItems(["Octagonal", "Cuadrado", "Circular"])
        gate_cmb.setStyleSheet(
            f"QComboBox {{ background: {_RAISED}; border: 1px solid {_BORDER}; "
            f"border-radius: 4px; color: {_TXT_MD}; font-size: 10px; padding: 2px 6px; }}"
            f"QComboBox::drop-down {{ border: none; width: 18px; }}")
        gate_map = {0: StickCanvas.GATE_OCTAGONAL, 1: StickCanvas.GATE_SQUARE,
                    2: StickCanvas.GATE_CIRCULAR}

        def on_gate_changed(idx, s=stick):
            s.set_gate(gate_map[idx])

        gate_cmb.currentIndexChanged.connect(on_gate_changed)

        # Slots para direcciones
        dirs_row = QHBoxLayout()
        dirs_row.setSpacing(4)
        for sid, arrow in [(f"{player}_up", "↑"), (f"{player}_dn", "↓"),
                            (f"{player}_lt", "←"), (f"{player}_rt", "→")]:
            b = ButtonSlot(sid, arrow, ButtonSlot.RECT, 34)
            b.set_actions(ARCADE_ACTIONS)
            b.assignment_changed.connect(self._on_slot)
            self._slots[sid] = b
            dirs_row.addWidget(b)

        stick_lay.addWidget(stick, 0, Qt.AlignmentFlag.AlignHCenter)
        stick_lay.addWidget(gate_cmb, 0, Qt.AlignmentFlag.AlignHCenter)
        stick_lay.addLayout(dirs_row)

        # ── Botones ───────────────────────────────────────────────────────────
        btn_w = QWidget()
        btn_w.setStyleSheet("background: transparent;")
        btn_lay = QGridLayout(btn_w)
        btn_lay.setSpacing(7)
        btn_lay.setContentsMargins(0, 0, 0, 0)

        if self._btn_mode == 6:
            # 3+3: dos filas de 3 botones (layout Capcom CPS)
            positions = [
                (0, 0, f"{player}_b1"), (1, 0, f"{player}_b2"), (2, 0, f"{player}_b3"),
                (0, 1, f"{player}_b4"), (1, 1, f"{player}_b5"), (2, 1, f"{player}_b6"),
            ]
        else:
            # 4+4: dos filas de 4 botones (layout SNK/Neo Geo)
            positions = [
                (0, 0, f"{player}_b1"), (1, 0, f"{player}_b2"),
                (2, 0, f"{player}_b3"), (3, 0, f"{player}_b4"),
                (0, 1, f"{player}_b5"), (1, 1, f"{player}_b6"),
                (2, 1, f"{player}_b7"), (3, 1, f"{player}_b8"),
            ]

        for col, row, slot_id in positions:
            num = slot_id.split("_b")[1]
            btn = ButtonSlot(slot_id, f"B{num}", ButtonSlot.CIRCLE, 56)
            btn.set_actions(ARCADE_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            btn_lay.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)
            self._slots[slot_id] = btn

        lay.addWidget(stick_w)
        lay.addWidget(btn_w)
        return w

    def _build_center_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(180)
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setSpacing(8)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()

        # Panel negro central con botones de sistema
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: #0a0c10; border: 1px solid {_BORDER}; "
            f"border-radius: 10px; }}")
        p_lay = QVBoxLayout(panel)
        p_lay.setContentsMargins(10, 10, 10, 10)
        p_lay.setSpacing(8)

        rows_def = [
            [("p1_coin", "1P COIN"), ("p1_start", "1P START")],
            [("pause",   "PAUSE"),   ("exit",     "EXIT")],
            [("p2_coin", "2P COIN"), ("p2_start", "2P START")],
        ]
        sizes = [30, 26, 30]

        for row_def, sz in zip(rows_def, sizes):
            rw = QHBoxLayout()
            rw.setSpacing(8)
            rw.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for slot_id, label in row_def:
                btn = ButtonSlot(slot_id, label, ButtonSlot.RECT, sz + 8)
                btn.set_actions(ARCADE_ACTIONS)
                btn.assignment_changed.connect(self._on_slot)
                rw.addWidget(btn)
                self._slots[slot_id] = btn
            p_lay.addLayout(rw)

        lay.addWidget(panel, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()
        return w

    def _on_slot(self, slot_id: str, action: str):
        self.assignments[slot_id] = action
        self.slot_changed.emit(slot_id, action)

    def get_assignments(self) -> dict:
        return dict(self.assignments)

    def set_assignments(self, assignments: dict):
        self.assignments = dict(assignments)
        for sid, slot in self._slots.items():
            slot.set_action(assignments.get(sid, ""))

    def clear_all(self):
        self.assignments = {}
        for slot in self._slots.values():
            slot.set_action("")


# ─── GamepadLayout con imágenes reales ───────────────────────────────────────

class GamepadLayout(QWidget):
    """
    Panel de mando con imagen real PNG.
    Usa Mando_Oscuro.png en tema dark y Mando_claro.png en tema light.
    """
    slot_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._slots:      dict = {}
        self._controller_labels = []
        self._theme = "dark"
        self._build()

    def set_theme(self, theme: str):
        self._theme = theme
        if hasattr(self, "_p1_img"):
            self._update_controller_images()

    def _get_controller_image_path(self) -> str:
        """Retorna la imagen del mando según el tema activo."""
        base = Path(__file__).parent.parent
        # Tema dark → mando claro para contraste; tema light → mando oscuro
        if self._theme == "dark":
            for candidate in [
                base / "assets" / "Mando_claro.png",
                base / "Mando_claro.png",
                "/mnt/user-data/uploads/Mando_claro.png",
            ]:
                if Path(candidate).exists():
                    return str(candidate)
        else:
            for candidate in [
                base / "assets" / "Mando_Oscuro.png",
                base / "Mando_Oscuro.png",
                "/mnt/user-data/uploads/Mando_Oscuro.png",
            ]:
                if Path(candidate).exists():
                    return str(candidate)
        return ""

    def _build(self):
        self.setStyleSheet(
            f"GamepadLayout {{ background: {_BASE}; border: 1px solid {_BORDER}; "
            f"border-radius: 10px; }}")
        self.setMinimumSize(960, 380)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ── Panel izquierdo: LT/LB + D-pad + L-stick click ───────────────────
        left = self._build_left_panel()

        # ── Centro: imagen del mando + select/start ───────────────────────────
        center = self._build_center_panel()

        # ── Panel derecho: RT/RB + botones cara + R-stick click ──────────────
        right = self._build_right_panel()

        root.addLayout(left, 1)
        root.addWidget(center, 3)
        root.addLayout(right, 1)

    def _btn_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 700; letter-spacing: 0.8px; "
            f"color: {_TXT_GH}; background: transparent; font-family: {_MONO};")
        return lbl

    def _build_trigger_row(self, sid: str, label: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lbl = QLabel(label)
        lbl.setFixedWidth(36)
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 800; color: {_TXT_LO}; "
            f"background: transparent; font-family: {_MONO};")
        btn = ButtonSlot(sid, label, ButtonSlot.RECT, 40)
        btn.set_actions(GAMEPAD_ACTIONS)
        btn.assignment_changed.connect(self._on_slot)
        self._slots[sid] = btn
        lay.addWidget(lbl)
        lay.addWidget(btn)
        return w

    def _build_dpad(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background: transparent;")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(3)

        w = QWidget()
        w.setMinimumSize(150, 150)
        w.setStyleSheet("background: transparent;")
        lay = QGridLayout(w)
        lay.setSpacing(2)
        lay.setContentsMargins(4, 4, 4, 4)

        for row, col, sid, arrow in [
            (0, 1, "dpad_up", "↑"), (1, 0, "dpad_left", "←"),
            (1, 2, "dpad_right", "→"), (2, 1, "dpad_down", "↓"),
        ]:
            btn = ButtonSlot(sid, arrow, ButtonSlot.RECT, 38)
            btn.set_actions(GAMEPAD_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            self._slots[sid] = btn
            lay.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        center = QWidget()
        center.setFixedSize(36, 36)
        center.setStyleSheet(f"background: {_RAISED}; border-radius: 4px;")
        lay.addWidget(center, 1, 1)

        ol.addWidget(w)
        ol.addWidget(self._btn_label("D-PAD"))
        return outer

    def _build_face_buttons(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background: transparent;")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(3)

        w = QWidget()
        w.setMinimumSize(150, 150)
        w.setStyleSheet("background: transparent;")
        lay = QGridLayout(w)
        lay.setSpacing(2)
        lay.setContentsMargins(4, 4, 4, 4)

        for row, col, sid, label in [
            (0, 1, "btn_y", "Y"), (1, 0, "btn_x", "X"),
            (1, 2, "btn_b", "B"), (2, 1, "btn_a", "A"),
        ]:
            btn = ButtonSlot(sid, label, ButtonSlot.CIRCLE, 42)
            btn.set_actions(GAMEPAD_ACTIONS)
            face_colors = {
                "btn_a": "#2e7d32",  # A verde
                "btn_b": "#c62828",  # B rojo
                "btn_x": "#1565c0",  # X azul
                "btn_y": "#f9a825",  # Y amarillo
            }
            btn.set_custom_fill(face_colors.get(sid))
            btn.assignment_changed.connect(self._on_slot)
            self._slots[sid] = btn
            lay.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        ol.addWidget(w)
        ol.addWidget(self._btn_label("BOTONES"))
        return outer

    def _build_left_panel(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(8)
        lay.addWidget(self._build_trigger_row("lt", "LT"))
        lay.addWidget(self._build_trigger_row("lb", "LB"))
        lay.addSpacing(12)
        lay.addWidget(self._build_dpad())
        lay.addSpacing(8)

        # L-stick click
        ls_w = QWidget()
        ls_w.setStyleSheet("background: transparent;")
        ls_l = QVBoxLayout(ls_w)
        ls_l.setContentsMargins(0, 0, 0, 0)
        ls_l.setSpacing(3)
        ls_btn = ButtonSlot("ls_click", "L3", ButtonSlot.CIRCLE, 46)
        ls_btn.set_actions(GAMEPAD_ACTIONS)
        ls_btn.assignment_changed.connect(self._on_slot)
        self._slots["ls_click"] = ls_btn
        ls_l.addWidget(ls_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        ls_l.addWidget(self._btn_label("L STICK CLICK"))
        lay.addWidget(ls_w)
        lay.addStretch()
        return lay

    def _build_right_panel(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(8)
        lay.addWidget(self._build_trigger_row("rt", "RT"))
        lay.addWidget(self._build_trigger_row("rb", "RB"))
        lay.addSpacing(12)
        lay.addWidget(self._build_face_buttons())
        lay.addSpacing(8)

        # R-stick click
        rs_w = QWidget()
        rs_w.setStyleSheet("background: transparent;")
        rs_l = QVBoxLayout(rs_w)
        rs_l.setContentsMargins(0, 0, 0, 0)
        rs_l.setSpacing(3)
        rs_btn = ButtonSlot("rs_click", "R3", ButtonSlot.CIRCLE, 46)
        rs_btn.set_actions(GAMEPAD_ACTIONS)
        rs_btn.assignment_changed.connect(self._on_slot)
        self._slots["rs_click"] = rs_btn
        rs_l.addWidget(rs_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        rs_l.addWidget(self._btn_label("R STICK CLICK"))
        lay.addWidget(rs_w)
        lay.addStretch()
        return lay

    def _build_center_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)

        # Fila de mandos P1 y P2
        controllers_row = QHBoxLayout()
        controllers_row.setSpacing(24)
        controllers_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for player, label_text in [("p1", "PLAYER 1"), ("p2", "PLAYER 2")]:
            col_w = QWidget()
            col_w.setStyleSheet("background: transparent;")
            col_l = QVBoxLayout(col_w)
            col_l.setContentsMargins(0, 0, 0, 0)
            col_l.setSpacing(6)
            col_l.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # Imagen del mando
            img_lbl = QLabel()
            img_lbl.setMinimumSize(220, 170)
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setScaledContents(False)
            img_lbl.setStyleSheet("background: transparent;")
            setattr(self, f"_img_lbl_{player}", img_lbl)
            self._controller_labels.append(img_lbl)

            # Label del jugador
            player_lbl = QLabel(label_text)
            player_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = _AMBER if player == "p1" else _CYAN
            player_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 800; color: {color}; "
                f"letter-spacing: 1.5px; background: transparent; font-family: {_MONO};")

            col_l.addWidget(img_lbl)
            col_l.addWidget(player_lbl)
            controllers_row.addWidget(col_w)

        lay.addLayout(controllers_row)

        # Select / Start
        spec_row = QHBoxLayout()
        spec_row.setSpacing(14)
        spec_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for sid, label in [("btn_select", "SELECT"), ("btn_start", "START")]:
            vw = QWidget()
            vw.setStyleSheet("background: transparent;")
            vl = QVBoxLayout(vw)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(3)
            btn = ButtonSlot(sid, label, ButtonSlot.RECT, 34)
            btn.set_actions(GAMEPAD_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            self._slots[sid] = btn
            vl.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            vl.addWidget(self._btn_label(label))
            spec_row.addWidget(vw)
        lay.addLayout(spec_row)

        # Cargar imágenes iniciales
        QTimer.singleShot(100, self._update_controller_images)
        return w

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_controller_images()

    def _update_controller_images(self):
        """Carga y redimensiona la imagen del mando según el tema."""
        img_path = self._get_controller_image_path()
        for player in ["p1", "p2"]:
            lbl = getattr(self, f"_img_lbl_{player}", None)
            if not lbl:
                continue
            if img_path and Path(img_path).exists():
                pix = QPixmap(img_path)
                if not pix.isNull():
                    scaled = pix.scaled(
                        lbl.width(), lbl.height(),
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl.setPixmap(scaled)
                    lbl.setToolTip(f"Mando {player.upper()}")
            else:
                # Fallback: texto
                lbl.setText(f"🎮\n{player.upper()}")
                lbl.setStyleSheet(
                    f"font-size: 32px; color: {_TXT_GH}; background: transparent;")

    def _on_slot(self, slot_id: str, action: str):
        self.assignments[slot_id] = action
        self.slot_changed.emit(slot_id, action)

    def get_assignments(self) -> dict:
        return dict(self.assignments)

    def set_assignments(self, assignments: dict):
        self.assignments = dict(assignments)
        for sid, slot in self._slots.items():
            slot.set_action(assignments.get(sid, ""))

    def clear_all(self):
        self.assignments = {}
        for slot in self._slots.values():
            slot.set_action("")


# ─── ControlsTab ─────────────────────────────────────────────────────────────

class ControlsTab(TabModule):
    tab_title = "🎮 Controles"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config:   dict = {}
        self._systems:  list = []
        self._current_system:  str = ""
        self._current_profile: str = "Default"
        self._current_mode:    str = "arcade"
        self._profiles: dict = {"Default": {}}
        self._main_widget: Optional[QWidget] = None

    def widget(self) -> QWidget:
        if self._main_widget is None:
            self._main_widget = self._build()
        return self._main_widget

    def load_data(self, config: dict):
        self._config = config
        if self._main_widget:
            self._reload_systems()
            # Actualizar imágenes del mando según tema
            theme = config.get("theme", "dark")
            if hasattr(self, "gamepad_layout"):
                self.gamepad_layout.set_theme(theme)

    def save_data(self) -> dict:
        return {}

    # ── Construcción ──────────────────────────────────────────────────────────

    def _build(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(f"background: {_DEEP};")
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        root_lay.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {_BORDER}; }}")

        self._palette = ActionPalette(ARCADE_ACTIONS)
        editor_w = self._build_editor()
        right_panel = self._build_right_panel()

        splitter.addWidget(self._palette)
        splitter.addWidget(editor_w)
        splitter.addWidget(right_panel)
        splitter.setSizes([170, 740, 280])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        root_lay.addWidget(splitter, 1)

        # Hint bar
        hint = QWidget()
        hint.setFixedHeight(26)
        hint.setStyleSheet(
            f"background: {_DEEP}; border-top: 1px solid {_BORDER};")
        hl = QHBoxLayout(hint)
        hl.setContentsMargins(16, 0, 16, 0)
        hint_lbl = QLabel(
            "💡  Arrastra una acción al botón  ·  Doble clic para elegir  ·  Clic derecho para borrar")
        hint_lbl.setStyleSheet(
            f"font-size: 11px; color: {_TXT_GH}; background: transparent; font-family: {_MONO};")
        hl.addWidget(hint_lbl)
        root_lay.addWidget(hint)
        return root

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setMinimumHeight(56)
        bar.setStyleSheet(
            f"background: {_DEEP}; border-bottom: 1px solid {_BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)

        dot = QLabel("●")
        dot.setStyleSheet(f"font-size: 10px; color: {_AMBER}; background: transparent;")
        title = QLabel("Editor de Controles")
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_TXT_HI}; background: transparent;")

        # Sistema
        lbl_sys = QLabel("Sistema:")
        lbl_sys.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {_TXT_LO}; background: transparent;")
        self.cmb_system = QComboBox()
        self.cmb_system.setMinimumWidth(170)
        self.cmb_system.setMinimumHeight(34)
        self.cmb_system.addItem("(todos los sistemas)")
        self.cmb_system.currentTextChanged.connect(self._on_system_changed)

        # Modo
        self.btn_arcade = QPushButton("🕹 Arcade")
        self.btn_gamepad = QPushButton("🎮 Gamepad")
        for b in [self.btn_arcade, self.btn_gamepad]:
            b.setCheckable(True)
            b.setFixedHeight(32)
            b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            b.setStyleSheet(
                f"QPushButton {{ background: {_RAISED}; color: {_TXT_LO}; "
                f"border: 1px solid {_BORDER}; border-radius: 6px; "
                f"padding: 0 16px; font-weight: 700; font-size: 12px; }}"
                f"QPushButton:hover {{ background: #111520; color: {_TXT_MD}; "
                f"border-color: {_MID}; }}"
                f"QPushButton:checked {{ background: #1a0e04; color: {_AMBER}; "
                f"border-color: {_AMBER}; }}")
        self.btn_arcade.setChecked(True)
        self.btn_arcade.clicked.connect(lambda: self._set_mode("arcade"))
        self.btn_gamepad.clicked.connect(lambda: self._set_mode("gamepad"))

        # Selector botones 6/8
        self.btn_6btn = QPushButton("6 BTN")
        self.btn_8btn = QPushButton("8 BTN")
        for b in [self.btn_6btn, self.btn_8btn]:
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            b.setStyleSheet(
                f"QPushButton {{ background: {_RAISED}; color: {_TXT_GH}; "
                f"border: 1px solid {_BORDER}; border-radius: 5px; "
                f"padding: 0 12px; font-weight: 700; font-size: 11px; font-family: {_MONO}; }}"
                f"QPushButton:hover {{ color: {_TXT_LO}; border-color: {_MID}; }}"
                f"QPushButton:checked {{ background: #0a1520; color: {_CYAN}; "
                f"border-color: {_CYAN}; }}")
        self.btn_8btn.setChecked(True)
        self.btn_6btn.clicked.connect(lambda: self._set_btn_mode(6))
        self.btn_8btn.clicked.connect(lambda: self._set_btn_mode(8))

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {_BORDER};")

        lay.addWidget(dot)
        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(lbl_sys)
        lay.addWidget(self.cmb_system)
        lay.addWidget(sep)
        lay.addWidget(self.btn_arcade)
        lay.addWidget(self.btn_gamepad)
        lay.addWidget(sep)
        lay.addWidget(QLabel("Botonera:"))
        lay.addWidget(self.btn_6btn)
        lay.addWidget(self.btn_8btn)
        return bar

    def _build_editor(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        self.lbl_active = QLabel("Perfil: Default  ·  Modo: Arcade  ·  8 botones")
        self.lbl_active.setStyleSheet(
            f"font-size: 12px; font-weight: 700; font-family: {_MONO}; "
            f"color: {_AMBER}; background: transparent; letter-spacing: 0.5px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background: {_BASE}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background: {_BASE};")
        c_lay = QVBoxLayout(content)
        c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.setContentsMargins(0, 8, 0, 8)

        self.arcade_layout  = ArcadeLayout(btn_mode=8)
        self.gamepad_layout = GamepadLayout()
        self.gamepad_layout.hide()
        self.arcade_layout.slot_changed.connect(self._on_assignment_changed)
        self.gamepad_layout.slot_changed.connect(self._on_assignment_changed)

        c_lay.addWidget(self.arcade_layout)
        c_lay.addWidget(self.gamepad_layout)
        c_lay.addStretch()
        scroll.setWidget(content)

        lay.addWidget(self.lbl_active)
        lay.addWidget(scroll, 1)
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(300)
        w.setMaximumWidth(420)
        w.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        w.setStyleSheet(
            f"background: {_CARD}; border-left: 1px solid {_BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(12)

        def section_header(title: str) -> QLabel:
            lbl = QLabel(title)
            lbl.setFixedHeight(20)
            lbl.setStyleSheet(
                f"font-size: 9px; font-weight: 800; letter-spacing: 1.5px; "
                f"color: {_TXT_GH}; font-family: {_MONO}; background: transparent;")
            return lbl

        def sep_line() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.HLine)
            f.setFixedHeight(1)
            f.setStyleSheet(f"background: {_BORDER}; border: none;")
            return f

        # ── Perfiles ──────────────────────────────────────────────────────────
        lay.addWidget(section_header("PERFILES"))

        prof_row = QHBoxLayout()
        self.cmb_profile = QComboBox()
        self.cmb_profile.addItem("Default")
        self.cmb_profile.currentTextChanged.connect(self._on_profile_changed)
        btn_new = QPushButton("+")
        btn_new.setFixedWidth(32)
        btn_new.setFixedHeight(32)
        btn_new.setToolTip("Nuevo perfil")
        btn_new.clicked.connect(self._new_profile)
        btn_del = QPushButton("−")
        btn_del.setFixedWidth(32)
        btn_del.setFixedHeight(32)
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self._delete_profile)
        prof_row.addWidget(self.cmb_profile, 1)
        prof_row.addWidget(btn_new)
        prof_row.addWidget(btn_del)
        lay.addLayout(prof_row)

        for label, method, obj_name in [
            ("💾  Guardar perfil",    self._save_profile,       "btn_success"),
            ("📂  Cargar .cfg",       self._load_profile_file,  ""),
            ("📤  Exportar JoyToKey", self._export_joytokey,    "btn_primary"),
            ("🗑  Limpiar todo",      self._clear_layout,       "btn_danger"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(32)
            if obj_name:
                b.setObjectName(obj_name)
            b.clicked.connect(method)
            lay.addWidget(b)

        lay.addWidget(sep_line())

        # ── TeknoParrot ───────────────────────────────────────────────────────
        lay.addWidget(section_header("TEKNOPARROT"))
        tp_row = QHBoxLayout()
        self.inp_tp = QLineEdit()
        self.inp_tp.setPlaceholderText("UserProfile .xml")
        self.inp_tp.setFixedHeight(30)
        btn_tp = QPushButton("…")
        btn_tp.setFixedSize(30, 30)
        btn_tp.clicked.connect(self._browse_tp)
        tp_row.addWidget(self.inp_tp, 1)
        tp_row.addWidget(btn_tp)
        lay.addLayout(tp_row)
        btn_tp_apply = QPushButton("Aplicar en módulo RL")
        btn_tp_apply.setObjectName("btn_primary")
        btn_tp_apply.setFixedHeight(30)
        btn_tp_apply.clicked.connect(self._apply_tp)
        lay.addWidget(btn_tp_apply)

        lay.addWidget(sep_line())

        # ── PCLauncher ────────────────────────────────────────────────────────
        lay.addWidget(section_header("PCLAUNCHER"))
        pc_row = QHBoxLayout()
        self.inp_pc = QLineEdit()
        self.inp_pc.setPlaceholderText("Ruta .exe del juego")
        self.inp_pc.setFixedHeight(30)
        btn_pc = QPushButton("…")
        btn_pc.setFixedSize(30, 30)
        btn_pc.clicked.connect(self._browse_pc)
        pc_row.addWidget(self.inp_pc, 1)
        pc_row.addWidget(btn_pc)
        lay.addLayout(pc_row)
        btn_pc_apply = QPushButton("Aplicar en Games.ini")
        btn_pc_apply.setObjectName("btn_primary")
        btn_pc_apply.setFixedHeight(30)
        btn_pc_apply.clicked.connect(self._apply_pc)
        lay.addWidget(btn_pc_apply)

        lay.addWidget(sep_line())

        # ── Asignaciones ─────────────────────────────────────────────────────
        lay.addWidget(section_header("ASIGNACIONES ACTUALES"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setMinimumHeight(140)
        self.txt_summary.setStyleSheet(
            f"QTextEdit {{ background: {_DEEP}; border: 1px solid {_BORDER}; "
            f"color: {_TXT_LO}; font-family: {_MONO}; font-size: 11px; "
            f"border-radius: 6px; padding: 6px; }}")
        lay.addWidget(self.txt_summary)
        lay.addStretch()
        return w

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _reload_systems(self):
        scan = self._config.get("scan_results", {})
        self._systems = scan.get("systems", [])
        self.cmb_system.clear()
        self.cmb_system.addItem("(todos los sistemas)")
        for s in self._systems:
            self.cmb_system.addItem(s)

    def _on_system_changed(self, name: str):
        self._current_system = "" if name == "(todos los sistemas)" else name
        self._load_profiles_for_system()

    def _get_profile_dir(self) -> str:
        rl_dir = self._config.get("rocketlauncher_dir", "")
        if not rl_dir:
            return ""
        sub = self._current_system if self._current_system else "_Global"
        return os.path.join(rl_dir, "Profiles", sub)

    def _load_profiles_for_system(self):
        self._profiles = {"Default": {}}
        self.cmb_profile.clear()
        self.cmb_profile.addItem("Default")
        prof_dir = self._get_profile_dir()
        if prof_dir and os.path.isdir(prof_dir):
            for f in sorted(os.listdir(prof_dir)):
                if f.endswith(".cfg"):
                    name = f[:-4]
                    try:
                        with open(os.path.join(prof_dir, f), "r", encoding="utf-8") as fp:
                            self._profiles[name] = json.load(fp)
                        if name != "Default":
                            self.cmb_profile.addItem(name)
                    except Exception:
                        pass
        self._apply_profile("Default")

    def _set_mode(self, mode: str):
        self._current_mode = mode
        is_arcade = (mode == "arcade")
        self.arcade_layout.setVisible(is_arcade)
        self.gamepad_layout.setVisible(not is_arcade)
        self.btn_arcade.setChecked(is_arcade)
        self.btn_gamepad.setChecked(not is_arcade)
        self.btn_6btn.setEnabled(is_arcade)
        self.btn_8btn.setEnabled(is_arcade)

        new_palette = ActionPalette(ARCADE_ACTIONS if is_arcade else GAMEPAD_ACTIONS)
        splitter = self._palette.parent()
        if splitter:
            idx = splitter.indexOf(self._palette)
            self._palette.deleteLater()
            self._palette = new_palette
            splitter.insertWidget(idx, self._palette)
        self._update_label()

    def _set_btn_mode(self, mode: int):
        self.btn_6btn.setChecked(mode == 6)
        self.btn_8btn.setChecked(mode == 8)
        self.arcade_layout.set_btn_mode(mode)
        self._update_label()

    def _on_assignment_changed(self, slot_id: str, action: str):
        self._update_summary()

    def _update_label(self):
        sys_lbl  = self._current_system or "Todos"
        mode_lbl = "Arcade" if self._current_mode == "arcade" else "Gamepad"
        btn_lbl  = f"{6 if self.btn_6btn.isChecked() else 8} BTN" if self._current_mode == "arcade" else ""
        parts = [f"Sistema: {sys_lbl}", f"Perfil: {self._current_profile}", f"Modo: {mode_lbl}"]
        if btn_lbl:
            parts.append(btn_lbl)
        self.lbl_active.setText("  ·  ".join(parts))

    def _update_summary(self):
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        lines = [f"{sid:<20} → {act}"
                 for sid, act in sorted(layout.get_assignments().items()) if act]
        self.txt_summary.setText("\n".join(lines) if lines else "(sin asignaciones)")

    def _on_profile_changed(self, name: str):
        if name:
            self._current_profile = name
            self._apply_profile(name)
            self._update_label()

    def _apply_profile(self, name: str):
        data  = self._profiles.get(name, {})
        mode  = data.get("_mode", "arcade")
        btn_mode = int(data.get("_btn_mode", 8))
        self._set_mode(mode)
        self._set_btn_mode(6 if btn_mode == 6 else 8)
        asgn  = {k: v for k, v in data.items() if not k.startswith("_")}
        layout = self.arcade_layout if mode == "arcade" else self.gamepad_layout
        layout.set_assignments(asgn)
        self._update_summary()

    def _save_profile(self):
        name   = self.cmb_profile.currentText()
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        data   = layout.get_assignments()
        data["_mode"]   = self._current_mode
        data["_system"] = self._current_system
        data["_btn_mode"] = 6 if self.btn_6btn.isChecked() else 8
        self._profiles[name] = data
        prof_dir = self._get_profile_dir()
        if prof_dir:
            os.makedirs(prof_dir, exist_ok=True)
            path = os.path.join(prof_dir, f"{name}.cfg")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self._save_system_joytokey_cfg()
                if self.parent:
                    self.parent.statusBar().showMessage(
                        f"✓ Perfil '{name}' guardado en {path}", 4000)
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", str(e))

    def _save_system_joytokey_cfg(self):
        system_name = (self._current_system or "").strip()
        rl_dir = (self._config.get("rocketlauncher_dir", "") or "").strip()
        if not system_name or not rl_dir:
            return
        joy_dir  = os.path.join(rl_dir, "Profiles", "JoyToKey", system_name)
        cfg_path = os.path.join(joy_dir, f"{system_name}.cfg")
        content  = make_joytokey_cfg(system_name)
        os.makedirs(joy_dir, exist_ok=True)
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                    current = f.read()
                if current != content:
                    ok = QMessageBox.question(
                        self.parent, "JoyToKey existente",
                        f"Ya existe:\n{cfg_path}\n\n¿Sobrescribir con la plantilla del sistema?",
                        QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
                    if ok != QMessageBox.Yes:
                        return
            except Exception:
                return
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _new_profile(self):
        name, ok = QInputDialog.getText(self.parent, "Nuevo perfil", "Nombre del perfil:")
        if ok and name.strip():
            name = name.strip()
            self._profiles[name] = {}
            if self.cmb_profile.findText(name) < 0:
                self.cmb_profile.addItem(name)
            self.cmb_profile.setCurrentText(name)

    def _delete_profile(self):
        name = self.cmb_profile.currentText()
        if name == "Default":
            QMessageBox.warning(self.parent, "No permitido", "No se puede eliminar 'Default'.")
            return
        reply = QMessageBox.question(
            self.parent, "Eliminar perfil", f"¿Eliminar el perfil '{name}'?",
            QMessageBox.Yes | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            self.cmb_profile.removeItem(self.cmb_profile.currentIndex())
            self._profiles.pop(name, None)
            prof_dir = self._get_profile_dir()
            if prof_dir:
                path = os.path.join(prof_dir, f"{name}.cfg")
                if os.path.isfile(path):
                    os.remove(path)

    def _load_profile_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Cargar perfil", "", "Perfil (*.cfg);;JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = Path(path).stem
            self._profiles[name] = data
            if self.cmb_profile.findText(name) < 0:
                self.cmb_profile.addItem(name)
            self.cmb_profile.setCurrentText(name)
            self._apply_profile(name)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error al cargar", str(e))

    def _export_joytokey(self):
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        asgn   = layout.get_assignments()
        if not asgn:
            QMessageBox.information(self.parent, "Sin asignaciones",
                                    "No hay asignaciones que exportar.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.parent, "Exportar JoyToKey",
            f"{self._current_profile}_{self._current_mode}.cfg", "JoyToKey (*.cfg)")
        if not path:
            return
        lines = [
            "; HyperSpin Manager — JoyToKey Export",
            f"; Sistema: {self._current_system or 'Global'}",
            f"; Perfil: {self._current_profile}",
            f"; Modo: {self._current_mode}", "", "[config]", "FileVersion=2", "",
        ]
        for i, (sid, act) in enumerate(sorted(asgn.items()), 1):
            if act and act != "---":
                lines += [f"[Button_{i}]", f"Slot={sid}", f"Action={act}", ""]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            if self.parent:
                self.parent.statusBar().showMessage(f"✓ Exportado: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error al exportar", str(e))

    def _clear_layout(self):
        reply = QMessageBox.question(
            self.parent, "Limpiar", "¿Eliminar todas las asignaciones?",
            QMessageBox.Yes | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
            layout.clear_all()
            self._update_summary()

    def _browse_tp(self):
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "UserProfile TeknoParrot",
            self._config.get("rocketlauncher_dir", ""), "XML (*.xml);;Todos (*.*)")
        if path:
            self.inp_tp.setText(path)

    def _apply_tp(self):
        tp = self.inp_tp.text().strip()
        rl = self._config.get("rocketlauncher_dir", "")
        sys_name = self._current_system
        if not sys_name or not tp:
            QMessageBox.warning(self.parent, "Datos incompletos",
                                "Selecciona un sistema y una ruta de perfil TP.")
            return
        emu_ini = os.path.join(rl, "Settings", sys_name, "Emulators.ini")
        if not os.path.isfile(emu_ini):
            QMessageBox.warning(self.parent, "Sin Emulators.ini",
                                f"No encontrado:\n{emu_ini}")
            return
        cfg = configparser.RawConfigParser()
        cfg.read(emu_ini, encoding="utf-8")
        updated = False
        for sec in cfg.sections():
            if "tekno" in sec.lower():
                cfg.set(sec, "UserProfile", tp)
                updated = True
        if updated:
            with open(emu_ini, "w", encoding="utf-8") as f:
                cfg.write(f)
            if self.parent:
                self.parent.statusBar().showMessage(
                    "✓ UserProfile TeknoParrot actualizado.", 5000)
        else:
            QMessageBox.information(self.parent, "Sin sección TeknoParrot",
                                    "No se encontró sección [TeknoParrot] en Emulators.ini.")

    def _browse_pc(self):
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Ejecutable del juego", "", "Ejecutables (*.exe);;Todos (*.*)")
        if path:
            self.inp_pc.setText(path)

    def _apply_pc(self):
        exe = self.inp_pc.text().strip()
        rl  = self._config.get("rocketlauncher_dir", "")
        sys_name = self._current_system
        if not sys_name or not exe:
            QMessageBox.warning(self.parent, "Datos incompletos",
                                "Selecciona un sistema y el ejecutable.")
            return
        games_ini = os.path.join(rl, "Settings", sys_name, "Games.ini")
        os.makedirs(os.path.dirname(games_ini), exist_ok=True)
        cfg = configparser.RawConfigParser()
        if os.path.isfile(games_ini):
            cfg.read(games_ini, encoding="utf-8")
        if not cfg.has_section(sys_name):
            cfg.add_section(sys_name)
        cfg.set(sys_name, "Exe_Path", exe)
        with open(games_ini, "w", encoding="utf-8") as f:
            cfg.write(f)
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ Exe_Path actualizado en {games_ini}", 5000)
