"""
tabs/controls.py
ControlsTab — Editor visual de perfiles de control para HyperSpin Manager

FIXES v3:
 - Mandos PNG más grandes (280x220 por mando)
 - Botones del mando con colores y etiquetas correctas (A verde, B rojo, X azul, Y amarillo)
 - Descripción de cada función en los slots (LT=gatillo, LB=bumper, LS=movimiento, etc.)
 - Cambio 6/8 BTN reconstruye el widget correctamente (QWidget.deleteLater + rebuild)
 - Layout completamente responsivo: usa stretch + SizePolicy, sin fixedSize en el área central
 - Contraste: todos los textos visibles en dark
"""

import os
import json
import configparser
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QScrollArea, QFrame, QSplitter,
    QFileDialog, QMessageBox, QInputDialog,
    QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt, QMimeData, QRect, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont,
    QDrag, QPixmap, QRadialGradient, QPolygon
)

from tabs.create_system import make_joytokey_cfg

try:
    from main import TabModule
except ImportError:
    class TabModule:
        tab_title = "Módulo"
        tab_icon = ""

        def __init__(self, parent):
            self.parent = parent

        def widget(self):
            raise NotImplementedError

        def load_data(self, config):
            pass

        def save_data(self):
            return {}


# ─── Paleta ───────────────────────────────────────────────────────────────────
_AMBER = "#f5a623"
_CYAN = "#00c9e8"
_GREEN = "#00e599"
_DEEP = "#05070b"
_BASE = "#090c12"
_RAISED = "#0d1018"
_CARD = "#0a0d14"
_BORDER = "#1a2035"
_MID = "#243050"
_TXT_HI = "#e8edf8"
_TXT_MD = "#c8d4ec"
_TXT_LO = "#8a9ab8"
_TXT_GH = "#4a5878"
_MONO = "'Consolas', 'Courier New', monospace"

# ─── Colores de botones del gamepad ──────────────────────────────────────────
BTN_COLORS = {
    "btn_a": "#1b7a2e",  # verde  (A / Cross)
    "btn_b": "#aa1a28",  # rojo   (B / Circle)
    "btn_x": "#1040a0",  # azul   (X / Square)
    "btn_y": "#c48000",  # amarillo (Y / Triangle)
}

# ─── Acciones ─────────────────────────────────────────────────────────────────
ARCADE_ACTIONS = [
    "Start P1", "Start P2", "Coin P1", "Coin P2",
    "Pause", "Exit", "Config",
    "Button 1", "Button 2", "Button 3", "Button 4",
    "Button 5", "Button 6", "Button 7", "Button 8",
    "Up", "Down", "Left", "Right",
    "Service", "Test", "---",
]

GAMEPAD_ACTIONS = [
    "A — Confirmar/Acción", "B — Cancelar/Volver", "X — Acc. Secundaria", "Y — Acc. Terciaria",
    "LB — Bumper Izq", "RB — Bumper Der",
    "LT — Gatillo Izq", "RT — Gatillo Der",
    "L3 — Pulsar Stick Izq", "R3 — Pulsar Stick Der",
    "Start", "Select / Back",
    "D-Up", "D-Down", "D-Left", "D-Right",
    "LS — Mover Personaje", "RS — Mover Cámara",
    "Pause", "Exit", "---",
]

