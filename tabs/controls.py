"""
controller_tester.py
Probador de mandos — PyQt6
- Mando Xbox dibujado en QPainter (fiel al original blanco sobre negro)
- Stick analógico dibujado en QPainter
- Detección de mandos conectados (SDL2 / XInput / DirectInput vía pygame)
- Captura de botones: teclado, mando SDL/XInput, DirectInput
- Selector desplegable: Mando 1, Mando 2, etc.
"""

import sys
import math
import threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, pyqtSignal, QObject
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QPainterPath,
    QRadialGradient, QLinearGradient, QFont, QKeyEvent
)

try:
    from main import TabModule
except ImportError:
    class TabModule:
        tab_title = "Módulo"
        tab_icon = ""
        def __init__(self, parent): self.parent = parent
        def widget(self): raise NotImplementedError
        def load_data(self, config): pass
        def save_data(self): return {}

# ─── Intentar importar pygame para SDL/XInput/DirectInput ───────────────────
try:
    import pygame
    import pygame.joystick
    pygame.init()
    pygame.joystick.init()
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

# ─── Paleta ──────────────────────────────────────────────────────────────────
_BG       = "#0a0c10"
_CARD     = "#0d1018"
_BORDER   = "#1a2035"
_MID      = "#1e2840"
_AMBER    = "#f5a623"
_CYAN     = "#00c9e8"
_GREEN    = "#00e599"
_RED      = "#e8192c"
_TXT_HI   = "#ffffff"
_TXT_MD   = "#dde6f8"
_TXT_LO   = "#b0c4e8"
_TXT_GH   = "#8099cc"

# Colores botones Xbox (imagen original: blanco con botones de colores)
_COL_A = "#1db954"   # verde
_COL_B = "#e8192c"   # rojo
_COL_X = "#2a6bbf"   # azul
_COL_Y = "#f5c518"   # amarillo


# ══════════════════════════════════════════════════════════════════════════════
#  XboxControllerWidget  — dibuja el mando Xbox fiel a la imagen de referencia
# ══════════════════════════════════════════════════════════════════════════════

