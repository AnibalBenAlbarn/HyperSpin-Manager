"""
tabs/controls.py
ControlsTab — Editor visual de perfiles de control para HyperSpin Manager

v4 — Layout visual estilo PCSX2/Citron:
 - GamepadWidget: mando Xbox dibujado en QPainter, botones clicables superpuestos
 - ArcadeWidget:  panel arcade dibujado (cuerpo madera, stick real, botonera)
 - Sin dependencia de PNGs externos — todo se dibuja con PyQt6
 - Texto con alto contraste, fuentes claras
"""

import os
import json
import math
import configparser
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QLineEdit,
    QScrollArea, QFrame, QSplitter,
    QFileDialog, QMessageBox, QInputDialog,
    QSizePolicy, QTextEdit, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox
)
from PyQt6.QtCore import (
    Qt, QMimeData, QRect, QRectF, QPointF,
    pyqtSignal, QTimer, QPoint, QSize
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics,
    QDrag, QPixmap, QRadialGradient, QLinearGradient,
    QPolygon, QPolygonF, QPainterPath
)

try:
    from tabs.create_system import make_joytokey_cfg
except ImportError:
    def make_joytokey_cfg(name: str) -> str:
        return f"; JoyToKey cfg for {name}\n[General]\nFileVersion=51\n"

try:
    from main import TabModule
except ImportError:
    class TabModule:
        tab_title = "Modulo"
        tab_icon = ""
        def __init__(self, parent): self.parent = parent
        def widget(self): raise NotImplementedError
        def load_data(self, config): pass
        def save_data(self): return {}


# ─── Paleta ───────────────────────────────────────────────────────────────────
_AMBER  = "#f5a623"
_CYAN   = "#00c9e8"
_GREEN  = "#00e599"
_DEEP   = "#05070b"
_BASE   = "#090c12"
_RAISED = "#0d1018"
_CARD   = "#0a0d14"
_BORDER = "#1a2035"
_MID    = "#243050"
_TXT_HI = "#ffffff"
_TXT_MD = "#dde6f8"
_TXT_LO = "#b0c4e8"
_TXT_GH = "#8099cc"
_MONO   = "'Consolas', 'Courier New', monospace"

_COL_A    = "#1db954"
_COL_B    = "#e8192c"
_COL_X    = "#2a6bbf"
_COL_Y    = "#f5c518"
_COL_BUMP = "#3a4a6a"
_COL_TRIG = "#2a3a5a"
_COL_STICK= "#222840"
_COL_DPAD = "#1e2840"
_COL_SYS  = "#1a2030"

ARCADE_ACTIONS = [
    "Start P1", "Start P2", "Coin P1", "Coin P2",
    "Pause", "Exit", "Config",
    "Button 1", "Button 2", "Button 3", "Button 4",
    "Button 5", "Button 6", "Button 7", "Button 8",
    "Up", "Down", "Left", "Right",
    "Service", "Test", "---",
]

GAMEPAD_ACTIONS = [
    "A -- Confirmar/Accion", "B -- Cancelar/Volver",
    "X -- Acc. Secundaria",  "Y -- Acc. Terciaria",
    "LB -- Bumper Izq", "RB -- Bumper Der",
    "LT -- Gatillo Izq", "RT -- Gatillo Der",
    "L3 -- Pulsar Stick Izq", "R3 -- Pulsar Stick Der",
    "Start", "Select / Back",
    "D-Up", "D-Down", "D-Left", "D-Right",
    "LS -- Mover Personaje", "RS -- Mover Camara",
    "Pause", "Exit", "---",
]

ACTION_COLORS = {
    "Start P1": "#1565c0", "Start P2": "#1565c0",
    "Coin P1": "#4a148c", "Coin P2": "#4a148c",
    "Pause": "#1b5e20", "Exit": "#b71c1c", "Config": "#e65100",
    "Button 1": "#c62828", "Button 2": "#283593",
    "Button 3": "#1b5e20", "Button 4": "#c47800",
    "Button 5": "#880e4f", "Button 6": "#006064",
    "Button 7": "#37474f", "Button 8": "#4e342e",
    "---": "#1e2330",
}
DEFAULT_ACTION_COLOR = "#1e3a5f"


def action_color(action: str) -> str:
    if not action or action == "---":
        return "#1e2330"
    return ACTION_COLORS.get(action, DEFAULT_ACTION_COLOR)


# ══════════════════════════════════════════════════════════════════════════════
#  ActionPickerDialog
# ══════════════════════════════════════════════════════════════════════════════

