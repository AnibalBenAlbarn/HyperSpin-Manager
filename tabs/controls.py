"""
tabs/controls.py
ControlsTab — Editor visual de perfiles de control para HyperSpin Manager

Soporta:
  - Layout Arcade (joystick + 8 botones por jugador, basado en medidas reales slagcoin.com)
  - Layout Gamepad (mando con sticks, botones frontales, gatillos, D-pad)
  - Perfiles JoyToKey (.cfg) por sistema
  - Soporte TeknoParrot / PCLauncher (modificación UserProfile en INIs de módulo)
  - Drag & drop de acciones a botones
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
    QListWidget, QListWidgetItem, QTabWidget,
    QFileDialog, QMessageBox, QInputDialog,
    QSizePolicy, QAbstractItemView, QDialog,
    QDialogButtonBox, QCheckBox, QTextEdit
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

ACTION_COLORS = {
    "Start P1":  "#1565c0", "Start P2":  "#1565c0",
    "Coin P1":   "#4a148c", "Coin P2":   "#4a148c",
    "Pause":     "#1b5e20", "Exit":      "#b71c1c",
    "Config":    "#e65100",
    "Button 1":  "#c62828", "Button 2":  "#283593",
    "Button 3":  "#1b5e20", "Button 4":  "#f9a825",
    "Button 5":  "#880e4f", "Button 6":  "#006064",
    "Button 7":  "#37474f", "Button 8":  "#4e342e",
    "---":       "#1e2330",
}
DEFAULT_COLOR = "#1e3a5f"

BUTTON_COLORS = [
    "#c62828", "#283593", "#1b5e20", "#f9a825",
    "#880e4f", "#006064", "#4a148c", "#37474f",
]


def action_color(action: str) -> str:
    if not action or action == "---":
        return "#1e2330"
    return ACTION_COLORS.get(action, DEFAULT_COLOR)


# ─── ButtonSlot: botón drag & drop ───────────────────────────────────────────

class ButtonSlot(QWidget):
    assignment_changed = pyqtSignal(str, str)
    CIRCLE = "circle"
    RECT   = "rect"

    def __init__(self, slot_id: str, label: str = "", shape: str = "circle",
                 size: int = 44, parent=None):
        super().__init__(parent)
        self.slot_id  = slot_id
        self.label    = label
        self.shape    = shape
        self._size    = size
        self.action   = ""
        self._hover   = False
        self._actions = ARCADE_ACTIONS
        fixed = size + 16 if shape == self.CIRCLE else size + 8
        self.setFixedSize(fixed, fixed)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_actions(self, actions: list):
        self._actions = actions

    def set_action(self, action: str):
        self.action = action
        self.update()

    def paintEvent(self, event):
        p  = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r  = self._size // 2
        color_str = action_color(self.action) if self.action else "#161922"
        base = QColor(color_str).lighter(130) if self._hover else QColor(color_str)

        # Sombra
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 80)))
        if self.shape == self.CIRCLE:
            p.drawEllipse(cx - r + 2, cy - r + 2, r * 2, r * 2)
        else:
            p.drawRoundedRect(4, 4, w - 4, h - 4, 6, 6)

        # Cuerpo con gradiente radial
        grad = QRadialGradient(cx - r // 3, cy - r // 3, r * 2)
        grad.setColorAt(0, base.lighter(130))
        grad.setColorAt(1, base)
        p.setBrush(QBrush(grad))
        border_color = QColor("#4fc3f7") if self._hover else QColor("#2a3a55")
        p.setPen(QPen(border_color, 1.5))
        if self.shape == self.CIRCLE:
            p.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        else:
            p.drawRoundedRect(2, 2, w - 4, h - 4, 6, 6)

        # Etiqueta del slot
        if self.label:
            p.setFont(QFont("Segoe UI", 7, QFont.Bold))
            p.setPen(QPen(QColor("#3a4560")))
            p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, self.label)

        # Acción asignada
        if self.action and self.action != "---":
            p.setFont(QFont("Segoe UI", 7, QFont.Bold))
            p.setPen(QPen(QColor("#e8ecf4")))
            rect = QRect(cx - r + 2, cy - 10, r * 2 - 4, 20)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.action[:12])
        else:
            p.setFont(QFont("Segoe UI", 7))
            p.setPen(QPen(QColor("#2a3a55")))
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
        action = event.mimeData().text()
        self.set_action(action)
        self.assignment_changed.emit(self.slot_id, action)
        self.update()
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
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background:{action_color(action)};border-radius:5px;")
        lbl = QLabel(action)
        lbl.setStyleSheet("color:#8892a4;font-size:12px;")
        lay.addWidget(dot)
        lay.addWidget(lbl)
        lay.addStretch()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.action)
            drag.setMimeData(mime)
            pix = QPixmap(160, 28)
            pix.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(QColor(action_color(self.action))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 160, 28, 4, 4)
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QPen(QColor("#ffffff")))
            painter.drawText(QRect(0, 0, 160, 28), Qt.AlignmentFlag.AlignCenter, self.action)
            painter.end()
            drag.setPixmap(pix)
            drag.setHotSpot(event.pos())
            drag.exec(Qt.DropAction.CopyAction)


# ─── ActionPalette ────────────────────────────────────────────────────────────

class ActionPalette(QWidget):
    def __init__(self, actions: list, parent=None):
        super().__init__(parent)
        self.setFixedWidth(160)
        self._actions = actions
        self._scroll_content = None
        self._c_lay = None
        self._build(actions)

    def _build(self, actions: list):
        # Limpiar si ya hay layout
        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QLabel("  ACCIONES")
        hdr.setFixedHeight(30)
        hdr.setStyleSheet(
            "background:#080a0f;color:#2a3a55;font-size:10px;"
            "font-weight:700;letter-spacing:1px;"
            "border-bottom:1px solid #1e2330;padding:0 8px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:#0a0d12;")

        content = QWidget()
        c_lay   = QVBoxLayout(content)
        c_lay.setContentsMargins(4, 4, 4, 4)
        c_lay.setSpacing(2)
        for action in actions:
            c_lay.addWidget(DraggableActionItem(action))
        c_lay.addStretch()
        scroll.setWidget(content)

        lay.addWidget(hdr)
        lay.addWidget(scroll, 1)


# ─── StickCanvas helper ────────────────────────────────────────────────────────

class StickCanvas(QWidget):
    def __init__(self, accent_color: str, parent=None):
        super().__init__(parent)
        self.accent = QColor(accent_color)
        self.setFixedSize(90, 90)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r = 45, 45, 38

        # Restrictor gate octogonal
        gs = 34
        pts = [
            QPoint(cx - gs//2, cy - gs), QPoint(cx + gs//2, cy - gs),
            QPoint(cx + gs,    cy - gs//2), QPoint(cx + gs,    cy + gs//2),
            QPoint(cx + gs//2, cy + gs),  QPoint(cx - gs//2, cy + gs),
            QPoint(cx - gs,    cy + gs//2), QPoint(cx - gs,    cy - gs//2),
        ]
        p.setPen(QPen(QColor("#2a2a2a"), 1.5))
        p.setBrush(QBrush(QColor("#111111")))
        p.drawPolygon(QPolygon(pts))

        # Base del stick
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#222222")))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Anillo de acento
        p.setPen(QPen(self.accent, 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Bola
        ball_r = 14
        grad = QRadialGradient(cx - 4, cy - 4, ball_r * 2)
        grad.setColorAt(0, QColor("#444444"))
        grad.setColorAt(1, QColor("#1a1a1a"))
        p.setPen(QPen(QColor("#555555"), 1))
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - ball_r, cy - ball_r, ball_r * 2, ball_r * 2)


# ─── ArcadeLayout ────────────────────────────────────────────────────────────

class ArcadeLayout(QWidget):
    slot_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._slots: dict = {}
        self._build()

    def _build(self):
        self.setStyleSheet(
            "ArcadeLayout{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #1a1a1a,stop:1 #0d0d0d);"
            "border:2px solid #2a2a2a;border-radius:12px;}")
        self.setMinimumSize(880, 300)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(20, 14, 20, 14)
        main_lay.setSpacing(8)

        # Header jugadores
        top_row = QHBoxLayout()
        p1_lbl = QLabel("● PLAYER 1")
        p1_lbl.setStyleSheet(
            "color:#ffb74d;font-size:11px;font-weight:800;"
            "letter-spacing:1.5px;font-family:'Consolas',monospace;")
        p2_lbl = QLabel("PLAYER 2 ●")
        p2_lbl.setStyleSheet(
            "color:#4fc3f7;font-size:11px;font-weight:800;"
            "letter-spacing:1.5px;font-family:'Consolas',monospace;")
        p2_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        top_row.addWidget(p1_lbl)
        top_row.addStretch()
        top_row.addWidget(p2_lbl)

        # Contenido
        mid_row = QHBoxLayout()
        mid_row.setSpacing(0)
        mid_row.addWidget(self._build_player_panel("p1", "#ffb74d"))
        mid_row.addStretch(1)
        mid_row.addWidget(self._build_center_panel())
        mid_row.addStretch(1)
        mid_row.addWidget(self._build_player_panel("p2", "#4fc3f7"))

        main_lay.addLayout(top_row)
        main_lay.addLayout(mid_row)

    def _build_player_panel(self, player: str, accent: str) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setSpacing(16)
        lay.setContentsMargins(0, 0, 0, 0)

        # Joystick
        js_w = QWidget()
        js_w.setFixedSize(90, 120)
        js_lay = QVBoxLayout(js_w)
        js_lay.setContentsMargins(0, 0, 0, 0)
        js_lay.setSpacing(2)
        stick = StickCanvas(accent)
        dirs_lbl = QLabel("↑ ↓ ← →")
        dirs_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dirs_lbl.setStyleSheet(f"color:{accent};font-size:10px;font-weight:700;")
        js_lay.addWidget(stick, 0, Qt.AlignmentFlag.AlignHCenter)
        js_lay.addWidget(dirs_lbl)

        # Botones 3+3+2 (layout Sega/Capcom)
        btn_w = QWidget()
        btn_lay = QGridLayout(btn_w)
        btn_lay.setSpacing(6)
        btn_lay.setContentsMargins(0, 0, 0, 0)

        positions = [
            (0, 0, f"{player}_b4"), (1, 0, f"{player}_b5"), (2, 0, f"{player}_b6"),
            (0, 1, f"{player}_b1"), (1, 1, f"{player}_b2"), (2, 1, f"{player}_b3"),
            (0, 2, f"{player}_b7"), (1, 2, f"{player}_b8"),
        ]
        for col, row, slot_id in positions:
            num = slot_id.split("_b")[1]
            btn = ButtonSlot(slot_id, f"B{num}", ButtonSlot.CIRCLE, 42)
            btn.set_actions(ARCADE_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            btn_lay.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)
            self._slots[slot_id] = btn

        lay.addWidget(js_w)
        lay.addWidget(btn_w)
        return w

    def _build_center_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(200)
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 0, 0)

        rows = [
            [("p1_coin", "1P\nCOIN"), ("p1_start", "1P\nSTART")],
            [("pause", "PAUSE"),    ("exit", "EXIT")],
            [("p2_coin", "2P\nCOIN"), ("p2_start", "2P\nSTART")],
        ]
        sizes = [32, 28, 32]
        lay.addStretch()
        for row_def, sz in zip(rows, sizes):
            row_w = QHBoxLayout()
            row_w.setSpacing(6)
            for slot_id, label in row_def:
                btn = ButtonSlot(slot_id, label, ButtonSlot.RECT, sz)
                btn.set_actions(ARCADE_ACTIONS)
                btn.assignment_changed.connect(self._on_slot)
                row_w.addWidget(btn)
                self._slots[slot_id] = btn
            lay.addLayout(row_w)
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


# ─── GamepadBody (silueta pintada) ───────────────────────────────────────────

class GamepadBody(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 170)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Cuerpo
        path = QPainterPath()
        path.addRoundedRect(40, 50, 180, 90, 30, 30)
        path.addRoundedRect(18, 100, 65, 65, 22, 22)
        path.addRoundedRect(177, 100, 65, 65, 22, 22)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor("#252b3d"))
        grad.setColorAt(1, QColor("#141820"))

        p.setPen(QPen(QColor("#2a3a55"), 1.5))
        p.setBrush(QBrush(grad))
        p.drawPath(path)

        # Bumpers
        p.setPen(QPen(QColor("#1e2d45"), 1))
        p.setBrush(QBrush(QColor("#1a2035")))
        p.drawRoundedRect(30, 28, 55, 24, 8, 8)
        p.drawRoundedRect(175, 28, 55, 24, 8, 8)

        # Sticks
        for cx, cy, r in [(88, 102, 22), (162, 128, 22)]:
            p.setPen(QPen(QColor("#1a2a40"), 1.5))
            p.setBrush(QBrush(QColor("#0d1525")))
            p.drawEllipse(cx-r, cy-r, r*2, r*2)
            p.setBrush(QBrush(QColor("#151e30")))
            p.drawEllipse(cx-14, cy-14, 28, 28)

        # Botones ABXY
        face = [
            (185, 76,  "#f9a825"),
            (200, 92,  "#c62828"),
            (185, 108, "#1b5e20"),
            (170, 92,  "#1565c0"),
        ]
        for fx, fy, fc in face:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(fc)))
            p.drawEllipse(fx-7, fy-7, 14, 14)

        # D-pad
        p.setPen(QPen(QColor("#1e2d45"), 1))
        p.setBrush(QBrush(QColor("#161d2e")))
        p.drawRoundedRect(58, 87, 42, 14, 4, 4)
        p.drawRoundedRect(65, 80, 14, 28, 4, 4)

        # Select / Start (pequeños)
        for cx in [118, 142]:
            p.setPen(QPen(QColor("#1e2d45"), 1))
            p.setBrush(QBrush(QColor("#1a2035")))
            p.drawRoundedRect(cx-10, 87, 20, 8, 3, 3)


# ─── GamepadLayout ────────────────────────────────────────────────────────────

class GamepadLayout(QWidget):
    slot_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._slots: dict = {}
        self._build()

    def _build(self):
        self.setStyleSheet(
            "GamepadLayout{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #0f1118,stop:1 #080a0f);"
            "border:1px solid #1e2330;border-radius:10px;}")
        self.setMinimumSize(860, 360)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(0)

        left  = self._build_left()
        center = self._build_center()
        right  = self._build_right()

        root.addLayout(left, 2)
        root.addLayout(center, 3)
        root.addLayout(right, 2)

    def _build_trigger_row(self, slot_id: str, label: str) -> QWidget:
        w = QWidget()
        w.setFixedHeight(46)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(32)
        lbl.setStyleSheet("color:#3a4560;font-size:11px;font-weight:700;")
        btn = ButtonSlot(slot_id, label, ButtonSlot.RECT, 30)
        btn.set_actions(GAMEPAD_ACTIONS)
        btn.assignment_changed.connect(self._on_slot)
        self._slots[slot_id] = btn
        lay.addWidget(lbl)
        lay.addWidget(btn)
        return w

    def _build_dpad(self) -> QWidget:
        outer = QWidget()
        outer_l = QVBoxLayout(outer)
        outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.setSpacing(2)

        w = QWidget()
        w.setFixedSize(128, 128)
        lay = QGridLayout(w)
        lay.setSpacing(2)
        lay.setContentsMargins(4, 4, 4, 4)

        for row, col, sid, arrow in [
            (0, 1, "dpad_up",    "↑"),
            (1, 0, "dpad_left",  "←"),
            (1, 2, "dpad_right", "→"),
            (2, 1, "dpad_down",  "↓"),
        ]:
            btn = ButtonSlot(sid, arrow, ButtonSlot.RECT, 28)
            btn.set_actions(GAMEPAD_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            self._slots[sid] = btn
            lay.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        center = QWidget()
        center.setFixedSize(28, 28)
        center.setStyleSheet("background:#161922;border-radius:4px;")
        lay.addWidget(center, 1, 1)

        lbl = QLabel("D-PAD")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#2a3a55;font-size:9px;font-weight:700;")
        outer_l.addWidget(w)
        outer_l.addWidget(lbl)
        return outer

    def _build_face_buttons(self) -> QWidget:
        outer = QWidget()
        outer_l = QVBoxLayout(outer)
        outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.setSpacing(2)

        w = QWidget()
        w.setFixedSize(128, 128)
        lay = QGridLayout(w)
        lay.setSpacing(2)
        lay.setContentsMargins(4, 4, 4, 4)

        for row, col, sid, label in [
            (0, 1, "btn_y", "Y"),
            (1, 0, "btn_x", "X"),
            (1, 2, "btn_b", "B"),
            (2, 1, "btn_a", "A"),
        ]:
            btn = ButtonSlot(sid, label, ButtonSlot.CIRCLE, 34)
            btn.set_actions(GAMEPAD_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            self._slots[sid] = btn
            lay.addWidget(btn, row, col, Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("BOTONES")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#2a3a55;font-size:9px;font-weight:700;")
        outer_l.addWidget(w)
        outer_l.addWidget(lbl)
        return outer

    def _build_stick_section(self, slot_id: str, label: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        btn = ButtonSlot(slot_id, label, ButtonSlot.CIRCLE, 40)
        btn.set_actions(GAMEPAD_ACTIONS)
        btn.assignment_changed.connect(self._on_slot)
        self._slots[slot_id] = btn
        lbl = QLabel(f"{label} click")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#2a3a55;font-size:9px;")
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(lbl)
        return w

    def _build_left(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(6)
        lay.addWidget(self._build_trigger_row("lt", "LT"))
        lay.addWidget(self._build_trigger_row("lb", "LB"))
        lay.addSpacing(8)
        lay.addWidget(self._build_dpad())
        lay.addSpacing(8)
        lay.addWidget(self._build_stick_section("ls", "L STICK"))
        lay.addStretch()
        return lay

    def _build_right(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(6)
        lay.addWidget(self._build_trigger_row("rt", "RT"))
        lay.addWidget(self._build_trigger_row("rb", "RB"))
        lay.addSpacing(8)
        lay.addWidget(self._build_face_buttons())
        lay.addSpacing(8)
        lay.addWidget(self._build_stick_section("rs", "R STICK"))
        lay.addStretch()
        return lay

    def _build_center(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(8)

        body = GamepadBody()
        lay.addWidget(body, 0, Qt.AlignmentFlag.AlignHCenter)

        spec_row = QHBoxLayout()
        spec_row.setSpacing(10)
        spec_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for sid, label in [("btn_select", "SELECT"), ("btn_start", "START")]:
            btn = ButtonSlot(sid, label, ButtonSlot.RECT, 26)
            btn.set_actions(GAMEPAD_ACTIONS)
            btn.assignment_changed.connect(self._on_slot)
            self._slots[sid] = btn
            spec_row.addWidget(btn)
        lay.addLayout(spec_row)

        credit_lbl = QLabel("HyperSpin Manager · Gamepad Editor")
        credit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit_lbl.setStyleSheet("color:#1e2d45;font-size:9px;")
        lay.addWidget(credit_lbl)
        lay.addStretch()
        return lay

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


# ─── ControlsTab (módulo principal) ──────────────────────────────────────────

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

    def save_data(self) -> dict:
        return {}

    def _build(self) -> QWidget:
        root = QWidget()
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        root_lay.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle{background:#1e2330;}")

        self._palette = ActionPalette(ARCADE_ACTIONS)
        editor_w     = self._build_editor()
        right_panel  = self._build_right_panel()

        splitter.addWidget(self._palette)
        splitter.addWidget(editor_w)
        splitter.addWidget(right_panel)
        splitter.setSizes([160, 700, 280])
        root_lay.addWidget(splitter, 1)

        hint = QLabel(
            "💡  Arrastra una acción a un botón  ·  "
            "Doble clic para elegir  ·  Clic derecho para limpiar")
        hint.setStyleSheet(
            "background:#080a0f;color:#2a3a55;font-size:11px;"
            "padding:5px 16px;border-top:1px solid #1e2330;")
        root_lay.addWidget(hint)
        return root

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background:#080a0f;border-bottom:1px solid #1e2330;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(10)

        title = QLabel("Editor de Controles")
        title.setStyleSheet("font-size:15px;font-weight:700;color:#c8cdd8;")

        lbl_sys = QLabel("Sistema:")
        lbl_sys.setStyleSheet("color:#5a6278;font-size:12px;")
        self.cmb_system = QComboBox()
        self.cmb_system.setMinimumWidth(160)
        self.cmb_system.addItem("(todos los sistemas)")
        self.cmb_system.currentTextChanged.connect(self._on_system_changed)

        lbl_mode = QLabel("Tipo:")
        lbl_mode.setStyleSheet("color:#5a6278;font-size:12px;")

        self.btn_arcade  = QPushButton("🕹 Arcade")
        self.btn_gamepad = QPushButton("🎮 Gamepad")
        for b in [self.btn_arcade, self.btn_gamepad]:
            b.setCheckable(True)
            b.setFixedWidth(100)
            b.setStyleSheet(
                "QPushButton:checked{background:#0d4f7a;color:#4fc3f7;border-color:#1a6fa0;}")
        self.btn_arcade.setChecked(True)
        self.btn_arcade.clicked.connect(lambda: self._set_mode("arcade"))
        self.btn_gamepad.clicked.connect(lambda: self._set_mode("gamepad"))

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(lbl_sys)
        lay.addWidget(self.cmb_system)
        lay.addWidget(lbl_mode)
        lay.addWidget(self.btn_arcade)
        lay.addWidget(self.btn_gamepad)
        return bar

    def _build_editor(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:#0d0f14;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self.lbl_active = QLabel("Perfil: Default  ·  Modo: Arcade")
        self.lbl_active.setStyleSheet(
            "color:#4fc3f7;font-size:12px;font-weight:600;letter-spacing:0.5px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:#0d0f14;")

        content = QWidget()
        content.setStyleSheet("background:#0d0f14;")
        c_lay = QVBoxLayout(content)
        c_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_lay.setContentsMargins(0, 0, 0, 0)

        self.arcade_layout  = ArcadeLayout()
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
        w.setStyleSheet("background:#0a0d12;border-left:1px solid #1e2330;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Perfiles
        gb_prof = QGroupBox("Perfiles")
        prof_lay = QVBoxLayout(gb_prof)
        prof_lay.setSpacing(6)

        prof_row = QHBoxLayout()
        self.cmb_profile = QComboBox()
        self.cmb_profile.addItem("Default")
        self.cmb_profile.currentTextChanged.connect(self._on_profile_changed)
        btn_new = QPushButton("+")
        btn_new.setFixedWidth(28)
        btn_new.setToolTip("Nuevo perfil")
        btn_new.clicked.connect(self._new_profile)
        btn_del = QPushButton("−")
        btn_del.setFixedWidth(28)
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self._delete_profile)
        prof_row.addWidget(self.cmb_profile, 1)
        prof_row.addWidget(btn_new)
        prof_row.addWidget(btn_del)

        btn_save   = QPushButton("💾  Guardar perfil")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save_profile)
        btn_load   = QPushButton("📂  Cargar .cfg")
        btn_load.clicked.connect(self._load_profile_file)
        btn_export = QPushButton("📤  Exportar JoyToKey")
        btn_export.clicked.connect(self._export_joytokey)
        btn_clear  = QPushButton("🗑  Limpiar todo")
        btn_clear.setObjectName("btn_danger")
        btn_clear.clicked.connect(self._clear_layout)

        prof_lay.addLayout(prof_row)
        for b in [btn_save, btn_load, btn_export, btn_clear]:
            prof_lay.addWidget(b)

        # TeknoParrot
        gb_tp = QGroupBox("TeknoParrot")
        tp_lay = QVBoxLayout(gb_tp)
        tp_lay.setSpacing(6)
        lbl_tp = QLabel("UserProfile:")
        lbl_tp.setStyleSheet("color:#5a6278;font-size:11px;")
        tp_row = QHBoxLayout()
        self.inp_tp = QLineEdit()
        self.inp_tp.setPlaceholderText("Ruta al .xml de perfil")
        btn_tp = QPushButton("…")
        btn_tp.setFixedWidth(28)
        btn_tp.clicked.connect(self._browse_tp)
        tp_row.addWidget(self.inp_tp)
        tp_row.addWidget(btn_tp)
        btn_tp_apply = QPushButton("Aplicar en módulo RL")
        btn_tp_apply.setObjectName("btn_primary")
        btn_tp_apply.clicked.connect(self._apply_tp)
        tp_lay.addWidget(lbl_tp)
        tp_lay.addLayout(tp_row)
        tp_lay.addWidget(btn_tp_apply)

        # PCLauncher
        gb_pc = QGroupBox("PCLauncher")
        pc_lay = QVBoxLayout(gb_pc)
        pc_lay.setSpacing(6)
        lbl_pc = QLabel("Exe del juego:")
        lbl_pc.setStyleSheet("color:#5a6278;font-size:11px;")
        pc_row = QHBoxLayout()
        self.inp_pc = QLineEdit()
        self.inp_pc.setPlaceholderText("C:\\Games\\juego.exe")
        btn_pc = QPushButton("…")
        btn_pc.setFixedWidth(28)
        btn_pc.clicked.connect(self._browse_pc)
        pc_row.addWidget(self.inp_pc)
        pc_row.addWidget(btn_pc)
        btn_pc_apply = QPushButton("Aplicar en Games.ini")
        btn_pc_apply.setObjectName("btn_primary")
        btn_pc_apply.clicked.connect(self._apply_pc)
        pc_lay.addWidget(lbl_pc)
        pc_lay.addLayout(pc_row)
        pc_lay.addWidget(btn_pc_apply)

        # Resumen
        gb_sum = QGroupBox("Asignaciones actuales")
        sum_lay = QVBoxLayout(gb_sum)
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setFixedHeight(100)
        self.txt_summary.setStyleSheet(
            "QTextEdit{background:#080a0f;border:1px solid #1e2330;"
            "color:#4a6080;font-family:Consolas,monospace;font-size:11px;"
            "border-radius:4px;}")
        sum_lay.addWidget(self.txt_summary)

        for w_item in [gb_prof, gb_tp, gb_pc, gb_sum]:
            lay.addWidget(w_item)
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
        new_palette = ActionPalette(ARCADE_ACTIONS if is_arcade else GAMEPAD_ACTIONS)
        splitter = self._palette.parent()
        if splitter:
            idx = splitter.indexOf(self._palette)
            self._palette.deleteLater()
            self._palette = new_palette
            splitter.insertWidget(idx, self._palette)
        self._update_label()

    def _on_assignment_changed(self, slot_id: str, action: str):
        self._update_summary()

    def _update_label(self):
        sys_lbl  = self._current_system or "Todos"
        mode_lbl = "Arcade" if self._current_mode == "arcade" else "Gamepad"
        self.lbl_active.setText(
            f"Sistema: {sys_lbl}  ·  Perfil: {self._current_profile}  ·  Modo: {mode_lbl}")

    def _update_summary(self):
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        lines = [f"{sid:<18} → {act}"
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
        self._set_mode(mode)
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
                    self.parent.statusBar().showMessage(f"✓ Perfil '{name}' guardado.", 4000)
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", str(e))

    def _save_system_joytokey_cfg(self):
        """Exporta también el perfil base de JoyToKey por sistema al guardar."""
        system_name = (self._current_system or "").strip()
        rl_dir = (self._config.get("rocketlauncher_dir", "") or "").strip()
        if not system_name or not rl_dir:
            return

        joy_dir = os.path.join(rl_dir, "Profiles", "JoyToKey", system_name)
        cfg_path = os.path.join(joy_dir, f"{system_name}.cfg")
        content = make_joytokey_cfg(system_name)
        os.makedirs(joy_dir, exist_ok=True)

        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                    current = f.read()
                if current != content:
                    ok = QMessageBox.question(
                        self.parent, "JoyToKey existente",
                        f"Ya existe:\n{cfg_path}\n\n¿Sobrescribir con la plantilla del sistema?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
                    if ok != QMessageBox.StandardButton.Yes:
                        return
            except Exception:
                return

        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _new_profile(self):
        name, ok = QInputDialog.getText(self.parent, "Nuevo perfil", "Nombre:")
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
            self.parent, "Eliminar perfil", f"¿Eliminar '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
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
            QMessageBox.critical(self.parent, "Error", str(e))

    def _export_joytokey(self):
        layout = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        asgn   = layout.get_assignments()
        if not asgn:
            QMessageBox.information(self.parent, "Sin asignaciones", "No hay asignaciones.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.parent, "Exportar JoyToKey",
            f"{self._current_profile}_{self._current_mode}.cfg", "JoyToKey (*.cfg)")
        if not path:
            return
        lines = [
            f"; HyperSpin Manager — JoyToKey Export",
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
            QMessageBox.critical(self.parent, "Error", str(e))

    def _clear_layout(self):
        reply = QMessageBox.question(
            self.parent, "Limpiar", "¿Eliminar todas las asignaciones?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
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
                                "Selecciona sistema y ruta del perfil TP.")
            return
        emu_ini = os.path.join(rl, "Settings", sys_name, "../../../Downloads/Emulators.ini")
        if not os.path.isfile(emu_ini):
            QMessageBox.warning(self.parent, "Sin Emulators.ini", f"No encontrado:\n{emu_ini}")
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
                self.parent.statusBar().showMessage("✓ UserProfile TeknoParrot actualizado.", 5000)
        else:
            QMessageBox.information(self.parent, "Sin sección",
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
        games_ini = os.path.join(rl, "Settings", sys_name, "../../../Downloads/Games.ini")
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
            self.parent.statusBar().showMessage(f"✓ Exe_Path actualizado en Games.ini.", 5000)