class XboxControllerWidget(QWidget):
    """
    Mando Xbox One dibujado en QPainter.
    Cuerpo blanco sobre fondo negro, botones de colores,
    sticks grises, D-pad gris, bumpers, gatillos, logo Xbox central.
    Los botones/zonas se iluminan cuando están activos.
    """

    # IDs de zona → (cx_rel, cy_rel, shape, label, color_normal, color_active, radio_rel)
    _ZONES = {
        # botones cara
        "btn_y":      (0.775, 0.40, "circle", "Y",   "#f5c518", "#ffe566", 0.044),
        "btn_b":      (0.840, 0.515,"circle", "B",   "#e8192c", "#ff6060", 0.044),
        "btn_x":      (0.710, 0.515,"circle", "X",   "#2a6bbf", "#5599ff", 0.044),
        "btn_a":      (0.775, 0.63, "circle", "A",   "#1db954", "#44ff88", 0.044),
        # bumpers
        "lb":         (0.205, 0.195,"pill",   "LB",  "#b0b0b0", _AMBER,   0.070),
        "rb":         (0.795, 0.195,"pill",   "RB",  "#b0b0b0", _AMBER,   0.070),
        # gatillos
        "lt":         (0.185, 0.095,"pill",   "LT",  "#c0c0c0", _AMBER,   0.078),
        "rt":         (0.815, 0.095,"pill",   "RT",  "#c0c0c0", _AMBER,   0.078),
        # select/start
        "select":     (0.415, 0.415,"rect",   "⧉",   "#909090", _CYAN,    0.040),
        "start":      (0.585, 0.415,"rect",   "≡",   "#909090", _CYAN,    0.040),
        # home
        "home":       (0.500, 0.295,"circle", "X",   "#107020", "#33ff66", 0.058),
        # D-pad (cada brazo)
        "dpad_up":    (0.275, 0.565,"dpad",   "▲",   "#909090", _AMBER,   0.038),
        "dpad_down":  (0.275, 0.695,"dpad",   "▼",   "#909090", _AMBER,   0.038),
        "dpad_left":  (0.215, 0.630,"dpad",   "◀",   "#909090", _AMBER,   0.038),
        "dpad_right": (0.335, 0.630,"dpad",   "▶",   "#909090", _AMBER,   0.038),
        # sticks (press L3/R3)
        "ls":         (0.345, 0.510,"circle", "L3",  "#606060", _CYAN,    0.085),
        "rs":         (0.640, 0.660,"circle", "R3",  "#606060", _CYAN,    0.085),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(520, 370)
        # estado activo de cada zona
        self._active: dict[str, bool] = {k: False for k in self._ZONES}
        # posición de los sticks (−1..+1)
        self._ls = QPointF(0.0, 0.0)
        self._rs = QPointF(0.0, 0.0)

    def set_button(self, name: str, pressed: bool):
        if name in self._active:
            self._active[name] = pressed
            self.update()

    def set_axis(self, stick: str, x: float, y: float):
        if stick == "left":
            self._ls = QPointF(max(-1, min(1, x)), max(-1, min(1, y)))
        else:
            self._rs = QPointF(max(-1, min(1, x)), max(-1, min(1, y)))
        self.update()

    # ── pintado ────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        self._draw(p, W, H)

    def _draw(self, p: QPainter, W: int, H: int):
        # márgenes
        mx, my = int(W * 0.03), int(H * 0.04)
        ew, eh = W - mx * 2, H - my * 2

        def cx(r): return int(mx + r * ew)
        def cy(r): return int(my + r * eh)
        def sz(r): return int(min(ew, eh) * r)

        bx, by = cx(0.05), cy(0.10)
        bw = cx(0.95) - bx
        bh = cy(0.92) - by

        # ── sombra del cuerpo ──────────────────────────────────────────────
        body = self._body_path(bx, by, bw, bh)
        p.save(); p.translate(5, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(0, 0, 0, 120)))
        p.drawPath(body); p.restore()

        # ── cuerpo blanco ─────────────────────────────────────────────────
        body = self._body_path(bx, by, bw, bh)
        grad = QLinearGradient(bx + bw / 2, by, bx + bw / 2, by + bh)
        grad.setColorAt(0.0, QColor("#f8f8f8"))
        grad.setColorAt(0.45, QColor("#e8e8e8"))
        grad.setColorAt(1.0, QColor("#d0d0d0"))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#c0c0c0"), 1.5))
        p.drawPath(body)

        # ── brillo superior ────────────────────────────────────────────────
        hi = QPainterPath()
        hi.moveTo(bx + bw * 0.30, by + 3)
        hi.quadTo(bx + bw * 0.50, by - 4, bx + bw * 0.70, by + 3)
        hi.quadTo(bx + bw * 0.50, by + bh * 0.12, bx + bw * 0.30, by + 3)
        hi_g = QLinearGradient(0, by, 0, by + bh * 0.12)
        hi_g.setColorAt(0, QColor(255, 255, 255, 80))
        hi_g.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hi_g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(hi)

        # ── surco central superior ─────────────────────────────────────────
        groove = QPainterPath()
        groove.moveTo(bx + bw * 0.32, by + bh * 0.08)
        groove.quadTo(bx + bw * 0.50, by + bh * 0.28, bx + bw * 0.68, by + bh * 0.08)
        p.setPen(QPen(QColor("#b8b8b8"), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(groove)

        # ── bumpers ────────────────────────────────────────────────────────
        self._draw_bumper(p, cx, cy, sz, "lb", side="left")
        self._draw_bumper(p, cx, cy, sz, "rb", side="right")

        # ── gatillos ──────────────────────────────────────────────────────
        self._draw_trigger(p, cx, cy, sz, "lt", side="left")
        self._draw_trigger(p, cx, cy, sz, "rt", side="right")

        # ── zona central (panel gris oscuro) ───────────────────────────────
        panel_w = int(bw * 0.36)
        panel_h = int(bh * 0.22)
        panel_x = cx(0.5) - panel_w // 2
        panel_y = cy(0.34) - panel_h // 2
        pp = QPainterPath()
        pp.addRoundedRect(QRectF(panel_x, panel_y, panel_w, panel_h), 10, 10)
        p.setBrush(QBrush(QColor("#d8d8d8")))
        p.setPen(QPen(QColor("#b0b0b0"), 1))
        p.drawPath(pp)

        # ── logo Xbox (círculo + X) ────────────────────────────────────────
        lx, ly = cx(0.50), cy(0.24)
        lr = sz(0.055)
        home_active = self._active.get("home", False)
        lg = QRadialGradient(lx, ly, lr * 1.4)
        if home_active:
            lg.setColorAt(0, QColor("#66ff88")); lg.setColorAt(1, QColor("#007020"))
        else:
            lg.setColorAt(0, QColor("#c8c8c8")); lg.setColorAt(1, QColor("#909090"))
        p.setBrush(QBrush(lg))
        p.setPen(QPen(QColor("#808080"), 1.2))
        p.drawEllipse(int(lx - lr), int(ly - lr), int(lr * 2), int(lr * 2))
        # X del logo
        p.setPen(QPen(QColor("#505050" if not home_active else "#00aa33"), int(lr * 0.25) + 1))
        d = int(lr * 0.55)
        p.drawLine(int(lx - d), int(ly - d), int(lx + d), int(ly + d))
        p.drawLine(int(lx + d), int(ly - d), int(lx - d), int(ly + d))

        # ── botones SELECT / START ─────────────────────────────────────────
        for sid, rx, ry in [("select", 0.415, 0.415), ("start", 0.585, 0.415)]:
            active = self._active.get(sid, False)
            scx, scy = cx(rx), cy(ry)
            sw, sh = sz(0.065), sz(0.038)
            col = QColor(_CYAN if active else "#909090")
            p.setBrush(QBrush(col))
            p.setPen(QPen(col.darker(130), 1))
            p.drawRoundedRect(int(scx - sw // 2), int(scy - sh // 2), sw, sh, 5, 5)
            p.setFont(QFont("Segoe UI", max(5, sz(0.022)), QFont.Weight.Bold))
            p.setPen(QPen(QColor("#202020" if active else "#404040")))
            lbl = "⧉" if sid == "select" else "≡"
            p.drawText(QRectF(scx - sw / 2, scy - sh / 2, sw, sh),
                       Qt.AlignmentFlag.AlignCenter, lbl)

        # ── stick izquierdo ────────────────────────────────────────────────
        self._draw_stick(p, cx(0.345), cy(0.510), sz(0.080), self._ls,
                         self._active.get("ls", False))

        # ── stick derecho ──────────────────────────────────────────────────
        self._draw_stick(p, cx(0.640), cy(0.660), sz(0.080), self._rs,
                         self._active.get("rs", False))

        # ── D-pad ─────────────────────────────────────────────────────────
        self._draw_dpad(p, cx(0.275), cy(0.630), sz(0.052))

        # ── botones cara (A B X Y) ────────────────────────────────────────
        for sid, rx, ry, col_n, col_a, lbl in [
            ("btn_y", 0.775, 0.40,  _COL_Y, "#ffe080", "Y"),
            ("btn_b", 0.840, 0.515, _COL_B, "#ff8080", "B"),
            ("btn_x", 0.710, 0.515, _COL_X, "#80b0ff", "X"),
            ("btn_a", 0.775, 0.63,  _COL_A, "#80ff80", "A"),
        ]:
            active = self._active.get(sid, False)
            fcx, fcy = cx(rx), cy(ry)
            fr = sz(0.040)
            c = QColor(col_a if active else col_n)
            fg = QRadialGradient(fcx - fr * 0.3, fcy - fr * 0.4, fr * 1.5)
            fg.setColorAt(0, c.lighter(140 if active else 130))
            fg.setColorAt(0.5, c)
            fg.setColorAt(1, c.darker(140))
            p.setBrush(QBrush(fg))
            p.setPen(QPen(c.darker(130), 1.5))
            p.drawEllipse(int(fcx - fr), int(fcy - fr), int(fr * 2), int(fr * 2))
            # brillo
            if active:
                hg = QRadialGradient(fcx - fr * 0.2, fcy - fr * 0.3, fr * 0.8)
                hg.setColorAt(0, QColor(255, 255, 255, 120))
                hg.setColorAt(1, QColor(255, 255, 255, 0))
                p.setBrush(QBrush(hg)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(int(fcx - fr), int(fcy - fr), int(fr * 2), int(fr * 2))
            p.setFont(QFont("Segoe UI", max(7, int(fr * 0.85)), QFont.Weight.Bold))
            p.setPen(QPen(QColor(255, 255, 255, 240)))
            p.drawText(QRectF(fcx - fr, fcy - fr, fr * 2, fr * 2),
                       Qt.AlignmentFlag.AlignCenter, lbl)

    def _body_path(self, bx, by, bw, bh) -> QPainterPath:
        body = QPainterPath()
        body.moveTo(bx + bw * 0.24, by)
        body.lineTo(bx + bw * 0.76, by)
        body.quadTo(bx + bw * 1.00, by + 0,         bx + bw, by + bh * 0.34)
        body.lineTo(bx + bw,        by + bh * 0.52)
        body.quadTo(bx + bw * 0.96, by + bh * 0.82, bx + bw * 0.80, by + bh)
        body.lineTo(bx + bw * 0.60, by + bh)
        body.quadTo(bx + bw * 0.51, by + bh * 0.78, bx + bw * 0.50, by + bh * 0.75)
        body.quadTo(bx + bw * 0.49, by + bh * 0.78, bx + bw * 0.40, by + bh)
        body.lineTo(bx + bw * 0.20, by + bh)
        body.quadTo(bx + bw * 0.04, by + bh * 0.82, bx,              by + bh * 0.52)
        body.lineTo(bx,             by + bh * 0.34)
        body.quadTo(bx,             by + 0,          bx + bw * 0.24, by)
        body.closeSubpath()
        return body

    def _draw_bumper(self, p, cx, cy, sz, sid, side):
        active = self._active.get(sid, False)
        if side == "left":
            bcx, bcy = cx(0.205), cy(0.200)
            bw2, bh2 = sz(0.130), sz(0.048)
            path = QPainterPath()
            path.moveTo(bcx + bw2 * 0.5, bcy + bh2)
            path.quadTo(bcx - bw2 * 0.1, bcy + bh2, bcx - bw2 * 0.35, bcy + bh2 * 0.4)
            path.quadTo(bcx - bw2 * 0.5, bcy - bh2 * 0.2, bcx + bw2 * 0.0, bcy - bh2 * 0.5)
            path.quadTo(bcx + bw2 * 0.3, bcy - bh2 * 0.8, bcx + bw2 * 0.5, bcy)
            path.closeSubpath()
        else:
            bcx, bcy = cx(0.795), cy(0.200)
            bw2, bh2 = sz(0.130), sz(0.048)
            path = QPainterPath()
            path.moveTo(bcx - bw2 * 0.5, bcy + bh2)
            path.quadTo(bcx + bw2 * 0.1, bcy + bh2, bcx + bw2 * 0.35, bcy + bh2 * 0.4)
            path.quadTo(bcx + bw2 * 0.5, bcy - bh2 * 0.2, bcx - bw2 * 0.0, bcy - bh2 * 0.5)
            path.quadTo(bcx - bw2 * 0.3, bcy - bh2 * 0.8, bcx - bw2 * 0.5, bcy)
            path.closeSubpath()
        col = QColor(_AMBER if active else "#b8b8b8")
        p.setBrush(QBrush(col))
        p.setPen(QPen(col.darker(130), 1.2))
        p.drawPath(path)
        lbl = "LB" if side == "left" else "RB"
        p.setFont(QFont("Segoe UI", max(6, int(bh2 * 0.55)), QFont.Weight.Bold))
        p.setPen(QPen(QColor("#303030" if not active else "#202020")))
        if side == "left":
            p.drawText(QRectF(bcx - bw2 * 0.2, bcy - bh2 * 0.1, bw2 * 0.7, bh2 * 0.9),
                       Qt.AlignmentFlag.AlignCenter, lbl)
        else:
            p.drawText(QRectF(bcx - bw2 * 0.5, bcy - bh2 * 0.1, bw2 * 0.7, bh2 * 0.9),
                       Qt.AlignmentFlag.AlignCenter, lbl)

    def _draw_trigger(self, p, cx, cy, sz, sid, side):
        active = self._active.get(sid, False)
        if side == "left":
            tcx, tcy = cx(0.185), cy(0.095)
            tw, th = sz(0.120), sz(0.060)
        else:
            tcx, tcy = cx(0.815), cy(0.095)
            tw, th = sz(0.120), sz(0.060)
        col = QColor(_AMBER if active else "#c8c8c8")
        path = QPainterPath()
        if side == "left":
            path.moveTo(tcx - tw * 0.4, tcy + th)
            path.quadTo(tcx - tw * 0.5, tcy + th * 0.5, tcx - tw * 0.3, tcy)
            path.quadTo(tcx, tcy - th * 0.5, tcx + tw * 0.4, tcy)
            path.lineTo(tcx + tw * 0.4, tcy + th)
            path.closeSubpath()
        else:
            path.moveTo(tcx + tw * 0.4, tcy + th)
            path.quadTo(tcx + tw * 0.5, tcy + th * 0.5, tcx + tw * 0.3, tcy)
            path.quadTo(tcx, tcy - th * 0.5, tcx - tw * 0.4, tcy)
            path.lineTo(tcx - tw * 0.4, tcy + th)
            path.closeSubpath()
        p.setBrush(QBrush(col))
        p.setPen(QPen(col.darker(130), 1.2))
        p.drawPath(path)
        lbl = "LT" if side == "left" else "RT"
        p.setFont(QFont("Segoe UI", max(6, int(th * 0.55)), QFont.Weight.Bold))
        p.setPen(QPen(QColor("#303030" if not active else "#202020")))
        p.drawText(QRectF(tcx - tw * 0.3, tcy + th * 0.05, tw * 0.6, th * 0.8),
                   Qt.AlignmentFlag.AlignCenter, lbl)

    def _draw_stick(self, p, scx, scy, sr, pos: QPointF, pressed: bool):
        # Anillo exterior (base)
        bg = QRadialGradient(scx - sr * 0.2, scy - sr * 0.2, sr * 1.5)
        bg.setColorAt(0, QColor("#c0c0c0"))
        bg.setColorAt(0.5, QColor("#989898"))
        bg.setColorAt(1, QColor("#707070"))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor("#606060"), 1.5))
        p.drawEllipse(int(scx - sr), int(scy - sr), int(sr * 2), int(sr * 2))
        # Cap del stick (se desplaza con pos)
        cap_r = sr * 0.62
        off_x = pos.x() * (sr - cap_r) * 0.7
        off_y = pos.y() * (sr - cap_r) * 0.7
        cx2, cy2 = scx + off_x, scy + off_y
        col = QColor(_CYAN if pressed else "#d0d0d0")
        cg = QRadialGradient(cx2 - cap_r * 0.3, cy2 - cap_r * 0.3, cap_r * 1.4)
        cg.setColorAt(0, col.lighter(120))
        cg.setColorAt(0.5, col)
        cg.setColorAt(1, col.darker(140))
        p.setBrush(QBrush(cg))
        p.setPen(QPen(QColor("#404040"), 1.2))
        p.drawEllipse(int(cx2 - cap_r), int(cy2 - cap_r), int(cap_r * 2), int(cap_r * 2))
        # Cruz central del stick
        p.setPen(QPen(QColor("#909090"), 1))
        p.drawLine(int(cx2 - cap_r * 0.4), int(cy2), int(cx2 + cap_r * 0.4), int(cy2))
        p.drawLine(int(cx2), int(cy2 - cap_r * 0.4), int(cx2), int(cy2 + cap_r * 0.4))

    def _draw_dpad(self, p, dcx, dcy, arm):
        wid = int(arm * 0.58)
        p.setBrush(QBrush(QColor("#c0c0c0")))
        p.setPen(QPen(QColor("#909090"), 1))
        # centro
        p.drawRoundedRect(int(dcx - wid // 2), int(dcy - wid // 2), wid, wid, 3, 3)
        dirs = {
            "dpad_up":    (0, -1), "dpad_down":  (0,  1),
            "dpad_left":  (-1, 0), "dpad_right": ( 1, 0),
        }
        for sid, (dx, dy) in dirs.items():
            active = self._active.get(sid, False)
            col = QColor(_AMBER if active else "#c0c0c0")
            p.setBrush(QBrush(col))
            p.setPen(QPen(col.darker(130), 1))
            rx = int(dcx + dx * arm - wid // 2)
            ry = int(dcy + dy * arm - wid // 2)
            rw = wid if dy == 0 else wid
            rh = arm if dy != 0 else wid
            p.drawRoundedRect(rx, ry, rw, rh, 3, 3)


# ══════════════════════════════════════════════════════════════════════════════
#  StickWidget — visualizador del stick analógico
# ══════════════════════════════════════════════════════════════════════════════

class StickWidget(QWidget):
    """Muestra la posición del stick como punto en un círculo."""

    def __init__(self, label="L", parent=None):
        super().__init__(parent)
        self.label = label
        self._x = 0.0
        self._y = 0.0
        self.setFixedSize(130, 130)
        self.setStyleSheet("background: transparent;")

    def set_pos(self, x: float, y: float):
        self._x = max(-1.0, min(1.0, x))
        self._y = max(-1.0, min(1.0, y))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W // 2, H // 2
        r = min(W, H) // 2 - 12

        # fondo
        bg = QRadialGradient(cx, cy, r)
        bg.setColorAt(0, QColor("#1a1e2a"))
        bg.setColorAt(1, QColor("#0d1018"))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor(_BORDER), 1.5))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # cuadrícula
        p.setPen(QPen(QColor(_MID), 1))
        p.drawLine(cx - r, cy, cx + r, cy)
        p.drawLine(cx, cy - r, cx, cy + r)
        p.drawEllipse(cx - r // 2, cy - r // 2, r, r)

        # punto del stick
        dot_r = 10
        dot_x = cx + int(self._x * (r - dot_r))
        dot_y = cy + int(self._y * (r - dot_r))
        dg = QRadialGradient(dot_x - dot_r // 3, dot_y - dot_r // 3, dot_r * 1.5)
        dg.setColorAt(0, QColor(_CYAN).lighter(130))
        dg.setColorAt(1, QColor(_CYAN).darker(150))
        p.setBrush(QBrush(dg))
        p.setPen(QPen(QColor(_CYAN).darker(120), 1.5))
        p.drawEllipse(dot_x - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2)

        # etiqueta
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.setPen(QPen(QColor(_TXT_LO)))
        p.drawText(QRectF(0, H - 18, W, 18), Qt.AlignmentFlag.AlignCenter,
                   f"{self.label}  ({self._x:+.2f}, {self._y:+.2f})")
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(QPen(QColor(_TXT_GH)))
        p.drawText(QRectF(cx - r, cy - r - 16, r * 2, 16),
                   Qt.AlignmentFlag.AlignCenter, f"Stick {self.label}")


# ══════════════════════════════════════════════════════════════════════════════
#  InputBridge — hilo que lee eventos pygame y emite señales Qt
# ══════════════════════════════════════════════════════════════════════════════

class InputBridge(QObject):
    button_event = pyqtSignal(int, str, bool)   # joystick_id, btn_name, pressed
    axis_event   = pyqtSignal(int, str, float, float)  # jid, "left"/"right", x, y
    devices_changed = pyqtSignal(list)           # lista de nombres

    def __init__(self, parent=None):
        super().__init__(parent)
        self._joysticks: dict[int, any] = {}
        self._axis_vals: dict[int, list] = {}
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(16)   # ~60 Hz
        self._timer.timeout.connect(self._poll)

    def start(self):
        self._running = True
        self._timer.start()
        self._scan_devices()

    def stop(self):
        self._running = False
        self._timer.stop()

    def _scan_devices(self):
        if not PYGAME_OK:
            self.devices_changed.emit(["Teclado (sin pygame)"])
            return
        pygame.joystick.quit()
        pygame.joystick.init()
        names = ["Teclado"]
        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            self._joysticks[i] = js
            self._axis_vals[i] = [0.0] * max(js.get_numaxes(), 4)
            names.append(f"Mando {i+1} — {js.get_name()}")
        self.devices_changed.emit(names)

    def _poll(self):
        if not PYGAME_OK:
            return
        # re-escanear si cambia el nº de mandos
        count = pygame.joystick.get_count()
        if count != len(self._joysticks):
            self._scan_devices()
            return

        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                name = self._btn_name(event.joy, event.button)
                self.button_event.emit(event.joy, name, True)
            elif event.type == pygame.JOYBUTTONUP:
                name = self._btn_name(event.joy, event.button)
                self.button_event.emit(event.joy, name, False)
            elif event.type == pygame.JOYAXISMOTION:
                jid = event.joy
                ax = event.axis
                val = event.value
                if jid in self._axis_vals:
                    avs = self._axis_vals[jid]
                    if ax < len(avs):
                        avs[ax] = val
                    # ejes 0,1 = stick izq; 2,3 = stick der (layout estándar SDL)
                    lx = avs[0] if len(avs) > 0 else 0.0
                    ly = avs[1] if len(avs) > 1 else 0.0
                    rx = avs[3] if len(avs) > 3 else (avs[2] if len(avs) > 2 else 0.0)
                    ry = avs[4] if len(avs) > 4 else (avs[3] if len(avs) > 3 else 0.0)
                    self.axis_event.emit(jid, "left",  lx, ly)
                    self.axis_event.emit(jid, "right", rx, ry)
            elif event.type == pygame.JOYHATMOTION:
                jid = event.joy
                hx, hy = event.value
                self.button_event.emit(jid, "dpad_left",  hx == -1)
                self.button_event.emit(jid, "dpad_right", hx ==  1)
                self.button_event.emit(jid, "dpad_up",    hy ==  1)
                self.button_event.emit(jid, "dpad_down",  hy == -1)

    # Mapa botones SDL estándar → nombre del mando Xbox
    _BTN_MAP = {
        0: "btn_a", 1: "btn_b", 2: "btn_x",  3: "btn_y",
        4: "lb",    5: "rb",
        6: "select", 7: "start",
        8: "home",
        9: "ls",   10: "rs",
    }

    def _btn_name(self, jid: int, btn: int) -> str:
        return self._BTN_MAP.get(btn, f"btn_{btn}")


# ══════════════════════════════════════════════════════════════════════════════
#  EventLog — panel inferior con log de eventos
# ══════════════════════════════════════════════════════════════════════════════

class EventLog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(90)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)
        hdr = QLabel("EVENTOS DE ENTRADA")
        hdr.setStyleSheet(
            f"font-family:'Consolas','Courier New',monospace;"
            f"font-size:10px;font-weight:800;letter-spacing:2px;"
            f"color:{_TXT_GH};background:transparent;")
        lay.addWidget(hdr)
        self._lines: list[QLabel] = []
        for _ in range(4):
            lbl = QLabel("")
            lbl.setStyleSheet(
                f"font-family:'Consolas','Courier New',monospace;"
                f"font-size:11px;color:{_AMBER};background:transparent;")
            lay.addWidget(lbl)
            self._lines.append(lbl)
        self._history: list[str] = []

    def log(self, msg: str):
        self._history.append(msg)
        if len(self._history) > 4:
            self._history = self._history[-4:]
        for i, lbl in enumerate(self._lines):
            if i < len(self._history):
                lbl.setText(self._history[-(i+1)])
            else:
                lbl.setText("")


# ══════════════════════════════════════════════════════════════════════════════
#  ControllerTesterWidget — widget principal
# ══════════════════════════════════════════════════════════════════════════════

class ControllerTesterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f"QWidget{{background:{_BG};color:{_TXT_HI};}}")
        self._selected_jid = -1   # -1 = teclado
        self._current_category = "arcade"
        self._current_slot = "1"
        self._profiles_by_slot = {
            "arcade": {"1": "Arcade P1", "2": "Arcade P2", "3": "Arcade P3"},
            "consola": {"1": "Consola P1", "2": "Consola P2", "3": "Consola P3"},
        }
        self._device_by_slot = {
            "arcade": {"1": "Teclado", "2": "Teclado", "3": "Teclado"},
            "consola": {"1": "Teclado", "2": "Teclado", "3": "Teclado"},
        }
        self._known_devices = ["Teclado"]
        self._bridge = InputBridge(self)
        self._build_ui()
        self._bridge.button_event.connect(self._on_btn)
        self._bridge.axis_event.connect(self._on_axis)
        self._bridge.devices_changed.connect(self._on_devices)
        self._bridge.start()
        # re-escanear periódicamente
        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(3000)
        self._scan_timer.timeout.connect(self._bridge._scan_devices)
        self._scan_timer.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # ── Barra superior ─────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(10)

        title = QLabel("PROBADOR DE MANDOS")
        title.setStyleSheet(
            f"font-size:15px;font-weight:800;letter-spacing:3px;"
            f"color:{_AMBER};font-family:'Consolas','Courier New',monospace;")
        top.addWidget(title)
        top.addStretch()

        # indicador pygame
        if PYGAME_OK:
            status_col = _GREEN
            status_txt = "● SDL2/pygame activo"
        else:
            status_col = _RED
            status_txt = "⚠ pygame no disponible — solo teclado"
        lbl_status = QLabel(status_txt)
        lbl_status.setStyleSheet(
            f"font-size:11px;color:{status_col};"
            f"font-family:'Consolas','Courier New',monospace;")
        top.addWidget(lbl_status)

        # selector de mando
        lbl_dev = QLabel("Dispositivo:")
        lbl_dev.setStyleSheet(f"font-size:12px;color:{_TXT_LO};")
        top.addWidget(lbl_dev)

        lbl_cat = QLabel("Categoría:")
        lbl_cat.setStyleSheet(f"font-size:12px;color:{_TXT_LO};")
        top.addWidget(lbl_cat)
        self._cmb_category = QComboBox()
        self._cmb_category.addItems(["Arcade", "Consola"])
        self._cmb_category.setStyleSheet(
            f"QComboBox{{background:#0d1018;border:1px solid {_BORDER};"
            f"border-radius:6px;color:{_TXT_HI};font-size:12px;padding:4px 10px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}")
        self._cmb_category.currentIndexChanged.connect(self._on_category_changed)
        top.addWidget(self._cmb_category)

        lbl_slot = QLabel("Mando:")
        lbl_slot.setStyleSheet(f"font-size:12px;color:{_TXT_LO};")
        top.addWidget(lbl_slot)
        self._cmb_slot = QComboBox()
        self._cmb_slot.addItems(["1", "2", "3"])
        self._cmb_slot.setStyleSheet(
            f"QComboBox{{background:#0d1018;border:1px solid {_BORDER};"
            f"border-radius:6px;color:{_TXT_HI};font-size:12px;padding:4px 10px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}")
        self._cmb_slot.currentIndexChanged.connect(self._on_slot_changed)
        top.addWidget(self._cmb_slot)

        lbl_profile = QLabel("Perfil:")
        lbl_profile.setStyleSheet(f"font-size:12px;color:{_TXT_LO};")
        top.addWidget(lbl_profile)
        self._cmb_profile = QComboBox()
        self._cmb_profile.setEditable(True)
        self._cmb_profile.setMinimumWidth(150)
        self._cmb_profile.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._cmb_profile.setStyleSheet(
            f"QComboBox{{background:#0d1018;border:1px solid {_BORDER};"
            f"border-radius:6px;color:{_TXT_HI};font-size:12px;padding:4px 10px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}")
        self._cmb_profile.lineEdit().editingFinished.connect(self._save_profile_name)
        top.addWidget(self._cmb_profile)

        self._cmb = QComboBox()
        self._cmb.setMinimumWidth(260)
        self._cmb.setStyleSheet(
            f"QComboBox{{background:#0d1018;border:1px solid {_BORDER};"
            f"border-radius:6px;color:{_TXT_HI};font-size:12px;padding:4px 10px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:#0d1018;border:1px solid {_BORDER};"
            f"color:{_TXT_HI};selection-background-color:{_MID};}}")
        self._cmb.addItem("Teclado")
        self._cmb.currentIndexChanged.connect(self._on_device_selected)
        top.addWidget(self._cmb)

        btn_refresh = QPushButton("⟳ Actualizar")
        btn_refresh.setFixedHeight(30)
        btn_refresh.setStyleSheet(
            f"QPushButton{{background:{_MID};border:1px solid {_BORDER};"
            f"border-radius:6px;color:{_TXT_HI};font-size:11px;padding:0 12px;}}"
            f"QPushButton:hover{{background:{_BORDER};color:{_AMBER};}}")
        btn_refresh.clicked.connect(self._bridge._scan_devices)
        top.addWidget(btn_refresh)

        root.addLayout(top)

        # ── Separador ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{_BORDER};")
        root.addWidget(sep)

        # ── Área central: mando + sticks ───────────────────────────────────
        center = QHBoxLayout()
        center.setSpacing(12)

        # Stick izquierdo
        self._stick_l = StickWidget("L")
        center.addWidget(self._stick_l, 0, Qt.AlignmentFlag.AlignVCenter)

        # Mando Xbox
        self._controller = XboxControllerWidget()
        center.addWidget(self._controller, 1)

        # Stick derecho
        self._stick_r = StickWidget("R")
        center.addWidget(self._stick_r, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addLayout(center, 1)

        # ── Log de eventos ─────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color:{_BORDER};")
        root.addWidget(sep2)

        self._log = EventLog()
        root.addWidget(self._log)

        self._active_profile_lbl = QLabel("")
        self._active_profile_lbl.setStyleSheet(
            f"font-size:11px;color:{_CYAN};font-family:'Consolas','Courier New',monospace;")
        root.addWidget(self._active_profile_lbl)

        # ── Info teclado ───────────────────────────────────────────────────
        info = QLabel(
            "Teclado → A=A  B=S  X=D  Y=W  LB=Q  RB=E  LT=Z  RT=C  "
            "Select=Tab  Start=Intro  Home=H  D-pad=↑↓←→  LS-clic=F  RS-clic=G")
        info.setStyleSheet(
            f"font-size:10px;color:{_TXT_GH};"
            f"font-family:'Consolas','Courier New',monospace;")
        info.setWordWrap(True)
        root.addWidget(info)
        self._restore_slot_state()

    # ── Slots ──────────────────────────────────────────────────────────────
    def _on_devices(self, names: list):
        self._known_devices = names[:] if names else ["Teclado"]
        current = self._cmb.currentText()
        self._cmb.blockSignals(True)
        self._cmb.clear()
        self._cmb.addItems(names)
        idx = self._cmb.findText(current)
        if idx >= 0:
            self._cmb.setCurrentIndex(idx)
        self._cmb.blockSignals(False)
        self._restore_slot_state()

    def _on_device_selected(self, idx: int):
        # idx 0 = teclado, idx 1+ = mando 0,1,...
        self._selected_jid = idx - 1
        self._device_by_slot[self._current_category][self._current_slot] = self._cmb.currentText()
        self._update_active_profile_label()

    def _on_category_changed(self):
        self._current_category = "arcade" if self._cmb_category.currentIndex() == 0 else "consola"
        self._restore_slot_state()

    def _on_slot_changed(self):
        self._current_slot = self._cmb_slot.currentText() or "1"
        self._restore_slot_state()

    def _save_profile_name(self):
        name = self._cmb_profile.currentText().strip()
        if not name:
            return
        self._profiles_by_slot[self._current_category][self._current_slot] = name
        if self._cmb_profile.findText(name) < 0:
            self._cmb_profile.addItem(name)
        self._update_active_profile_label()

    def _restore_slot_state(self):
        profile = self._profiles_by_slot[self._current_category][self._current_slot]
        device_name = self._device_by_slot[self._current_category][self._current_slot]

        self._cmb_profile.blockSignals(True)
        self._cmb_profile.clear()
        base_profiles = sorted({
            self._profiles_by_slot[self._current_category]["1"],
            self._profiles_by_slot[self._current_category]["2"],
            self._profiles_by_slot[self._current_category]["3"],
        })
        self._cmb_profile.addItems(base_profiles)
        if self._cmb_profile.findText(profile) < 0:
            self._cmb_profile.addItem(profile)
        self._cmb_profile.setCurrentText(profile)
        self._cmb_profile.blockSignals(False)

        self._cmb.blockSignals(True)
        dev_idx = self._cmb.findText(device_name)
        if dev_idx < 0:
            dev_idx = self._cmb.findText("Teclado")
        self._cmb.setCurrentIndex(max(0, dev_idx))
        self._cmb.blockSignals(False)
        self._selected_jid = self._cmb.currentIndex() - 1
        self._update_active_profile_label()

    def _update_active_profile_label(self):
        cat = "Arcade" if self._current_category == "arcade" else "Consola"
        dev = self._cmb.currentText() or "Teclado"
        prof = self._profiles_by_slot[self._current_category][self._current_slot]
        self._active_profile_lbl.setText(
            f"Perfil activo → {cat} / Mando {self._current_slot}: {prof} [{dev}]"
        )

    def _on_btn(self, jid: int, name: str, pressed: bool):
        if jid != self._selected_jid:
            return
        self._controller.set_button(name, pressed)
        state = "▼" if pressed else "▲"
        cat = "Arcade" if self._current_category == "arcade" else "Consola"
        self._log.log(f"[{cat} M{self._current_slot}] {name} {state}")

    def _on_axis(self, jid: int, stick: str, x: float, y: float):
        if jid != self._selected_jid:
            return
        if stick == "left":
            self._stick_l.set_pos(x, y)
            self._controller.set_axis("left", x, y)
        else:
            self._stick_r.set_pos(x, y)
            self._controller.set_axis("right", x, y)

    # ── Teclado ────────────────────────────────────────────────────────────
    _KEY_MAP = {
        Qt.Key.Key_A:      "btn_a",
        Qt.Key.Key_B:      "btn_b",   # remapeo práctico → S para B
        Qt.Key.Key_S:      "btn_b",
        Qt.Key.Key_X:      "btn_x",
        Qt.Key.Key_D:      "btn_x",
        Qt.Key.Key_W:      "btn_y",
        Qt.Key.Key_Y:      "btn_y",
        Qt.Key.Key_Q:      "lb",
        Qt.Key.Key_E:      "rb",
        Qt.Key.Key_Z:      "lt",
        Qt.Key.Key_C:      "rt",
        Qt.Key.Key_Tab:    "select",
        Qt.Key.Key_Return: "start",
        Qt.Key.Key_H:      "home",
        Qt.Key.Key_Up:     "dpad_up",
        Qt.Key.Key_Down:   "dpad_down",
        Qt.Key.Key_Left:   "dpad_left",
        Qt.Key.Key_Right:  "dpad_right",
        Qt.Key.Key_F:      "ls",
        Qt.Key.Key_G:      "rs",
    }

    def keyPressEvent(self, event: QKeyEvent):
        if self._selected_jid != -1:
            return
        if event.isAutoRepeat():
            return
        name = self._KEY_MAP.get(event.key())
        if name:
            self._controller.set_button(name, True)
            self._log.log(f"[Teclado] {name} ▼  (tecla {event.text() or event.key().name})")

    def keyReleaseEvent(self, event: QKeyEvent):
        if self._selected_jid != -1:
            return
        if event.isAutoRepeat():
            return
        name = self._KEY_MAP.get(event.key())
        if name:
            self._controller.set_button(name, False)
            self._log.log(f"[Teclado] {name} ▲")

    def closeEvent(self, event):
        self._bridge.stop()
        if PYGAME_OK:
            pygame.quit()
        super().closeEvent(event)

    def export_state(self) -> dict:
        return {
            "category": self._current_category,
            "slot": self._current_slot,
            "profiles_by_slot": self._profiles_by_slot,
            "device_by_slot": self._device_by_slot,
        }

    def load_state(self, data: dict):
        if not isinstance(data, dict):
            return
        prof = data.get("profiles_by_slot", {})
        devs = data.get("device_by_slot", {})
        for cat in ("arcade", "consola"):
            if isinstance(prof.get(cat), dict):
                for slot in ("1", "2", "3"):
                    val = prof[cat].get(slot)
                    if isinstance(val, str) and val.strip():
                        self._profiles_by_slot[cat][slot] = val.strip()
            if isinstance(devs.get(cat), dict):
                for slot in ("1", "2", "3"):
                    val = devs[cat].get(slot)
                    if isinstance(val, str) and val.strip():
                        self._device_by_slot[cat][slot] = val.strip()

        cat = data.get("category", "arcade")
        slot = data.get("slot", "1")
        self._current_category = cat if cat in ("arcade", "consola") else "arcade"
        self._current_slot = slot if slot in ("1", "2", "3") else "1"

        self._cmb_category.blockSignals(True)
        self._cmb_category.setCurrentIndex(0 if self._current_category == "arcade" else 1)
        self._cmb_category.blockSignals(False)
        self._cmb_slot.blockSignals(True)
        self._cmb_slot.setCurrentText(self._current_slot)
        self._cmb_slot.blockSignals(False)
        self._restore_slot_state()


class ControlsTab(TabModule):
    """Adaptador del probador de mandos para integrarlo como pestaña cargable."""
    tab_title = "🎮 Controls"
    tab_icon = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._widget = None

    def widget(self):
        if self._widget is None:
            self._widget = ControllerTesterWidget()
        return self._widget

    def load_data(self, config: dict):
        if self._widget is None:
            self._widget = ControllerTesterWidget()
        state = config.get("controls_profiles", {})
        self._widget.load_state(state)
        return None

    def save_data(self) -> dict:
        if self._widget is None:
            return {"controls_profiles": {}}
        return {"controls_profiles": self._widget.export_state()}


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = QWidget()
    win.setWindowTitle("Controller Tester — HyperSpin Manager")
    win.setMinimumSize(820, 640)
    win.setStyleSheet(f"QWidget{{background:{_BG};}}")

    lay = QVBoxLayout(win)
    lay.setContentsMargins(0, 0, 0, 0)
    tester = ControllerTesterWidget()
    lay.addWidget(tester)

    win.show()
    sys.exit(app.exec())