class ActionPickerDialog(QDialog):
    def __init__(self, actions: list, current: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar accion")
        self.setMinimumSize(320, 420)
        self.setStyleSheet(
            f"QDialog{{background:{_BASE};color:{_TXT_HI};}}"
            f"QListWidget{{background:{_RAISED};border:1px solid {_BORDER};"
            f"color:{_TXT_HI};font-size:13px;border-radius:6px;}}"
            f"QListWidget::item:selected{{background:{_MID};color:{_AMBER};}}"
            f"QListWidget::item:hover{{background:#111a28;}}"
            f"QLineEdit{{background:{_RAISED};border:1px solid {_BORDER};"
            f"color:{_TXT_HI};font-size:13px;border-radius:5px;padding:4px 8px;}}")
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filtrar...")
        self._search.textChanged.connect(self._filter)
        lay.addWidget(self._search)
        self._list = QListWidget()
        self._all  = actions
        self._populate(actions, current)
        lay.addWidget(self._list, 1)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.setStyleSheet(
            f"QPushButton{{background:{_MID};color:{_TXT_HI};border:1px solid {_BORDER};"
            f"border-radius:5px;padding:5px 18px;font-weight:700;}}"
            f"QPushButton:hover{{background:{_BORDER};color:{_AMBER};}}")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._list.itemDoubleClicked.connect(lambda _: self.accept())

    def _populate(self, actions, current=""):
        self._list.clear()
        for a in actions:
            item = QListWidgetItem(a)
            item.setForeground(QColor(_TXT_HI))
            self._list.addItem(item)
            if a == current:
                self._list.setCurrentItem(item)

    def _filter(self, text: str):
        self._populate([a for a in self._all if text.lower() in a.lower()])

    def selected_action(self) -> str:
        item = self._list.currentItem()
        return item.text() if item else ""


# ══════════════════════════════════════════════════════════════════════════════
#  ControlZone — zona clicable superpuesta
# ══════════════════════════════════════════════════════════════════════════════

class ControlZone(QWidget):
    assignment_changed = pyqtSignal(str, str)

    def __init__(self, slot_id: str, label: str, actions: list,
                 shape: str = "ellipse", color: str = "", size: int = 44,
                 parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.label   = label
        self.actions = actions
        self.shape   = shape
        self._color  = color or _COL_SYS
        self._sz     = size
        self.action  = ""
        self._hover  = False
        self.setFixedSize(size, size)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setToolTip(f"{label} — clic para asignar · clic derecho = borrar")

    def set_action(self, action: str):
        self.action = action
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        base = QColor(self._color)
        if self.action and self.action != "---":
            base = QColor(action_color(self.action))
        if self._hover:
            base = base.lighter(160)

        path = QPainterPath()
        if self.shape == "ellipse":
            path.addEllipse(QRectF(2, 2, w - 4, h - 4))
        elif self.shape == "pill":
            path.addRoundedRect(QRectF(2, 2, w - 4, h - 4), 8, 8)
        else:
            path.addRoundedRect(QRectF(2, 2, w - 4, h - 4), 6, 6)

        # sombra
        p.save(); p.translate(2, 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 100)))
        p.drawPath(path); p.restore()

        grad = QRadialGradient(w * 0.35, h * 0.30, max(w, h) * 0.8)
        grad.setColorAt(0, base.lighter(130))
        grad.setColorAt(1, base)
        p.setBrush(QBrush(grad))
        border = QColor(_AMBER) if self._hover else base.lighter(170)
        p.setPen(QPen(border, 1.8 if self._hover else 1.2))
        p.drawPath(path)

        # brillo
        hi = QPainterPath()
        hi.addEllipse(QRectF(w * 0.2, h * 0.1, w * 0.45, h * 0.28))
        hi_g = QLinearGradient(0, h * 0.1, 0, h * 0.4)
        hi_g.setColorAt(0, QColor(255, 255, 255, 60))
        hi_g.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hi_g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(hi)

        # etiqueta fija (letra del slot)
        p.setFont(QFont("Segoe UI", max(7, self._sz // 6), QFont.Weight.Bold))
        p.setPen(QPen(QColor(255, 255, 255, 220)))
        p.drawText(QRect(0, 0, w, h - 2),
                   Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, self.label)

        # accion asignada
        if self.action and self.action != "---":
            short = self.action.split("--")[0].strip() if "--" in self.action else self.action
            short = short[:8]
            p.setFont(QFont("Consolas", max(5, self._sz // 9), QFont.Weight.Bold))
            p.setPen(QPen(QColor(255, 255, 255, 240)))
            p.drawText(QRect(1, 2, w - 2, h - 12), Qt.AlignmentFlag.AlignCenter, short)
        else:
            p.setBrush(QBrush(QColor(255, 255, 255, 40)))
            p.setPen(Qt.PenStyle.NoPen)
            r = max(3, self._sz // 10)
            p.drawEllipse(w // 2 - r, h // 2 - r - 3, r * 2, r * 2)

    def enterEvent(self, e):  self._hover = True;  self.update()
    def leaveEvent(self, e):  self._hover = False; self.update()

    def _pick(self):
        dlg = ActionPickerDialog(self.actions, self.action, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            act = dlg.selected_action()
            if act:
                self.set_action(act)
                self.assignment_changed.emit(self.slot_id, act)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick()

    def contextMenuEvent(self, event):
        self.set_action("")
        self.assignment_changed.emit(self.slot_id, "")

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            self._hover = True; self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._hover = False; self.update()

    def dropEvent(self, event):
        self._hover = False
        act = event.mimeData().text()
        self.set_action(act)
        self.assignment_changed.emit(self.slot_id, act)
        event.acceptProposedAction()


# ══════════════════════════════════════════════════════════════════════════════
#  GamepadCanvas — mando Xbox dibujado en QPainter
# ══════════════════════════════════════════════════════════════════════════════

class GamepadCanvas(QWidget):
    """Dibuja el mando Xbox sin widgets encima — solo la imagen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(480, 340)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw(p, self.width(), self.height())

    def _draw(self, p: QPainter, W: int, H: int):
        px = int(W * 0.04); py = int(H * 0.05)
        ew = W - px * 2;    eh = H - py * 2

        def cx(r): return int(px + r * ew)
        def cy(r): return int(py + r * eh)
        def sz(r): return int(min(ew, eh) * r)

        bx, by = cx(0.06), cy(0.12)
        bw = cx(0.94) - bx
        bh = cy(0.90) - by

        # ── cuerpo ──
        body = QPainterPath()
        body.moveTo(bx + bw * 0.24, by)
        body.lineTo(bx + bw * 0.76, by)
        body.quadTo(bx + bw, by, bx + bw, by + bh * 0.36)
        body.lineTo(bx + bw, by + bh * 0.54)
        body.quadTo(bx + bw * 0.95, by + bh * 0.84, bx + bw * 0.78, by + bh)
        body.lineTo(bx + bw * 0.58, by + bh)
        body.quadTo(bx + bw * 0.50, by + bh * 0.77, bx + bw * 0.50, by + bh * 0.74)
        body.quadTo(bx + bw * 0.50, by + bh * 0.77, bx + bw * 0.42, by + bh)
        body.lineTo(bx + bw * 0.22, by + bh)
        body.quadTo(bx + bw * 0.05, by + bh * 0.84, bx, by + bh * 0.54)
        body.lineTo(bx, by + bh * 0.36)
        body.quadTo(bx, by, bx + bw * 0.24, by)
        body.closeSubpath()

        p.save(); p.translate(4, 5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 90)))
        p.drawPath(body); p.restore()

        bg = QLinearGradient(0, by, 0, by + bh)
        bg.setColorAt(0.0, QColor("#303030"))
        bg.setColorAt(0.5, QColor("#1c1c1c"))
        bg.setColorAt(1.0, QColor("#101010"))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor("#484848"), 1.5))
        p.drawPath(body)

        # brillo superior
        hi = QPainterPath()
        hi.moveTo(bx + bw * 0.28, by + 2)
        hi.quadTo(bx + bw * 0.5, by - 5, bx + bw * 0.72, by + 2)
        hi.quadTo(bx + bw * 0.5, by + bh * 0.14, bx + bw * 0.28, by + 2)
        hi_g = QLinearGradient(0, by, 0, by + bh * 0.14)
        hi_g.setColorAt(0, QColor(255, 255, 255, 30))
        hi_g.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hi_g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(hi)

        # zona central
        mid_cx, mid_cy = cx(0.5), cy(0.38)
        mid_w, mid_h   = sz(0.26), sz(0.20)
        mid_p = QPainterPath()
        mid_p.addRoundedRect(
            QRectF(mid_cx - mid_w / 2, mid_cy - mid_h / 2, mid_w, mid_h), 10, 10)
        p.setBrush(QBrush(QColor("#262626")))
        p.setPen(QPen(QColor("#363636"), 1))
        p.drawPath(mid_p)

        # LED verde
        led_r = sz(0.033)
        lx, ly = cx(0.5), cy(0.26)
        lg = QRadialGradient(lx - led_r * 0.3, ly - led_r * 0.3, led_r * 1.5)
        lg.setColorAt(0, QColor("#55ff75"))
        lg.setColorAt(0.5, QColor("#10b030"))
        lg.setColorAt(1, QColor("#004010"))
        p.setBrush(QBrush(lg))
        p.setPen(QPen(QColor("#007020"), 1))
        p.drawEllipse(lx - led_r, ly - led_r, led_r * 2, led_r * 2)

        # sticks
        for rx, ry in [(0.35, 0.52), (0.65, 0.68)]:
            scx, scy = cx(rx), cy(ry)
            sr = sz(0.068)
            sg = QRadialGradient(scx - sr * 0.3, scy - sr * 0.3, sr * 1.6)
            sg.setColorAt(0, QColor("#505050"))
            sg.setColorAt(0.6, QColor("#262626"))
            sg.setColorAt(1, QColor("#141414"))
            p.setBrush(QBrush(sg))
            p.setPen(QPen(QColor("#606060"), 1.5))
            p.drawEllipse(scx - sr, scy - sr, sr * 2, sr * 2)
            p.setPen(QPen(QColor("#363636"), 1))
            p.drawLine(int(scx), int(scy - sr + 5), int(scx), int(scy + sr - 5))
            p.drawLine(int(scx - sr + 5), int(scy), int(scx + sr - 5), int(scy))

        # D-Pad
        dp_cx, dp_cy = cx(0.28), cy(0.71)
        dp_arm = sz(0.044)
        dp_wid = int(dp_arm * 0.62)
        p.setBrush(QBrush(QColor("#2c2c2c")))
        p.setPen(QPen(QColor("#484848"), 1))
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            r = QRect(
                dp_cx + dx * dp_arm - dp_wid // 2,
                dp_cy + dy * dp_arm - dp_wid // 2,
                dp_wid, dp_arm)
            p.drawRoundedRect(r, 2, 2)

        # bumpers
        for rx, sign in [(0.20, -1), (0.80, 1)]:
            bcx, bcy = cx(rx), cy(0.20)
            bw2, bh2 = sz(0.12), sz(0.048)
            bp = QPainterPath()
            if sign == -1:
                bp.moveTo(bcx, bcy + bh2 // 2)
                bp.quadTo(bcx - bw2 * 0.3, bcy - bh2,
                          bcx + bw2 * 0.6, bcy - bh2 // 2)
                bp.lineTo(bcx + bw2 * 0.6, bcy + bh2 // 2)
                bp.closeSubpath()
            else:
                bp.moveTo(bcx, bcy + bh2 // 2)
                bp.quadTo(bcx + bw2 * 0.3, bcy - bh2,
                          bcx - bw2 * 0.6, bcy - bh2 // 2)
                bp.lineTo(bcx - bw2 * 0.6, bcy + bh2 // 2)
                bp.closeSubpath()
            p.setBrush(QBrush(QColor("#2a2a38")))
            p.setPen(QPen(QColor("#3e3e50"), 1))
            p.drawPath(bp)

        # botones cara
        face = [
            (0.78, 0.42, _COL_Y, "Y"),
            (0.71, 0.54, _COL_X, "X"),
            (0.85, 0.54, _COL_B, "B"),
            (0.78, 0.66, _COL_A, "A"),
        ]
        for rx, ry, col, lbl in face:
            fcx, fcy = cx(rx), cy(ry)
            fr = sz(0.036)
            fg = QRadialGradient(fcx - fr * 0.3, fcy - fr * 0.4, fr * 1.6)
            c = QColor(col)
            fg.setColorAt(0, c.lighter(150))
            fg.setColorAt(0.6, c)
            fg.setColorAt(1, c.darker(150))
            p.setBrush(QBrush(fg))
            p.setPen(QPen(c.darker(130), 1.2))
            p.drawEllipse(int(fcx - fr), int(fcy - fr), int(fr * 2), int(fr * 2))
            p.setFont(QFont("Segoe UI", max(6, int(fr * 0.9)), QFont.Weight.Bold))
            p.setPen(QPen(QColor(255, 255, 255, 230)))
            p.drawText(QRect(int(fcx - fr), int(fcy - fr), int(fr * 2), int(fr * 2)),
                       Qt.AlignmentFlag.AlignCenter, lbl)

        # SELECT / START (rectangulos pequeños)
        for rx, lbl in [(0.42, "SEL"), (0.58, "STA")]:
            scx2, scy2 = cx(rx), cy(0.42)
            sw, sh2 = sz(0.06), sz(0.04)
            p.setBrush(QBrush(QColor("#1e1e2e")))
            p.setPen(QPen(QColor("#383850"), 1))
            p.drawRoundedRect(int(scx2 - sw // 2), int(scy2 - sh2 // 2), sw, sh2, 4, 4)
            p.setFont(QFont("Consolas", max(5, sz(0.022)), QFont.Weight.Bold))
            p.setPen(QPen(QColor(_TXT_GH)))
            p.drawText(QRect(int(scx2 - sw // 2), int(scy2 - sh2 // 2), sw, sh2),
                       Qt.AlignmentFlag.AlignCenter, lbl)


# ══════════════════════════════════════════════════════════════════════════════
#  GamepadWidget — canvas + ControlZones superpuestas
# ══════════════════════════════════════════════════════════════════════════════

class GamepadWidget(QWidget):
    slot_changed = pyqtSignal(str, str)

    _ZONE_DEFS = [
        # (cx_rel, cy_rel, sid, label, shape, color, sz_rel)
        (0.17, 0.08, "lt",         "LT",  "pill",    _COL_TRIG,  0.088),
        (0.83, 0.08, "rt",         "RT",  "pill",    _COL_TRIG,  0.088),
        (0.20, 0.20, "lb",         "LB",  "pill",    _COL_BUMP,  0.080),
        (0.80, 0.20, "rb",         "RB",  "pill",    _COL_BUMP,  0.080),
        (0.78, 0.42, "btn_y",      "Y",   "ellipse", _COL_Y,     0.070),
        (0.71, 0.54, "btn_x",      "X",   "ellipse", _COL_X,     0.070),
        (0.85, 0.54, "btn_b",      "B",   "ellipse", _COL_B,     0.070),
        (0.78, 0.66, "btn_a",      "A",   "ellipse", _COL_A,     0.070),
        (0.28, 0.61, "dpad_up",    "U",   "rect",    _COL_DPAD,  0.055),
        (0.28, 0.80, "dpad_down",  "D",   "rect",    _COL_DPAD,  0.055),
        (0.19, 0.70, "dpad_left",  "L",   "rect",    _COL_DPAD,  0.055),
        (0.37, 0.70, "dpad_right", "R",   "rect",    _COL_DPAD,  0.055),
        (0.35, 0.52, "ls",         "LS",  "ellipse", _COL_STICK, 0.100),
        (0.65, 0.68, "rs",         "RS",  "ellipse", _COL_STICK, 0.100),
        (0.42, 0.42, "select",     "SEL", "rect",    _COL_SYS,   0.065),
        (0.58, 0.42, "start",      "STA", "rect",    _COL_SYS,   0.065),
        (0.50, 0.35, "home",       "X",   "ellipse", "#1a3a1a",  0.068),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._zones: dict = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(480, 340)

        # Canvas de fondo (no intercepta eventos)
        self._canvas = GamepadCanvas(self)
        self._canvas.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._zones_built = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._canvas.setGeometry(0, 0, self.width(), self.height())
        self._reposition()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._zones_built:
            self._build_zones()
        QTimer.singleShot(30, self._reposition)

    def _build_zones(self):
        self._zones_built = True
        ref = min(self.width(), self.height())
        for (cx_r, cy_r, sid, lbl, shape, col, sz_r) in self._ZONE_DEFS:
            sz = max(34, int(ref * sz_r * 1.1))
            z = ControlZone(sid, lbl, GAMEPAD_ACTIONS, shape, col, sz, self)
            z.assignment_changed.connect(self._on_zone)
            self._zones[sid] = z
            z.show()
        self._reposition()

    def _reposition(self):
        W, H = self.width(), self.height()
        if W == 0 or H == 0:
            return
        px = int(W * 0.04); py = int(H * 0.05)
        ew = W - px * 2;    eh = H - py * 2
        ref = min(W, H)
        for (cx_r, cy_r, sid, lbl, shape, col, sz_r) in self._ZONE_DEFS:
            z = self._zones.get(sid)
            if not z:
                continue
            sz = max(34, int(ref * sz_r * 1.1))
            z.setFixedSize(sz, sz)
            x = int(px + cx_r * ew) - sz // 2
            y = int(py + cy_r * eh) - sz // 2
            z.move(x, y)

    def _on_zone(self, sid, action):
        self.assignments[sid] = action
        self.slot_changed.emit(sid, action)

    def get_assignments(self): return dict(self.assignments)
    def set_assignments(self, data):
        self.assignments = dict(data)
        for sid, z in self._zones.items(): z.set_action(data.get(sid, ""))
    def clear_all(self):
        self.assignments = {}
        for z in self._zones.values(): z.set_action("")


# ══════════════════════════════════════════════════════════════════════════════
#  GamepadLayout (wrapper)
# ══════════════════════════════════════════════════════════════════════════════

class GamepadLayout(QWidget):
    slot_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._slots:      dict = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        hint = QLabel("  Clic en cada control para asignar · arrastra accion desde la paleta · clic derecho = borrar")
        hint.setStyleSheet(f"font-size:11px;color:{_TXT_GH};background:transparent;font-family:{_MONO};")
        lay.addWidget(hint)
        self._gw = GamepadWidget()
        self._gw.slot_changed.connect(self._relay)
        lay.addWidget(self._gw, 1)
        self._slots = self._gw._zones

    def _relay(self, sid, action):
        self.assignments[sid] = action
        self._slots = self._gw._zones
        self.slot_changed.emit(sid, action)

    def set_theme(self, theme: str): pass
    def get_assignments(self): return self._gw.get_assignments()
    def set_assignments(self, data):
        self._gw.set_assignments(data)
        self.assignments = dict(data)
    def clear_all(self):
        self._gw.clear_all()
        self.assignments = {}


# ══════════════════════════════════════════════════════════════════════════════
#  ArcadeStickDrawing — joystick arcade dibujado
# ══════════════════════════════════════════════════════════════════════════════

class ArcadeStickDrawing(QWidget):
    def __init__(self, accent: str = _AMBER, gate: str = "octagonal", parent=None):
        super().__init__(parent)
        self.accent_color = QColor(accent)
        self.gate = gate
        self.setMinimumSize(80, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_accent(self, color: str): self.accent_color = QColor(color); self.update()
    def set_gate(self, gate: str):    self.gate = gate;                   self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        s  = min(W, H)
        cx = W // 2
        cy = H // 2 + int(s * 0.08)

        base_r  = int(s * 0.36)
        shaft_w = max(6, int(s * 0.10))
        shaft_h = int(s * 0.34)
        ball_r  = max(10, int(s * 0.16))
        gate_s  = int(base_r * 0.68)

        # gate
        p.setPen(QPen(QColor("#2a2a2a"), 1.5))
        p.setBrush(QBrush(QColor("#0e0e0e")))
        if self.gate == "octagonal":
            hg = gate_s // 2
            pts = [
                QPoint(cx - hg, cy - gate_s), QPoint(cx + hg, cy - gate_s),
                QPoint(cx + gate_s, cy - hg), QPoint(cx + gate_s, cy + hg),
                QPoint(cx + hg, cy + gate_s), QPoint(cx - hg, cy + gate_s),
                QPoint(cx - gate_s, cy + hg), QPoint(cx - gate_s, cy - hg),
            ]
            p.drawPolygon(QPolygon(pts))
        elif self.gate == "square":
            p.drawRect(cx - gate_s, cy - gate_s, gate_s * 2, gate_s * 2)
        else:
            p.drawEllipse(cx - gate_s, cy - gate_s, gate_s * 2, gate_s * 2)

        # base
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 80)))
        p.drawEllipse(cx - base_r + 3, cy - base_r + 3, base_r * 2, base_r * 2)
        bg = QRadialGradient(cx - base_r // 4, cy - base_r // 4, base_r * 1.4)
        bg.setColorAt(0, QColor("#505050"))
        bg.setColorAt(0.5, QColor("#2c2c2c"))
        bg.setColorAt(1, QColor("#141414"))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor("#606060"), 1.5))
        p.drawEllipse(cx - base_r, cy - base_r, base_r * 2, base_r * 2)
        p.setPen(QPen(QColor("#0a0a0a"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - base_r + 6, cy - base_r + 6, (base_r - 6) * 2, (base_r - 6) * 2)

        # shaft
        sx = cx - shaft_w // 2
        shaft_top = cy - shaft_h
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 90)))
        p.drawRoundedRect(sx + 3, shaft_top + 3, shaft_w, shaft_h, shaft_w // 2, shaft_w // 2)
        sg = QLinearGradient(sx, 0, sx + shaft_w, 0)
        sg.setColorAt(0, QColor("#585858")); sg.setColorAt(0.35, QColor("#c8c8c8"))
        sg.setColorAt(0.65, QColor("#888888")); sg.setColorAt(1, QColor("#303030"))
        p.setBrush(QBrush(sg))
        p.setPen(QPen(QColor("#1e1e1e"), 1))
        p.drawRoundedRect(sx, shaft_top, shaft_w, shaft_h, shaft_w // 2, shaft_w // 2)

        # ball
        ball_cx, ball_cy = cx, shaft_top + ball_r // 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 90)))
        p.drawEllipse(ball_cx - ball_r + 2, ball_cy - ball_r + 2, ball_r * 2, ball_r * 2)
        acc = self.accent_color
        bg2 = QRadialGradient(ball_cx - ball_r // 3, ball_cy - ball_r // 3, ball_r * 1.5)
        bg2.setColorAt(0, acc.lighter(190)); bg2.setColorAt(0.4, acc); bg2.setColorAt(1, acc.darker(170))
        p.setBrush(QBrush(bg2))
        p.setPen(QPen(acc.darker(140), 1.5))
        p.drawEllipse(ball_cx - ball_r, ball_cy - ball_r, ball_r * 2, ball_r * 2)
        hi_r = max(3, ball_r // 3)
        hi_x, hi_y = ball_cx - ball_r // 3, ball_cy - ball_r // 3
        hg2 = QRadialGradient(hi_x, hi_y, hi_r * 2)
        hg2.setColorAt(0, QColor(255, 255, 255, 210)); hg2.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hg2)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(hi_x - hi_r, hi_y - hi_r, hi_r * 2, hi_r * 2)

        # gate label
        gl = {"octagonal": "OCT", "square": "SQR", "circular": "CIR"}.get(self.gate, "")
        p.setFont(QFont("Consolas", max(6, s // 16)))
        p.setPen(QPen(QColor(_TXT_GH)))
        p.drawText(QRect(cx - 25, cy + base_r - 14, 50, 14), Qt.AlignmentFlag.AlignCenter, gl)


# ══════════════════════════════════════════════════════════════════════════════
#  ArcadeWidget — panel arcade con stick + botonera
# ══════════════════════════════════════════════════════════════════════════════

class ArcadeWidget(QWidget):
    slot_changed = pyqtSignal(str, str)

    def __init__(self, btn_mode: int = 8, parent=None):
        super().__init__(parent)
        self._btn_mode = btn_mode
        self.assignments: dict = {}
        self._zones: dict = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(600, 280)
        self._build()

    def _build(self):
        for z in list(self._zones.values()):
            z.setParent(None); z.deleteLater()
        self._zones = {}

        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget(): item.widget().setParent(None)
            QWidget().setLayout(old)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(16)

        root.addLayout(self._build_player("p1", _AMBER), 5)
        root.addWidget(self._build_center(), 2)
        root.addLayout(self._build_player("p2", _CYAN), 5)

    def _build_player(self, player: str, accent: str) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{accent};font-size:10px;background:transparent;")
        name = QLabel(f"PLAYER {'1' if player == 'p1' else '2'}")
        name.setStyleSheet(
            f"color:{accent};font-size:13px;font-weight:800;"
            f"letter-spacing:2px;font-family:{_MONO};background:transparent;")
        hdr.addWidget(dot); hdr.addWidget(name); hdr.addStretch()
        lay.addLayout(hdr)

        inner = QHBoxLayout()
        inner.setSpacing(12)

        # Columna stick
        sc = QVBoxLayout(); sc.setSpacing(4)

        lbl_s = QLabel("PALANCA")
        lbl_s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_s.setStyleSheet(
            f"font-size:10px;font-weight:800;letter-spacing:1px;"
            f"color:{_TXT_LO};font-family:{_MONO};background:transparent;")

        stick = ArcadeStickDrawing(accent=accent)
        stick.setObjectName(f"stick_{player}")
        stick.setMinimumSize(80, 100)
        stick.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        gate_cmb = QComboBox()
        gate_cmb.addItems(["Octagonal", "Cuadrado", "Circular"])
        gate_cmb.setFixedHeight(24)
        gate_cmb.setStyleSheet(
            f"QComboBox{{background:{_RAISED};border:1px solid {_BORDER};"
            f"border-radius:4px;color:{_TXT_MD};font-size:10px;padding:1px 6px;}}"
            f"QComboBox::drop-down{{border:none;width:14px;}}")
        gmap = {0: "octagonal", 1: "square", 2: "circular"}
        gate_cmb.currentIndexChanged.connect(lambda i, s=stick: s.set_gate(gmap[i]))

        dirs = QHBoxLayout(); dirs.setSpacing(2)
        dirs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for sid, arrow in [(f"{player}_up", "UP"), (f"{player}_dn", "DN"),
                           (f"{player}_lt", "LT"), (f"{player}_rt", "RT")]:
            z = ControlZone(sid, arrow, ARCADE_ACTIONS, "rect", _COL_DPAD, 32)
            z.assignment_changed.connect(self._on_zone)
            self._zones[sid] = z; z.setParent(self); z.show()
            dirs.addWidget(z)

        sc.addWidget(lbl_s); sc.addWidget(stick, 1)
        sc.addWidget(gate_cmb); sc.addLayout(dirs)
        inner.addLayout(sc, 3)

        # Columna botonera
        bc = QVBoxLayout(); bc.setSpacing(4)
        lbl_b = QLabel("BOTONERA")
        lbl_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_b.setStyleSheet(
            f"font-size:10px;font-weight:800;letter-spacing:1px;"
            f"color:{_TXT_LO};font-family:{_MONO};background:transparent;")
        bc.addWidget(lbl_b)

        gw = QWidget(); gw.setStyleSheet("background:transparent;")
        gw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(gw)
        grid.setSpacing(8); grid.setContentsMargins(0, 0, 0, 0)

        colors6 = ["#c62828","#283593","#006064","#c47800","#880e4f","#1b5e20"]
        colors8 = ["#c62828","#283593","#006064","#37474f",
                   "#c47800","#880e4f","#1b5e20","#4e342e"]

        if self._btn_mode == 6:
            pos = [(0,0),(0,1),(0,2),(1,0),(1,1),(1,2)]
            cols = colors6
        else:
            pos = [(0,0),(0,1),(0,2),(0,3),(1,0),(1,1),(1,2),(1,3)]
            cols = colors8

        for idx, (row, col) in enumerate(pos):
            num = idx + 1
            sid = f"{player}_b{num}"
            z = ControlZone(sid, f"B{num}", ARCADE_ACTIONS, "ellipse",
                            cols[idx] if idx < len(cols) else "#333344", 48)
            z.assignment_changed.connect(self._on_zone)
            self._zones[sid] = z; z.setParent(self); z.show()
            grid.addWidget(z, row, col, Qt.AlignmentFlag.AlignCenter)

        bc.addWidget(gw, 1)
        inner.addLayout(bc, 5)
        lay.addLayout(inner, 1)
        return lay

    def _build_center(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            f"QWidget{{background:#0a0c10;border:1px solid {_BORDER};border-radius:12px;}}")
        w.setMaximumWidth(150)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 12, 8, 12)
        lay.setSpacing(8)
        lay.addStretch()

        lbl = QLabel("CONTROLES")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"font-size:9px;font-weight:800;letter-spacing:2px;"
            f"color:{_TXT_GH};font-family:{_MONO};background:transparent;border:none;")
        lay.addWidget(lbl)

        for sid, txt, col in [
            ("p1_coin",  "1P COIN",  _COL_SYS),
            ("p1_start", "1P START", _COL_SYS),
            ("pause",    "PAUSE",    "#105010"),
            ("exit",     "EXIT",     "#7a1010"),
            ("p2_coin",  "2P COIN",  _COL_SYS),
            ("p2_start", "2P START", _COL_SYS),
        ]:
            z = ControlZone(sid, txt, ARCADE_ACTIONS, "rect", col, 38)
            z.assignment_changed.connect(self._on_zone)
            self._zones[sid] = z; z.setParent(self); z.show()
            lay.addWidget(z, 0, Qt.AlignmentFlag.AlignHCenter)

        lay.addStretch()
        return w

    def set_btn_mode(self, mode: int):
        if mode == self._btn_mode: return
        old = dict(self.assignments)
        self._btn_mode = mode
        self._build()
        for sid, act in old.items():
            if sid in self._zones:
                self._zones[sid].set_action(act)
                self.assignments[sid] = act

    def _on_zone(self, sid, action):
        self.assignments[sid] = action
        self.slot_changed.emit(sid, action)

    def get_assignments(self): return dict(self.assignments)
    def set_assignments(self, data):
        self.assignments = dict(data)
        for sid, z in self._zones.items(): z.set_action(data.get(sid, ""))
    def clear_all(self):
        self.assignments = {}
        for z in self._zones.values(): z.set_action("")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, W - 2, H - 2), 16, 16)
        grad = QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0.0, QColor("#1a1208"))
        grad.setColorAt(0.5, QColor("#120d06"))
        grad.setColorAt(1.0, QColor("#0c0806"))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#2a1e0a"), 2))
        p.drawPath(path)
        p.setPen(QPen(QColor(80, 50, 10, 18), 1))
        for y in range(0, H, 12):
            p.drawLine(0, y, W, y + 4)


# ══════════════════════════════════════════════════════════════════════════════
#  ArcadeLayout (wrapper)
# ══════════════════════════════════════════════════════════════════════════════

class ArcadeLayout(QWidget):
    slot_changed = pyqtSignal(str, str)
    MODE_6BTN = 6
    MODE_8BTN = 8

    def __init__(self, btn_mode: int = 8, parent=None):
        super().__init__(parent)
        self.assignments: dict = {}
        self._btn_mode = btn_mode
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("  Clic en cada control para asignar · arrastra accion desde la paleta · clic derecho = borrar")
        hint.setStyleSheet(f"font-size:11px;color:{_TXT_GH};background:transparent;font-family:{_MONO};")
        lay.addWidget(hint)
        self._aw = ArcadeWidget(btn_mode)
        self._aw.slot_changed.connect(self._relay)
        lay.addWidget(self._aw, 1)

    def _relay(self, sid, action):
        self.assignments[sid] = action
        self.slot_changed.emit(sid, action)

    def set_btn_mode(self, mode: int):
        self._btn_mode = mode
        self._aw.set_btn_mode(mode)

    def get_assignments(self): return self._aw.get_assignments()
    def set_assignments(self, data):
        self._aw.set_assignments(data); self.assignments = dict(data)
    def clear_all(self):
        self._aw.clear_all(); self.assignments = {}


# ══════════════════════════════════════════════════════════════════════════════
#  DraggableActionItem + ActionPalette
# ══════════════════════════════════════════════════════════════════════════════

class DraggableActionItem(QWidget):
    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = action
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(8)
        dot = QLabel("●")
        dot.setFixedWidth(10)
        dot.setStyleSheet(f"font-size:8px;color:{action_color(action)};background:transparent;")
        lbl = QLabel(action)
        lbl.setStyleSheet(f"font-size:13px;color:{_TXT_HI};background:transparent;")
        lay.addWidget(dot); lay.addWidget(lbl); lay.addStretch()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(self.action)
            drag.setMimeData(mime)
            pix = QPixmap(200, 32)
            pix.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = QColor(action_color(self.action))
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, 200, 32, 6, 6)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#ffffff")))
            painter.drawText(QRect(0, 0, 200, 32), Qt.AlignmentFlag.AlignCenter, self.action[:24])
            painter.end()
            drag.setPixmap(pix)
            drag.setHotSpot(event.pos())
            drag.exec(Qt.DropAction.CopyAction)


class ActionPalette(QWidget):
    def __init__(self, actions: list, parent=None):
        super().__init__(parent)
        self.setFixedWidth(195)
        self._build(actions)

    def _build(self, actions: list):
        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget(): item.widget().deleteLater()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        hdr = QWidget(); hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background:{_DEEP};border-bottom:1px solid {_BORDER};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12, 0, 12, 0)
        lbl = QLabel("ACCIONES  (arrastra)")
        lbl.setStyleSheet(
            f"font-size:10px;font-weight:800;letter-spacing:1px;"
            f"color:{_TXT_MD};font-family:{_MONO};background:transparent;")
        hl.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background:{_CARD};")

        content = QWidget(); content.setStyleSheet(f"background:{_CARD};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(4, 6, 4, 6); cl.setSpacing(1)
        for action in actions:
            cl.addWidget(DraggableActionItem(action))
        cl.addStretch()
        scroll.setWidget(content)
        lay.addWidget(hdr); lay.addWidget(scroll, 1)


# ══════════════════════════════════════════════════════════════════════════════
#  ControlsTab
# ══════════════════════════════════════════════════════════════════════════════

class ControlsTab(TabModule):
    tab_title = "Controles"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config:          dict         = {}
        self._systems:         list         = []
        self._current_system:  str          = ""
        self._current_profile: str          = "Default"
        self._current_mode:    str          = "arcade"
        self._current_btn_mode: int         = 8
        self._profiles:        dict         = {"Default": {}}
        self._main_widget:     Optional[QWidget] = None

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
        root.setStyleSheet(f"background:{_DEEP};")
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._build_toolbar())

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(f"QSplitter::handle{{background:{_BORDER};}}")

        self._palette     = ActionPalette(ARCADE_ACTIONS)
        self._editor_w    = self._build_editor()
        self._right_panel = self._build_right_panel()

        self._splitter.addWidget(self._palette)
        self._splitter.addWidget(self._editor_w)
        self._splitter.addWidget(self._right_panel)
        self._splitter.setSizes([195, 0, 275])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        rl.addWidget(self._splitter, 1)
        return root

    def _build_toolbar(self) -> QWidget:
        bar = QWidget(); bar.setFixedHeight(52)
        bar.setStyleSheet(f"background:{_DEEP};border-bottom:1px solid {_BORDER};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0); lay.setSpacing(10)

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

        def mode_btn(text):
            b = QPushButton(text); b.setCheckable(True); b.setFixedHeight(32)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(
                f"QPushButton{{background:{_RAISED};color:{_TXT_MD};border:1px solid {_BORDER};"
                f"border-radius:6px;padding:0 16px;font-weight:700;font-size:12px;}}"
                f"QPushButton:hover{{background:#111520;color:{_TXT_HI};border-color:{_MID};}}"
                f"QPushButton:checked{{background:#1a0e04;color:{_AMBER};border-color:{_AMBER};}}")
            return b

        def bm_btn(text, col):
            b = QPushButton(text); b.setCheckable(True); b.setFixedHeight(28)
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(
                f"QPushButton{{background:{_RAISED};color:{_TXT_LO};border:1px solid {_BORDER};"
                f"border-radius:5px;padding:0 14px;font-weight:800;font-size:11px;"
                f"font-family:{_MONO};}}"
                f"QPushButton:hover{{color:{_TXT_MD};border-color:{_MID};}}"
                f"QPushButton:checked{{background:#0a1520;color:{col};border-color:{col};}}")
            return b

        self.btn_arcade  = mode_btn("Arcade")
        self.btn_gamepad = mode_btn("Gamepad")
        self.btn_arcade.setChecked(True)
        self.btn_arcade.clicked.connect(lambda: self._set_mode("arcade"))
        self.btn_gamepad.clicked.connect(lambda: self._set_mode("gamepad"))

        self.btn_6btn = bm_btn("6 BTN", _GREEN)
        self.btn_8btn = bm_btn("8 BTN", _CYAN)
        self.btn_8btn.setChecked(True)
        self.btn_6btn.clicked.connect(lambda: self._set_btn_mode(6))
        self.btn_8btn.clicked.connect(lambda: self._set_btn_mode(8))

        lbl_b = QLabel("Botonera:")
        lbl_b.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{_TXT_LO};background:transparent;")

        sep  = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1); sep.setStyleSheet(f"background:{_BORDER};")
        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedWidth(1); sep2.setStyleSheet(f"background:{_BORDER};")

        lay.addWidget(dot); lay.addWidget(title); lay.addStretch()
        lay.addWidget(lbl_sys); lay.addWidget(self.cmb_system)
        lay.addWidget(sep)
        lay.addWidget(self.btn_arcade); lay.addWidget(self.btn_gamepad)
        lay.addWidget(sep2)
        lay.addWidget(lbl_b)
        lay.addWidget(self.btn_6btn); lay.addWidget(self.btn_8btn)
        return bar

    def _build_editor(self) -> QWidget:
        w = QWidget(); w.setStyleSheet(f"background:{_BASE};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(6)

        self.lbl_active = QLabel("Perfil: Default  |  Arcade  |  8 BTN")
        self.lbl_active.setStyleSheet(
            f"font-size:12px;font-weight:700;font-family:{_MONO};"
            f"color:{_AMBER};background:transparent;")

        self.arcade_layout  = ArcadeLayout(btn_mode=8)
        self.gamepad_layout = GamepadLayout()
        self.gamepad_layout.hide()

        self.arcade_layout.slot_changed.connect(self._on_assignment_changed)
        self.gamepad_layout.slot_changed.connect(self._on_assignment_changed)

        lay.addWidget(self.lbl_active)
        lay.addWidget(self.arcade_layout, 1)
        lay.addWidget(self.gamepad_layout, 1)
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget(); w.setFixedWidth(275)
        w.setStyleSheet(f"background:{_CARD};border-left:1px solid {_BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 14, 12, 14); lay.setSpacing(10)

        def sh(t):
            l = QLabel(t); l.setFixedHeight(18)
            l.setStyleSheet(
                f"font-size:10px;font-weight:800;letter-spacing:1.5px;"
                f"color:{_TXT_LO};font-family:{_MONO};background:transparent;")
            return l

        def sep():
            f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
            f.setFixedHeight(1); f.setStyleSheet(f"background:{_BORDER};border:none;")
            return f

        lay.addWidget(sh("PERFILES"))
        pr = QHBoxLayout()
        self.cmb_profile = QComboBox()
        self.cmb_profile.addItem("Default")
        self.cmb_profile.currentTextChanged.connect(self._on_profile_changed)
        b_new = QPushButton("+"); b_new.setFixedSize(32, 32)
        b_new.clicked.connect(self._new_profile)
        b_del = QPushButton("-"); b_del.setFixedSize(32, 32)
        b_del.setObjectName("btn_danger"); b_del.clicked.connect(self._delete_profile)
        pr.addWidget(self.cmb_profile, 1); pr.addWidget(b_new); pr.addWidget(b_del)
        lay.addLayout(pr)

        for lbl, fn, obj in [
            ("Guardar perfil",    self._save_profile,      "btn_success"),
            ("Cargar .cfg",       self._load_profile_file, ""),
            ("Exportar JoyToKey", self._export_joytokey,   "btn_primary"),
            ("Limpiar todo",      self._clear_layout,      "btn_danger"),
        ]:
            b = QPushButton(lbl); b.setFixedHeight(32)
            if obj: b.setObjectName(obj)
            b.clicked.connect(fn); lay.addWidget(b)

        lay.addWidget(sep())
        lay.addWidget(sh("TEKNOPARROT"))
        tp_r = QHBoxLayout()
        self.inp_tp = QLineEdit()
        self.inp_tp.setPlaceholderText("UserProfile .xml"); self.inp_tp.setFixedHeight(30)
        b_tp = QPushButton("..."); b_tp.setFixedSize(30, 30); b_tp.clicked.connect(self._browse_tp)
        tp_r.addWidget(self.inp_tp, 1); tp_r.addWidget(b_tp); lay.addLayout(tp_r)
        b_tp_a = QPushButton("Aplicar en modulo RL")
        b_tp_a.setObjectName("btn_primary"); b_tp_a.setFixedHeight(30)
        b_tp_a.clicked.connect(self._apply_tp); lay.addWidget(b_tp_a)

        lay.addWidget(sep())
        lay.addWidget(sh("PCLAUNCHER"))
        pc_r = QHBoxLayout()
        self.inp_pc = QLineEdit()
        self.inp_pc.setPlaceholderText("Ruta .exe del juego"); self.inp_pc.setFixedHeight(30)
        b_pc = QPushButton("..."); b_pc.setFixedSize(30, 30); b_pc.clicked.connect(self._browse_pc)
        pc_r.addWidget(self.inp_pc, 1); pc_r.addWidget(b_pc); lay.addLayout(pc_r)
        b_pc_a = QPushButton("Aplicar en Games.ini")
        b_pc_a.setObjectName("btn_primary"); b_pc_a.setFixedHeight(30)
        b_pc_a.clicked.connect(self._apply_pc); lay.addWidget(b_pc_a)

        lay.addWidget(sep())
        lay.addWidget(sh("ASIGNACIONES"))
        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True); self.txt_summary.setMinimumHeight(80)
        self.txt_summary.setStyleSheet(
            f"QTextEdit{{background:{_DEEP};border:1px solid {_BORDER};"
            f"color:{_TXT_LO};font-family:{_MONO};font-size:11px;"
            f"border-radius:6px;padding:6px;}}")
        lay.addWidget(self.txt_summary, 1)
        return w

    # ── logica ───────────────────────────────────────────────────────────────
    def _reload_systems(self):
        scan = self._config.get("scan_results", {})
        self._systems = scan.get("systems", [])
        self.cmb_system.clear()
        self.cmb_system.addItem("(todos los sistemas)")
        for s in self._systems:
            self.cmb_system.addItem(s)

    def _on_system_changed(self, name):
        self._current_system = "" if name == "(todos los sistemas)" else name
        self._load_profiles_for_system()

    def _get_profile_dir(self):
        rl = self._config.get("rocketlauncher_dir", "")
        if not rl: return ""
        return os.path.join(rl, "Profiles", self._current_system or "_Global")

    def _load_profiles_for_system(self):
        self._profiles = {"Default": {}}
        self.cmb_profile.clear(); self.cmb_profile.addItem("Default")
        pd = self._get_profile_dir()
        if pd and os.path.isdir(pd):
            for f in sorted(os.listdir(pd)):
                if f.endswith(".cfg"):
                    name = f[:-4]
                    try:
                        with open(os.path.join(pd, f), encoding="utf-8") as fp:
                            self._profiles[name] = json.load(fp)
                        if name != "Default": self.cmb_profile.addItem(name)
                    except Exception: pass
        self._apply_profile("Default")

    def _set_mode(self, mode):
        self._current_mode = mode
        is_a = mode == "arcade"
        self.arcade_layout.setVisible(is_a)
        self.gamepad_layout.setVisible(not is_a)
        self.btn_arcade.setChecked(is_a)
        self.btn_gamepad.setChecked(not is_a)
        self.btn_6btn.setEnabled(is_a); self.btn_8btn.setEnabled(is_a)
        new_pal = ActionPalette(ARCADE_ACTIONS if is_a else GAMEPAD_ACTIONS)
        sp = self._splitter
        idx = sp.indexOf(self._palette)
        self._palette.setParent(None); self._palette.deleteLater()
        self._palette = new_pal
        sp.insertWidget(idx, self._palette)
        sp.setSizes([195, 0, 275])
        sp.setStretchFactor(0, 0); sp.setStretchFactor(1, 1); sp.setStretchFactor(2, 0)
        self._update_label()

    def _set_btn_mode(self, mode):
        if mode == self._current_btn_mode: return
        self._current_btn_mode = mode
        self.btn_6btn.setChecked(mode == 6); self.btn_8btn.setChecked(mode == 8)
        self.arcade_layout.set_btn_mode(mode); self._update_label()

    def _on_assignment_changed(self, sid, action): self._update_summary()

    def _update_label(self):
        sys_l  = self._current_system or "Todos"
        mode_l = "Arcade" if self._current_mode == "arcade" else "Gamepad"
        btn_l  = f"  |  {self._current_btn_mode} BTN" if self._current_mode == "arcade" else ""
        self.lbl_active.setText(
            f"Sistema: {sys_l}  |  Perfil: {self._current_profile}  |  {mode_l}{btn_l}")

    def _update_summary(self):
        lay = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        lines = [f"{sid:<22} -> {act}"
                 for sid, act in sorted(lay.get_assignments().items()) if act]
        self.txt_summary.setText("\n".join(lines) if lines else "(sin asignaciones)")

    def _on_profile_changed(self, name):
        if name:
            self._current_profile = name
            self._apply_profile(name); self._update_label()

    def _apply_profile(self, name):
        data = self._profiles.get(name, {})
        mode = data.get("_mode", "arcade")
        self._set_mode(mode)
        asgn = {k: v for k, v in data.items() if not k.startswith("_")}
        lay = self.arcade_layout if mode == "arcade" else self.gamepad_layout
        lay.set_assignments(asgn); self._update_summary()

    def _save_profile(self):
        name = self.cmb_profile.currentText()
        lay  = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        data = lay.get_assignments()
        data["_mode"] = self._current_mode; data["_system"] = self._current_system
        self._profiles[name] = data
        pd = self._get_profile_dir()
        if pd:
            os.makedirs(pd, exist_ok=True)
            path = os.path.join(pd, f"{name}.cfg")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self._save_joytokey()
                if self.parent:
                    self.parent.statusBar().showMessage(f"Perfil '{name}' guardado.", 4000)
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", str(e))

    def _save_joytokey(self):
        sn = (self._current_system or "").strip()
        rl = (self._config.get("rocketlauncher_dir", "") or "").strip()
        if not sn or not rl: return
        joy_dir = os.path.join(rl, "Profiles", "JoyToKey", sn)
        cfg_p   = os.path.join(joy_dir, f"{sn}.cfg")
        content = make_joytokey_cfg(sn)
        os.makedirs(joy_dir, exist_ok=True)
        if os.path.isfile(cfg_p):
            try:
                with open(cfg_p, encoding="utf-8", errors="ignore") as f:
                    if f.read() == content: return
                ok = QMessageBox.question(
                    self.parent, "JoyToKey existente",
                    f"Ya existe:\n{cfg_p}\n\nSobrescribir?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel)
                if ok != QMessageBox.StandardButton.Yes: return
            except Exception: return
        with open(cfg_p, "w", encoding="utf-8") as f: f.write(content)

    def _new_profile(self):
        name, ok = QInputDialog.getText(self.parent, "Nuevo perfil", "Nombre:")
        if ok and name.strip():
            name = name.strip(); self._profiles[name] = {}
            if self.cmb_profile.findText(name) < 0: self.cmb_profile.addItem(name)
            self.cmb_profile.setCurrentText(name)

    def _delete_profile(self):
        name = self.cmb_profile.currentText()
        if name == "Default":
            QMessageBox.warning(self.parent, "No permitido", "No se puede eliminar 'Default'.")
            return
        r = QMessageBox.question(
            self.parent, "Eliminar", f"Eliminar '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Yes:
            self.cmb_profile.removeItem(self.cmb_profile.currentIndex())
            self._profiles.pop(name, None)
            pd = self._get_profile_dir()
            if pd:
                p = os.path.join(pd, f"{name}.cfg")
                if os.path.isfile(p): os.remove(p)

    def _load_profile_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Cargar perfil", "", "Perfil (*.cfg);;JSON (*.json)")
        if not path: return
        try:
            with open(path, encoding="utf-8") as f: data = json.load(f)
            name = Path(path).stem; self._profiles[name] = data
            if self.cmb_profile.findText(name) < 0: self.cmb_profile.addItem(name)
            self.cmb_profile.setCurrentText(name); self._apply_profile(name)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))

    def _export_joytokey(self):
        lay = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
        asgn = lay.get_assignments()
        if not asgn:
            QMessageBox.information(self.parent, "Sin asignaciones", "No hay asignaciones."); return
        path, _ = QFileDialog.getSaveFileName(
            self.parent, "Exportar JoyToKey",
            f"{self._current_profile}_{self._current_mode}.cfg", "JoyToKey (*.cfg)")
        if not path: return
        lines = [f"; HyperSpin Manager - JoyToKey", "", "[config]", "FileVersion=2", ""]
        for i, (sid, act) in enumerate(sorted(asgn.items()), 1):
            if act and act != "---":
                lines += [f"[Button_{i}]", f"Slot={sid}", f"Action={act}", ""]
        try:
            with open(path, "w", encoding="utf-8") as f: f.write("\n".join(lines))
            if self.parent: self.parent.statusBar().showMessage(f"Exportado: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self.parent, "Error", str(e))

    def _clear_layout(self):
        r = QMessageBox.question(
            self.parent, "Limpiar", "Eliminar todas las asignaciones?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Yes:
            lay = self.arcade_layout if self._current_mode == "arcade" else self.gamepad_layout
            lay.clear_all(); self._update_summary()

    def _browse_tp(self):
        p, _ = QFileDialog.getOpenFileName(
            self.parent, "UserProfile TeknoParrot",
            self._config.get("rocketlauncher_dir", ""), "XML (*.xml);;Todos (*.*)")
        if p: self.inp_tp.setText(p)

    def _apply_tp(self):
        tp = self.inp_tp.text().strip()
        rl = self._config.get("rocketlauncher_dir", "")
        sn = self._current_system
        if not sn or not tp:
            QMessageBox.warning(self.parent, "Datos incompletos", "Selecciona sistema y perfil TP."); return
        emu_ini = os.path.join(rl, "Settings", sn, "Emulators.ini")
        if not os.path.isfile(emu_ini):
            QMessageBox.warning(self.parent, "Sin Emulators.ini", f"No encontrado:\n{emu_ini}"); return
        cfg = configparser.RawConfigParser()
        cfg.read(emu_ini, encoding="utf-8")
        any((cfg.set(s, "UserProfile", tp) or True) for s in cfg.sections() if "tekno" in s.lower())
        with open(emu_ini, "w", encoding="utf-8") as f: cfg.write(f)
        if self.parent: self.parent.statusBar().showMessage("UserProfile TeknoParrot actualizado.", 5000)

    def _browse_pc(self):
        p, _ = QFileDialog.getOpenFileName(
            self.parent, "Ejecutable", "", "Ejecutables (*.exe);;Todos (*.*)")
        if p: self.inp_pc.setText(p)

    def _apply_pc(self):
        exe = self.inp_pc.text().strip()
        rl  = self._config.get("rocketlauncher_dir", "")
        sn  = self._current_system
        if not sn or not exe:
            QMessageBox.warning(self.parent, "Datos incompletos", "Selecciona sistema y ejecutable."); return
        games_ini = os.path.join(rl, "Settings", sn, "Games.ini")
        os.makedirs(os.path.dirname(games_ini), exist_ok=True)
        cfg = configparser.RawConfigParser()
        if os.path.isfile(games_ini): cfg.read(games_ini, encoding="utf-8")
        if not cfg.has_section(sn): cfg.add_section(sn)
        cfg.set(sn, "Exe_Path", exe)
        with open(games_ini, "w", encoding="utf-8") as f: cfg.write(f)
        if self.parent:
            self.parent.statusBar().showMessage(f"Exe_Path actualizado en {games_ini}", 5000)