ACTION_COLORS = {
    "Start P1": "#1565c0", "Start P2": "#1565c0",
    "Coin P1": "#4a148c", "Coin P2": "#4a148c",
    "Pause": "#1b5e20", "Exit": "#b71c1c",
    "Config": "#e65100",
    "Button 1": "#c62828", "Button 2": "#283593",
    "Button 3": "#1b5e20", "Button 4": "#c47800",
    "Button 5": "#880e4f", "Button 6": "#006064",
    "Button 7": "#37474f", "Button 8": "#4e342e",
    "A — Confirmar/Acción": "#1b7a2e",
    "B — Cancelar/Volver": "#aa1a28",
    "X — Acc. Secundaria": "#1040a0",
    "Y — Acc. Terciaria": "#c48000",
    "LT — Gatillo Izq": "#2e4a7a",
    "RT — Gatillo Der": "#2e4a7a",
    "LB — Bumper Izq": "#1a3a6a",
    "RB — Bumper Der": "#1a3a6a",
    "L3 — Pulsar Stick Izq": "#2a2a50",
    "R3 — Pulsar Stick Der": "#2a2a50",
    "LS — Mover Personaje": "#1a4a30",
    "RS — Mover Cámara": "#1a4a30",
    "---": "#1e2330",
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
    RECT = "rect"

    def __init__(self, slot_id: str, label: str = "", shape: str = "circle",
                 size: int = 48, accent: str = "", parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.label = label
        self.shape = shape
        self._size = size
        self._accent = accent
        self.action = ""
        self._hover = False
        self._actions = ARCADE_ACTIONS
        pad = 14 if shape == self.CIRCLE else 8
        self.setFixedSize(size + pad, size + pad)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Slot: {slot_id}\nDoble clic para asignar · Clic derecho para borrar")

    def set_actions(self, actions: list):
        self._actions = actions

    def set_action(self, action: str):
        self.action = action
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r = self._size // 2

        if self._accent:
            base_str = self._accent
        elif self.action:
            base_str = action_color(self.action)
        else:
            base_str = "#101520"

        base = QColor(base_str).lighter(130) if self._hover else QColor(base_str)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 120)))
        if self.shape == self.CIRCLE:
            p.drawEllipse(cx - r + 2, cy - r + 2, r * 2, r * 2)
        else:
            p.drawRoundedRect(3, 3, w - 3, h - 3, 7, 7)

        grad = QRadialGradient(cx - r // 3, cy - r // 3, r * 2)
        grad.setColorAt(0, base.lighter(115))
        grad.setColorAt(1, base)
        p.setBrush(QBrush(grad))
        border_color = QColor(_AMBER) if self._hover else QColor(_BORDER)
        p.setPen(QPen(border_color, 1.5))
        if self.shape == self.CIRCLE:
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        else:
            p.drawRoundedRect(2, 2, w - 4, h - 4, 7, 7)

        if self.label:
            p.setFont(QFont("Consolas", max(7, self._size // 7), QFont.Weight.Bold))
            p.setPen(QPen(QColor("#c8d4ec")))
            p.drawText(QRect(0, 2, w, 14), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self.label)

        if self.action and self.action != "---":
            short = self.action.split("—")[0].strip() if "—" in self.action else self.action
            short = short[:11]
            p.setFont(QFont("Segoe UI", max(6, self._size // 9), QFont.Weight.Bold))
            p.setPen(QPen(QColor("#ffffff")))
            p.drawText(QRect(cx - r + 2, cy - 10, r * 2 - 4, 20),
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, short)
        else:
            p.setFont(QFont("Segoe UI", 9))
            p.setPen(QPen(QColor(_TXT_GH)))
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
                self, f"Asignar — {self.slot_id}", "Selecciona una acción:",
                self._actions, 0, False)
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
            pix = QPixmap(180, 30)
            pix.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = QColor(action_color(self.action))
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 180, 30, 6, 6)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#ffffff")))
            painter.drawText(QRect(0, 0, 180, 30), Qt.AlignmentFlag.AlignCenter, self.action[:22])
            painter.end()
            drag.setPixmap(pix)
            drag.setHotSpot(event.pos())
            drag.exec(Qt.DropAction.CopyAction)


# ─── ActionPalette ────────────────────────────────────────────────────────────

class ActionPalette(QWidget):
    def __init__(self, actions: list, parent=None):
        super().__init__(parent)
        self.setFixedWidth(185)
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
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(
            f"background: {_DEEP}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        lbl = QLabel("ACCIONES  (arrastra)")
        lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 800; letter-spacing: 1px; "
            f"color: {_TXT_LO}; font-family: {_MONO}; background: transparent;")
        hl.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {_CARD};")

        content = QWidget()
        content.setStyleSheet(f"background: {_CARD};")
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(4, 6, 4, 6)
        c_lay.setSpacing(2)
        for action in actions:
            c_lay.addWidget(DraggableActionItem(action))
        c_lay.addStretch()
        scroll.setWidget(content)

        lay.addWidget(hdr)
        lay.addWidget(scroll, 1)


# ─── StickCanvas ─────────────────────────────────────────────────────────────

class StickCanvas(QWidget):
    GATE_OCTAGONAL = "octagonal"
    GATE_SQUARE = "square"
    GATE_CIRCULAR = "circular"

    def __init__(self, accent_color: str = _AMBER, gate: str = GATE_OCTAGONAL, parent=None):
        super().__init__(parent)
        self.accent = QColor(accent_color)
        self._gate = gate
        self.setMinimumSize(90, 90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Selector de gate abajo")

    def set_gate(self, gate: str):
        self._gate = gate
        self.update()

    def set_accent(self, color: str):
        self.accent = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = min(self.width(), self.height())
        cx = self.width() // 2
        cy = self.height() // 2
        r = int(s * 0.44)

        p.setPen(QPen(QColor("#333333"), 1.5))
        p.setBrush(QBrush(QColor("#0a0a0a")))
        gs = int(r * 0.70)

        if self._gate == self.GATE_OCTAGONAL:
            h = gs // 2
            pts = [
                QPoint(cx - h, cy - gs), QPoint(cx + h, cy - gs),
                QPoint(cx + gs, cy - h), QPoint(cx + gs, cy + h),
                QPoint(cx + h, cy + gs), QPoint(cx - h, cy + gs),
                QPoint(cx - gs, cy + h), QPoint(cx - gs, cy - h),
            ]
            p.drawPolygon(QPolygon(pts))
        elif self._gate == self.GATE_SQUARE:
            p.drawRect(cx - gs, cy - gs, gs * 2, gs * 2)
        else:
            p.drawEllipse(cx - gs, cy - gs, gs * 2, gs * 2)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#1a1a1a")))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        p.setPen(QPen(self.accent, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        p.setPen(QPen(QColor("#303030"), 1))
        p.drawLine(cx, cy - r + 6, cx, cy + r - 6)
        p.drawLine(cx - r + 6, cy, cx + r - 6, cy)

        br = int(r * 0.38)
        grad = QRadialGradient(cx - br // 3, cy - br // 3, br * 2)
        grad.setColorAt(0, QColor("#666666"))
        grad.setColorAt(1, QColor("#1a1a1a"))
        p.setPen(QPen(QColor("#555555"), 1))
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - br, cy - br, br * 2, br * 2)

        gate_txt = {"octagonal": "OCT", "square": "SQR", "circular": "CIR"}.get(self._gate, "")
        p.setFont(QFont("Consolas", max(6, s // 16)))
        p.setPen(QPen(QColor(_TXT_GH)))
        p.drawText(QRect(cx - 25, cy + r - 16, 50, 14), Qt.AlignmentFlag.AlignCenter, gate_txt)


# ─── ArcadeLayout ────────────────────────────────────────────────────────────

class ArcadeLayout(QWidget):
    """Layout de control arcade con palanca y botonera 6 u 8 botones."""
    slot_changed = pyqtSignal(str, str)

    MODE_6BTN = 6
    MODE_8BTN = 8

    def __init__(self, btn_mode: int = 8, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._slots: dict = {}
        self._btn_mode = btn_mode
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build()

    def set_btn_mode(self, mode: int):
        if mode == self._btn_mode:
            return
        old_asgn = dict(self.assignments)
        self._btn_mode = mode

        old_lay = self.layout()
        if old_lay:
            self._wipe_layout(old_lay)
            QWidget().setLayout(old_lay)

        self._slots = {}
        self.assignments = {}
        self._build()

        for sid, act in old_asgn.items():
            if sid in self._slots:
                self._slots[sid].set_action(act)
                self.assignments[sid] = act

    def _wipe_layout(self, lay):
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._wipe_layout(item.layout())

    def _build(self):
        self.setStyleSheet(
            "ArcadeLayout{" 
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 #14181f, stop:1 #09090f);"
            f"border: 2px solid #1e2535; border-radius: 14px;}}")
        self.setMinimumHeight(240)

        main = QVBoxLayout(self)
        main.setContentsMargins(16, 10, 16, 10)
        main.setSpacing(6)

        hdr = QHBoxLayout()
        p1l = QLabel("● PLAYER 1")
        p1l.setStyleSheet(
            f"color:{_AMBER}; font-size:12px; font-weight:800; "
            f"letter-spacing:2px; font-family:{_MONO}; background:transparent;")
        mode_lbl = QLabel(f"{'6' if self._btn_mode == 6 else '8'} BOTONES")
        mode_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_lbl.setStyleSheet(
            f"color:{_TXT_GH}; font-size:10px; font-weight:700; "
            f"letter-spacing:1px; font-family:{_MONO}; background:transparent;")
        p2l = QLabel("PLAYER 2 ●")
        p2l.setAlignment(Qt.AlignmentFlag.AlignRight)
        p2l.setStyleSheet(
            f"color:{_CYAN}; font-size:12px; font-weight:800; "
            f"letter-spacing:2px; font-family:{_MONO}; background:transparent;")
        hdr.addWidget(p1l)
        hdr.addStretch()
        hdr.addWidget(mode_lbl)
        hdr.addStretch()
        hdr.addWidget(p2l)

        mid = QHBoxLayout()
        mid.setSpacing(10)
        mid.addWidget(self._build_player("p1", _AMBER), 4)
        mid.addStretch(1)
        mid.addWidget(self._build_center(), 2)
        mid.addStretch(1)
        mid.addWidget(self._build_player("p2", _CYAN), 4)

        main.addLayout(hdr)
        main.addLayout(mid, 1)

    def _build_player(self, player: str, accent: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QHBoxLayout(w)
        lay.setSpacing(12)
        lay.setContentsMargins(0, 0, 0, 0)

        stick_col = QWidget()
        stick_col.setStyleSheet("background:transparent;")
        stick_col.setMinimumWidth(100)
        sc_lay = QVBoxLayout(stick_col)
        sc_lay.setContentsMargins(0, 0, 0, 0)
        sc_lay.setSpacing(4)

        lbl_stick = QLabel("PALANCA")
        lbl_stick.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_stick.setStyleSheet(
            f"font-size:9px; font-weight:800; letter-spacing:1px; "
            f"color:{_TXT_GH}; font-family:{_MONO}; background:transparent;")

        stick = StickCanvas(accent_color=accent, gate=StickCanvas.GATE_OCTAGONAL)
        stick.setObjectName(f"stick_{player}")
        stick.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        gate_cmb = QComboBox()
        gate_cmb.addItems(["Octagonal", "Cuadrado", "Circular"])
        gate_cmb.setToolTip("Restrictor de la palanca")
        gate_cmb.setStyleSheet(
            f"QComboBox{{background:{_RAISED};border:1px solid {_BORDER};"
            f"border-radius:4px;color:{_TXT_MD};font-size:10px;padding:2px 6px;}}"
            f"QComboBox::drop-down{{border:none;width:16px;}}")
        gate_map = {0: StickCanvas.GATE_OCTAGONAL, 1: StickCanvas.GATE_SQUARE,
                    2: StickCanvas.GATE_CIRCULAR}
        gate_cmb.currentIndexChanged.connect(lambda i, s=stick: s.set_gate(gate_map[i]))

        dirs_row = QHBoxLayout()
        dirs_row.setSpacing(3)
        dirs_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for sid, arrow in [(f"{player}_up", "↑"), (f"{player}_dn", "↓"),
                           (f"{player}_lt2", "←"), (f"{player}_rt2", "→")]:
            b = ButtonSlot(sid, arrow, ButtonSlot.RECT, 26)
            b.set_actions(ARCADE_ACTIONS)
            b.assignment_changed.connect(self._on_slot)
            self._slots[sid] = b
            dirs_row.addWidget(b)

        sc_lay.addWidget(lbl_stick)
        sc_lay.addWidget(stick, 1)
        sc_lay.addWidget(gate_cmb)
        sc_lay.addLayout(dirs_row)

        btn_col = QWidget()
        btn_col.setStyleSheet("background:transparent;")
        btn_col.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn_lay = QGridLayout(btn_col)
        btn_lay.setSpacing(6)
        btn_lay.setContentsMargins(0, 0, 0, 0)

        if self._btn_mode == 6:
            positions = [
                (0, 0, f"{player}_b4"), (1, 0, f"{player}_b5"), (2, 0, f"{player}_b6"),
                (0, 1, f"{player}_b1"), (1, 1, f"{player}_b2"), (2, 1, f"{player}_b3"),
            ]
        else:
            positions = [
                (0, 0, f"{player}_b1"), (1, 0, f"{player}_b2"),
                (2, 0, f"{player}_b3"), (3, 0, f"{player}_b4"),
                (0, 1, f"{player}_b5"), (1, 1, f"{player}_b6"),
                (2, 1, f"{player}_b7"), (3, 1, f"{player}_b8"),
            ]

        for col, row, slot_id in positions:
            num = slot_id.split("_b")[1]
            btn = ButtonSlot(slot_id, f"B{num}", ButtonSlot.CIRCLE, 44)
            btn.set_actions(ARCADE_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            btn_lay.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)
            self._slots[slot_id] = btn

        lay.addWidget(stick_col)
        lay.addWidget(btn_col, 1)
        return w

    def _build_center(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(6)
        lay.addStretch()

        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame{{background:#0a0c10;border:1px solid {_BORDER};border-radius:10px;}}")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(8, 8, 8, 8)
        pl.setSpacing(8)

        for row_def in [
            [("p1_coin", "1P COIN"), ("p1_start", "1P START")],
            [("pause", "PAUSE"), ("exit", "EXIT")],
            [("p2_coin", "2P COIN"), ("p2_start", "2P START")],
        ]:
            rw = QHBoxLayout()
            rw.setSpacing(8)
            rw.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for sid, lbl in row_def:
                b = ButtonSlot(sid, lbl, ButtonSlot.RECT, 30)
                b.set_actions(ARCADE_ACTIONS)
                b.assignment_changed.connect(self._on_slot)
                rw.addWidget(b)
                self._slots[sid] = b
            pl.addLayout(rw)

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


# ─── GamepadLayout ───────────────────────────────────────────────────────────

class GamepadLayout(QWidget):
    """Gamepad con imágenes PNG reales, botones de colores correctos, layout responsivo."""
    slot_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._slots: dict = {}
        self._theme = "dark"
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build()

    def set_theme(self, theme: str):
        self._theme = theme
        self._update_controller_images()

    def _get_img_path(self) -> str:
        base = Path(__file__).parent.parent
        candidates_dark = [
            base / "assets" / "Mando_claro.png",
            base / "Mando_claro.png",
            "/mnt/user-data/uploads/Mando_claro.png",
            "/mnt/user-data/outputs/assets/Mando_claro.png",
        ]
        candidates_light = [
            base / "assets" / "Mando_Oscuro.png",
            base / "Mando_Oscuro.png",
            "/mnt/user-data/uploads/Mando_Oscuro.png",
            "/mnt/user-data/outputs/assets/Mando_Oscuro.png",
        ]
        cands = candidates_dark if self._theme == "dark" else candidates_light
        for c in cands:
            if Path(c).exists():
                return str(c)
        return ""

    def _btn_lbl(self, text: str, color: str = "") -> QLabel:
        l = QLabel(text)
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c = color or _TXT_GH
        l.setStyleSheet(
            f"font-size:10px;font-weight:700;letter-spacing:0.5px;"
            f"color:{c};background:transparent;font-family:{_MONO};")
        return l

    def _build(self):
        self.setStyleSheet(
            f"GamepadLayout{{background:{_BASE};border:1px solid {_BORDER};border-radius:10px;}}")

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addLayout(self._build_left(), 2)
        root.addWidget(self._build_center(), 5)
        root.addLayout(self._build_right(), 2)

    def _trigger_row(self, sid: str, label: str, desc: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(6)
        btn = ButtonSlot(sid, label, ButtonSlot.RECT, 36)
        btn.set_actions(GAMEPAD_ACTIONS)
        btn.assignment_changed.connect(self._on_slot)
        self._slots[sid] = btn

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"font-size:11px;font-weight:800;color:{_TXT_MD};background:transparent;"
            f"font-family:{_MONO};")
        row.addWidget(name_lbl)
        row.addWidget(btn)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            f"font-size:9px;color:{_TXT_GH};background:transparent;")
        desc_lbl.setWordWrap(True)

        lay.addLayout(row)
        lay.addWidget(desc_lbl)
        return w

    def _build_dpad(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background:transparent;")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(4)

        grid_w = QWidget()
        grid_w.setFixedSize(110, 110)
        grid_w.setStyleSheet("background:transparent;")
        g = QGridLayout(grid_w)
        g.setSpacing(2)
        g.setContentsMargins(4, 4, 4, 4)

        for row, col, sid, arrow in [
            (0, 1, "dpad_up", "↑"), (1, 0, "dpad_left", "←"),
            (1, 2, "dpad_right", "→"), (2, 1, "dpad_down", "↓"),
        ]:
            b = ButtonSlot(sid, arrow, ButtonSlot.RECT, 28)
            b.set_actions(GAMEPAD_ACTIONS)
            b.assignment_changed.connect(self._on_slot)
            self._slots[sid] = b
            g.addWidget(b, row, col, Qt.AlignmentFlag.AlignCenter)

        center = QWidget()
        center.setFixedSize(28, 28)
        center.setStyleSheet(f"background:{_RAISED};border-radius:4px;")
        g.addWidget(center, 1, 1)

        ol.addWidget(grid_w)
        ol.addWidget(self._btn_lbl("D-PAD  (menús/inventario)"))
        return outer

    def _build_face_btns(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background:transparent;")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(4)

        grid_w = QWidget()
        grid_w.setFixedSize(120, 120)
        grid_w.setStyleSheet("background:transparent;")
        g = QGridLayout(grid_w)
        g.setSpacing(3)
        g.setContentsMargins(4, 4, 4, 4)

        face_def = [
            (0, 1, "btn_y", "Y", BTN_COLORS["btn_y"], "Acc. Terciaria"),
            (1, 0, "btn_x", "X", BTN_COLORS["btn_x"], "Acc. Secundaria"),
            (1, 2, "btn_b", "B", BTN_COLORS["btn_b"], "Cancelar"),
            (2, 1, "btn_a", "A", BTN_COLORS["btn_a"], "Confirmar"),
        ]
        for row, col, sid, lbl, color, desc in face_def:
            b = ButtonSlot(sid, lbl, ButtonSlot.CIRCLE, 36, accent=color)
            b.set_actions(GAMEPAD_ACTIONS)
            b.assignment_changed.connect(self._on_slot)
            self._slots[sid] = b
            b.setToolTip(f"{lbl} — {desc}\nDoble clic para asignar · Clic derecho para borrar")
            g.addWidget(b, row, col, Qt.AlignmentFlag.AlignCenter)

        ol.addWidget(grid_w)
        ol.addWidget(self._btn_lbl("BOTONES  CARA"))
        return outer

    def _stick_click(self, sid: str, label: str, desc: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(3)
        b = ButtonSlot(sid, label, ButtonSlot.CIRCLE, 40)
        b.set_actions(GAMEPAD_ACTIONS)
        b.assignment_changed.connect(self._on_slot)
        self._slots[sid] = b
        l.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(self._btn_lbl(f"{label}  {desc}"))
        return w

    def _build_left(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(10)
        lay.addWidget(self._trigger_row("lt", "LT", "Gatillo izq (analógico)"))
        lay.addWidget(self._trigger_row("lb", "LB", "Bumper izq (digital)"))
        lay.addSpacing(8)
        lay.addWidget(self._build_dpad())
        lay.addSpacing(8)
        lay.addWidget(self._stick_click("ls_click", "L3", "(pulsar stick izq)"))
        lay.addStretch()
        return lay

    def _build_right(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(10)
        lay.addWidget(self._trigger_row("rt", "RT", "Gatillo der (analógico)"))
        lay.addWidget(self._trigger_row("rb", "RB", "Bumper der (digital)"))
        lay.addSpacing(8)
        lay.addWidget(self._build_face_btns())
        lay.addSpacing(8)
        lay.addWidget(self._stick_click("rs_click", "R3", "(pulsar stick der)"))
        lay.addStretch()
        return lay

    def _build_center(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        ctls_row = QHBoxLayout()
        ctls_row.setSpacing(20)
        ctls_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for player, acc, p_desc in [
            ("p1", _AMBER, "PLAYER 1 — Stick Izq: Movimiento"),
            ("p2", _CYAN, "PLAYER 2 — Stick Der: Cámara"),
        ]:
            col = QWidget()
            col.setStyleSheet("background:transparent;")
            cl = QVBoxLayout(col)
            cl.setContentsMargins(0, 0, 0, 4)
            cl.setSpacing(6)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            img_lbl = QLabel()
            img_lbl.setMinimumSize(260, 200)
            img_lbl.setMaximumSize(340, 260)
            img_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setScaledContents(False)
            img_lbl.setStyleSheet("background:transparent;")
            setattr(self, f"_img_{player}", img_lbl)

            plbl = QLabel(p_desc)
            plbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            plbl.setStyleSheet(
                f"font-size:10px;font-weight:800;color:{acc};"
                f"letter-spacing:1px;background:transparent;font-family:{_MONO};")

            cl.addWidget(img_lbl, 1)
            cl.addWidget(plbl)
            ctls_row.addWidget(col, 1)

        lay.addLayout(ctls_row, 1)

        spec_row = QHBoxLayout()
        spec_row.setSpacing(20)
        spec_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for sid, lbl, desc in [
            ("btn_select", "SELECT", "Abrir mapa / inv."),
            ("btn_start", "START", "Pausar / menú"),
            ("ls_move", "LS", "Mover personaje"),
            ("rs_camera", "RS", "Mover cámara"),
        ]:
            vw = QWidget()
            vw.setStyleSheet("background:transparent;")
            vl = QVBoxLayout(vw)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(3)
            btn = ButtonSlot(sid, lbl, ButtonSlot.RECT, 32)
            btn.set_actions(GAMEPAD_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            self._slots[sid] = btn
            btn.setToolTip(f"{lbl} — {desc}")
            vl.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            vl.addWidget(self._btn_lbl(desc))
            spec_row.addWidget(vw)

        lay.addLayout(spec_row)

        QTimer.singleShot(150, self._update_controller_images)
        return w

    def _update_controller_images(self):
        path = self._get_img_path()
        for player in ["p1", "p2"]:
            lbl = getattr(self, f"_img_{player}", None)
            if not lbl:
                continue
            if path and Path(path).exists():
                pix = QPixmap(path)
                if not pix.isNull():
                    scaled = pix.scaled(
                        lbl.width(), lbl.height(),
                        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    lbl.setPixmap(scaled)
            else:
                lbl.setText(f"🎮\n{player.upper()}")
                lbl.setStyleSheet(
                    f"font-size:40px;color:{_TXT_GH};background:transparent;")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self._update_controller_images)

    def _on_slot(self, sid: str, action: str):
        self.assignments[sid] = action
        self.slot_changed.emit(sid, action)

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
    tab_icon = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config: dict = {}
        self._systems: list = []
        self._current_system: str = ""
        self._current_profile: str = "Default"
        self._current_mode: str = "arcade"
        self._current_btn_mode: int = 8
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
            theme = config.get("theme", "dark")
            if hasattr(self, "gamepad_layout"):
                self.gamepad_layout.set_theme(theme)

    def save_data(self) -> dict:
        return {}

    def _build(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet(f"background:{_DEEP};")
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        rl.addWidget(self._build_toolbar())

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(f"QSplitter::handle{{background:{_BORDER};}}")

        self._palette = ActionPalette(ARCADE_ACTIONS)
        self._editor_w = self._build_editor()
        self._right_panel = self._build_right_panel()

        self._splitter.addWidget(self._palette)
        self._splitter.addWidget(self._editor_w)
        self._splitter.addWidget(self._right_panel)
        self._splitter.setSizes([185, 0, 280])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        rl.addWidget(self._splitter, 1)

        hint = QWidget()
        hint.setFixedHeight(26)
        hint.setStyleSheet(f"background:{_DEEP};border-top:1px solid {_BORDER};")
        hl = QHBoxLayout(hint)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.addWidget(QLabel(
            "💡  Arrastra acción al botón  ·  Doble clic para elegir  ·  Clic derecho para borrar  "
            "·  A=verde  B=rojo  X=azul  Y=amarillo"))
        hl.itemAt(0).widget().setStyleSheet(
            f"font-size:11px;color:{_TXT_GH};background:transparent;font-family:{_MONO};")
        rl.addWidget(hint)
        return root

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet(f"background:{_DEEP};border-bottom:1px solid {_BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(10)

        dot = QLabel("●")
        dot.setStyleSheet(f"font-size:10px;color:{_AMBER};background:transparent;")
        title = QLabel("Controles")
        title.setStyleSheet(
            f"font-size:15px;font-weight:800;color:{_TXT_HI};background:transparent;")

        lbl_sys = QLabel("Sistema:")
        lbl_sys.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{_TXT_LO};background:transparent;")
        self.cmb_system = QComboBox()
        self.cmb_system.setMinimumWidth(180)
        self.cmb_system.addItem("(todos los sistemas)")
        self.cmb_system.currentTextChanged.connect(self._on_system_changed)

        def mode_btn(text: str) -> QPushButton:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setFixedHeight(32)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(
                f"QPushButton{{background:{_RAISED};color:{_TXT_MD};border:1px solid {_BORDER};"
                f"border-radius:6px;padding:0 16px;font-weight:700;font-size:12px;}}"
                f"QPushButton:hover{{background:#111520;color:{_TXT_HI};border-color:{_MID};}}"
                f"QPushButton:checked{{background:#1a0e04;color:{_AMBER};border-color:{_AMBER};}}")
            return b

        def btn_mode_btn(text: str, active_color: str) -> QPushButton:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(
                f"QPushButton{{background:{_RAISED};color:{_TXT_LO};border:1px solid {_BORDER};"
                f"border-radius:5px;padding:0 14px;font-weight:800;font-size:11px;"
                f"font-family:{_MONO};}}"
                f"QPushButton:hover{{color:{_TXT_MD};border-color:{_MID};}}"
                f"QPushButton:checked{{background:#0a1520;color:{active_color};"
                f"border-color:{active_color};}}")
            return b

        self.btn_arcade = mode_btn("🕹  Arcade")
        self.btn_gamepad = mode_btn("🎮  Gamepad")
        self.btn_arcade.setChecked(True)
        self.btn_arcade.clicked.connect(lambda: self._set_mode("arcade"))
        self.btn_gamepad.clicked.connect(lambda: self._set_mode("gamepad"))

        self.btn_6btn = btn_mode_btn("6 BTN", _GREEN)
        self.btn_8btn = btn_mode_btn("8 BTN", _CYAN)
        self.btn_8btn.setChecked(True)
        self.btn_6btn.clicked.connect(lambda: self._set_btn_mode(6))
        self.btn_8btn.clicked.connect(lambda: self._set_btn_mode(8))

        lbl_botonera = QLabel("Botonera:")
        lbl_botonera.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{_TXT_LO};background:transparent;")

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background:{_BORDER};")

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedWidth(1)
        sep2.setStyleSheet(f"background:{_BORDER};")

        lay.addWidget(dot)
        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(lbl_sys)
        lay.addWidget(self.cmb_system)
        lay.addWidget(sep)
        lay.addWidget(self.btn_arcade)
        lay.addWidget(self.btn_gamepad)
        lay.addWidget(sep2)
        lay.addWidget(lbl_botonera)
        lay.addWidget(self.btn_6btn)
        lay.addWidget(self.btn_8btn)
        return bar

    def _build_editor(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{_BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        self.lbl_active = QLabel("Perfil: Default  ·  Arcade  ·  8 BTN")
        self.lbl_active.setStyleSheet(
            f"font-size:12px;font-weight:700;font-family:{_MONO};"
            f"color:{_AMBER};background:transparent;")

        self.arcade_layout = ArcadeLayout(btn_mode=8)
        self.gamepad_layout = GamepadLayout()
        self.gamepad_layout.hide()

        self.arcade_layout.slot_changed.connect(self._on_assignment_changed)
        self.gamepad_layout.slot_changed.connect(self._on_assignment_changed)

        lay.addWidget(self.lbl_active)
        lay.addWidget(self.arcade_layout, 1)
        lay.addWidget(self.gamepad_layout, 1)
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(275)
        w.setStyleSheet(f"background:{_CARD};border-left:1px solid {_BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(10)

        def sh(title: str) -> QLabel:
            l = QLabel(title)
            l.setFixedHeight(18)
            l.setStyleSheet(
                f"font-size:10px;font-weight:800;letter-spacing:1.5px;"
                f"color:{_TXT_LO};font-family:{_MONO};background:transparent;")
            return l

        def sep() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.HLine)
            f.setFixedHeight(1)
            f.setStyleSheet(f"background:{_BORDER};border:none;")
            return f

        lay.addWidget(sh("PERFILES"))
        pr = QHBoxLayout()
        self.cmb_profile = QComboBox()
        self.cmb_profile.addItem("Default")
        self.cmb_profile.currentTextChanged.connect(self._on_profile_changed)
        b_new = QPushButton("+")
        b_new.setFixedSize(32, 32)
        b_new.setToolTip("Nuevo perfil")
        b_new.clicked.connect(self._new_profile)
        b_del = QPushButton("−")
        b_del.setFixedSize(32, 32)
        b_del.setObjectName("btn_danger")
        b_del.clicked.connect(self._delete_profile)
        pr.addWidget(self.cmb_profile, 1)
        pr.addWidget(b_new)
        pr.addWidget(b_del)
        lay.addLayout(pr)

        for lbl, fn, obj in [
            ("💾  Guardar perfil", self._save_profile, "btn_success"),
            ("📂  Cargar .cfg", self._load_profile_file, ""),
            ("📤  Exportar JoyToKey", self._export_joytokey, "btn_primary"),
            ("🗑  Limpiar todo", self._clear_layout, "btn_danger"),
        ]:
            b = QPushButton(lbl)
            b.setFixedHeight(32)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            lay.addWidget(b)

        lay.addWidget(sep())
        lay.addWidget(sh("TEKNOPARROT"))
        tp_r = QHBoxLayout()
        self.inp_tp = QLineEdit()
        self.inp_tp.setPlaceholderText("UserProfile .xml")
        self.inp_tp.setFixedHeight(30)
        b_tp = QPushButton("…")
        b_tp.setFixedSize(30, 30)
        b_tp.clicked.connect(self._browse_tp)
        tp_r.addWidget(self.inp_tp, 1)
        tp_r.addWidget(b_tp)
        lay.addLayout(tp_r)
        b_tp_a = QPushButton("Aplicar en módulo RL")
        b_tp_a.setObjectName("btn_primary")
        b_tp_a.setFixedHeight(30)
        b_tp_a.clicked.connect(self._apply_tp)
        lay.addWidget(b_tp_a)

        lay.addWidget(sep())
        lay.addWidget(sh("PCLAUNCHER"))
        pc_r = QHBoxLayout()
        self.inp_pc = QLineEdit()
        self.inp_pc.setPlaceholderText("Ruta .exe del juego")
        self.inp_pc.setFixedHeight(30)
        b_pc = QPushButton("…")
        b_pc.setFixedSize(30, 30)
        b_pc.clicked.connect(self._browse_pc)
        pc_r.addWidget(self.inp_pc, 1)
        pc_r.addWidget(b_pc)
        lay.addLayout(pc_r)
        b_pc_a = QPushButton("Aplicar en Games.ini")
        b_pc_a.setObjectName("btn_primary")
        b_pc_a.setFixedHeight(30)
        b_pc_a.clicked.connect(self._apply_pc)
        lay.addWidget(b_pc_a)

        lay.addWidget(sep())
        lay.addWidget(sh("ASIGNACIONES ACTUALES"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setMinimumHeight(80)
        self.txt_summary.setStyleSheet(
            f"QTextEdit{{background:{_DEEP};border:1px solid {_BORDER};"
            f"color:{_TXT_LO};font-family:{_MONO};font-size:11px;"
            f"border-radius:6px;padding:6px;}}")
        lay.addWidget(self.txt_summary, 1)
        return w

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
        sub = self._current_system or "_Global"
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
                        with open(os.path.join(prof_dir, f), encoding="utf-8") as fp:
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
        splitter = self._splitter
        old_idx = splitter.indexOf(self._palette)
        self._palette.setParent(None)
        self._palette.deleteLater()
        self._palette = new_palette
        splitter.insertWidget(old_idx, self._palette)
        splitter.setSizes([185, 0, 280])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self._update_label()

    def _set_btn_mode(self, mode: int):
        if mode == self._current_btn_mode:
            return
        self._current_btn_mode = mode
        self.btn_6btn.setChecked(mode == 6)
        self.btn_8btn.setChecked(mode == 8)
        self.arcade_layout.set_btn_mode(mode)
        self._update_label()

    def _on_assignment_changed(self, slot_id: str, action: str):
        self._update_summary()

    def _update_label(self):
        sys_l = self._current_system or "Todos"
        mode_l = "Arcade" if self._current_mode == "arcade" else "Gamepad"
        btn_l = f"  ·  {self._current_btn_mode} BTN" if self._current_mode == "arcade" else ""
        self.lbl_active.setText(
            f"Sistema: {sys_l}  ·  Perfil: {self._current_profile}  ·  {mode_l}{btn_l}")

    def _update_summary(self):
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        lines = [f"{sid:<22} → {act}"
                 for sid, act in sorted(layout.get_assignments().items()) if act]
        self.txt_summary.setText("\n".join(lines) if lines else "(sin asignaciones)")

    def _on_profile_changed(self, name: str):
        if name:
            self._current_profile = name
            self._apply_profile(name)
            self._update_label()

    def _apply_profile(self, name: str):
        data = self._profiles.get(name, {})
        mode = data.get("_mode", "arcade")
        self._set_mode(mode)
        asgn = {k: v for k, v in data.items() if not k.startswith("_")}
        layout = self.arcade_layout if mode == "arcade" else self.gamepad_layout
        layout.set_assignments(asgn)
        self._update_summary()

    def _save_profile(self):
        name = self.cmb_profile.currentText()
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        data = layout.get_assignments()
        data["_mode"] = self._current_mode
        data["_system"] = self._current_system
        self._profiles[name] = data
        prof_dir = self._get_profile_dir()
        if prof_dir:
            os.makedirs(prof_dir, exist_ok=True)
            path = os.path.join(prof_dir, f"{name}.cfg")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self._save_joytokey()
                if self.parent:
                    self.parent.statusBar().showMessage(
                        f"✓ Perfil '{name}' guardado.", 4000)
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", str(e))

    def _save_joytokey(self):
        sn = (self._current_system or "").strip()
        rl = (self._config.get("rocketlauncher_dir", "") or "").strip()
        if not sn or not rl:
            return
        joy_dir = os.path.join(rl, "Profiles", "JoyToKey", sn)
        cfg_p = os.path.join(joy_dir, f"{sn}.cfg")
        content = make_joytokey_cfg(sn)
        os.makedirs(joy_dir, exist_ok=True)
        if os.path.isfile(cfg_p):
            try:
                with open(cfg_p, encoding="utf-8", errors="ignore") as f:
                    if f.read() == content:
                        return
                ok = QMessageBox.question(
                    self.parent, "JoyToKey existente",
                    f"Ya existe:\n{cfg_p}\n\n¿Sobrescribir?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if ok != QMessageBox.StandardButton.Yes:
                    return
            except Exception:
                return
        with open(cfg_p, "w", encoding="utf-8") as f:
            f.write(content)

    def _new_profile(self):
        name, ok = QInputDialog.getText(
            self.parent, "Nuevo perfil", "Nombre del perfil:")
        if ok and name.strip():
            name = name.strip()
            self._profiles[name] = {}
            if self.cmb_profile.findText(name) < 0:
                self.cmb_profile.addItem(name)
            self.cmb_profile.setCurrentText(name)

    def _delete_profile(self):
        name = self.cmb_profile.currentText()
        if name == "Default":
            QMessageBox.warning(
                self.parent, "No permitido", "No se puede eliminar 'Default'.")
            return
        r = QMessageBox.question(
            self.parent, "Eliminar", f"¿Eliminar '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Yes:
            self.cmb_profile.removeItem(self.cmb_profile.currentIndex())
            self._profiles.pop(name, None)
            pd = self._get_profile_dir()
            if pd:
                p = os.path.join(pd, f"{name}.cfg")
                if os.path.isfile(p):
                    os.remove(p)

    def _load_profile_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Cargar perfil", "", "Perfil (*.cfg);;JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            name = Path(path).stem
            self._profiles[name] = data
            if self.cmb_profile.findText(name) < 0:
                self.cmb_profile.addItem(name)
            self.cmb_profile.setCurrentText(name)
            self._apply_profile(name)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))

    def _export_joytokey(self):
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        asgn = layout.get_assignments()
        if not asgn:
            QMessageBox.information(
                self.parent, "Sin asignaciones", "No hay asignaciones que exportar.")
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
            f"; Modo: {self._current_mode}",
            "", "[config]", "FileVersion=2", "",
        ]
        for i, (sid, act) in enumerate(sorted(asgn.items()), 1):
            if act and act != "---":
                lines += [f"[Button_{i}]", f"Slot={sid}", f"Action={act}", ""]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            if self.parent:
                self.parent.statusBar().showMessage(
                    f"✓ Exportado: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))

    def _clear_layout(self):
        r = QMessageBox.question(
            self.parent, "Limpiar", "¿Eliminar todas las asignaciones?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Yes:
            layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
            layout.clear_all()
            self._update_summary()

    def _browse_tp(self):
        p, _ = QFileDialog.getOpenFileName(
            self.parent, "UserProfile TeknoParrot",
            self._config.get("rocketlauncher_dir", ""), "XML (*.xml);;Todos (*.*)")
        if p:
            self.inp_tp.setText(p)

    def _apply_tp(self):
        tp = self.inp_tp.text().strip()
        rl = self._config.get("rocketlauncher_dir", "")
        sn = self._current_system
        if not sn or not tp:
            QMessageBox.warning(
                self.parent, "Datos incompletos",
                "Selecciona sistema y ruta de perfil TP.")
            return
        emu_ini = os.path.join(rl, "Settings", sn, "Emulators.ini")
        if not os.path.isfile(emu_ini):
            QMessageBox.warning(
                self.parent, "Sin Emulators.ini", f"No encontrado:\n{emu_ini}")
            return
        cfg = configparser.RawConfigParser()
        cfg.read(emu_ini, encoding="utf-8")
        updated = any(
            (cfg.set(s, "UserProfile", tp) or True)
            for s in cfg.sections() if "tekno" in s.lower()
        )
        if updated:
            with open(emu_ini, "w", encoding="utf-8") as f:
                cfg.write(f)
            if self.parent:
                self.parent.statusBar().showMessage(
                    "✓ UserProfile TeknoParrot actualizado.", 5000)
        else:
            QMessageBox.information(
                self.parent, "Sin sección TP",
                "No se encontró sección [TeknoParrot] en Emulators.ini.")

    def _browse_pc(self):
        p, _ = QFileDialog.getOpenFileName(
            self.parent, "Ejecutable del juego", "",
            "Ejecutables (*.exe);;Todos (*.*)")
        if p:
            self.inp_pc.setText(p)

    def _apply_pc(self):
        exe = self.inp_pc.text().strip()
        rl = self._config.get("rocketlauncher_dir", "")
        sn = self._current_system
        if not sn or not exe:
            QMessageBox.warning(
                self.parent, "Datos incompletos",
                "Selecciona sistema y ejecutable.")
            return
        games_ini = os.path.join(rl, "Settings", sn, "Games.ini")
        os.makedirs(os.path.dirname(games_ini), exist_ok=True)
        cfg = configparser.RawConfigParser()
        if os.path.isfile(games_ini):
            cfg.read(games_ini, encoding="utf-8")
        if not cfg.has_section(sn):
            cfg.add_section(sn)
        cfg.set(sn, "Exe_Path", exe)
        with open(games_ini, "w", encoding="utf-8") as f:
            cfg.write(f)
        if self.parent:
            self.parent.statusBar().showMessage(
                f"✓ Exe_Path actualizado en {games_ini}", 5000)
