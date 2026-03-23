"""
tabs/create_system.py
CreateSystemTab — Crea sistemas completos en HyperSpin + RocketLauncher de golpe

CREA TODO de una vez para un sistema nuevo:

HyperSpin:
  Settings/<Sistema>.ini          — todas las secciones reales
  Databases/<Sistema>/<Sistema>.xml
  Databases/Main Menu/All.xml     — añade entrada
  Media/<Sistema>/Images/Wheel|Artwork1-4|Backgrounds|Genre/Wheel|Genre/Backgrounds|
                          Letters|Other|Particle|Special|
                  Sound/Background Music|System Exit|System Start|Wheel Sounds
                  Themes/
                  Video/Override Transitions/

RocketLauncher:
  Settings/<Sistema>/RocketLauncher.ini  — use_global salvo overrides reales
  Settings/<Sistema>/Emulators.ini       — [ROMS] + [EmuladorNombre]
  Settings/<Sistema>/Bezel.ini           — todo use_global
  Settings/<Sistema>/Pause.ini           — todo use_global
  Settings/<Sistema>/Plugins.ini         — vacío (se rellena desde Global)
  Settings/<Sistema>/Games.ini           — comentario plantilla
  Settings/<Sistema>/Game Options.ini    — comentario plantilla
  Media/Bezels/<Sistema>/_Default/Horizontal/
  Media/Bezels/<Sistema>/_Default/Vertical/
  Media/Fade/<Sistema>/_Default/
  Media/Artwork/<Sistema>/
  Media/Backgrounds/<Sistema>/_Default/
  Media/Wheels/<Sistema>/_Default/
  Media/Guides/<Sistema>/
  Media/Manuals/<Sistema>/_Default/
  Media/MultiGame/<Sistema>/_Default/
  Media/Music/<Sistema>/
  Media/Videos/<Sistema>/_Default/
  Profiles/JoyToKey/<Sistema>/         — carpeta de perfil JoyToKey
  Profiles/JoyToKey/<Sistema>/<Sistema>.cfg — plantilla MAME.cfg real

RocketLauncherUI:
  Databases/<Sistema>/<Sistema>.xml     — copia/vacío sincronizado con HS
"""

import os
import json
import shutil
import configparser
from pathlib import Path
from typing import Optional

import xml.etree.ElementTree as ET

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QGroupBox, QScrollArea, QFrame, QCheckBox,
    QFileDialog, QMessageBox, QTextEdit, QProgressBar,
    QAbstractItemView, QSizePolicy, QDialog, QDialogButtonBox,
    QListWidget, QListWidgetItem, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

try:
    from main import TabModule
except ImportError:
    class TabModule:
        tab_title = "Modulo"
        tab_icon  = ""
        def __init__(self, parent): self.parent = parent
        def widget(self): raise NotImplementedError
        def load_data(self, config): pass
        def save_data(self): return {}


ROM_EXTENSIONS = {
    ".zip", ".7z", ".rar", ".iso", ".bin", ".cue", ".img",
    ".chd", ".rom", ".nes", ".smc", ".sfc", ".gba", ".gb",
    ".gbc", ".n64", ".z64", ".v64", ".nds", ".3ds", ".cia",
    ".cso", ".pbp", ".elf", ".xex", ".gcm", ".rvz", ".wad",
}

# =============================================================================
# PLANTILLAS DE ARCHIVOS INI (basadas en archivos reales)
# =============================================================================

def make_hs_system_ini(system_name: str, exe_path: str = "",
                       rom_path: str = "", rom_ext: str = "zip") -> str:
    """HyperSpin/Settings/<sistema>.ini — formato real completo."""
    return (
        f"; HyperSpin System INI — {system_name}\n"
        f"; Generado por HyperSpin Manager\n"
        f"\n"
        f"[exe info]\n"
        f"path={exe_path}\n"
        f"rompath={rom_path}\n"
        f"userompath=\n"
        f"exe=\n"
        f"romextension={rom_ext}\n"
        f"parameters=\n"
        f"searchsubfolders=\n"
        f"pcgame=false\n"
        f"winstate=HIDDEN\n"
        f"hyperlaunch=true\n"
        f"\n"
        f"[filters]\n"
        f"parents_only=false\n"
        f"themes_only=false\n"
        f"wheels_only=false\n"
        f"roms_only=false\n"
        f"\n"
        f"[themes]\n"
        f"use_parent_vids=true\n"
        f"use_parent_themes=false\n"
        f"animate_out_default=false\n"
        f"reload_backgrounds=false\n"
        f"\n"
        f"[wheel]\n"
        f"alpha=.15\n"
        f"small_alpha=1\n"
        f"style=normal\n"
        f"speed=low\n"
        f"pin_center_width=500\n"
        f"horz_wheel_y=512\n"
        f"vert_wheel_position=right\n"
        f"y_rotation=center\n"
        f"norm_large=360\n"
        f"norm_small=230\n"
        f"vert_large=400\n"
        f"vert_small=240\n"
        f"pin_large=500\n"
        f"pin_small=200\n"
        f"horz_large=240\n"
        f"horz_small=150\n"
        f"letter_wheel_x=800\n"
        f"letter_wheel_y=384\n"
        f"text_width=700\n"
        f"text_font=Style4\n"
        f"small_text_width=260\n"
        f"large_text_width=400\n"
        f"text_stroke_size=6\n"
        f"text_stroke_color=0x000000\n"
        f"text_color1=0x00BFFD\n"
        f"text_color2=0xFFFFFF\n"
        f"text_color3=0x00BFFD\n"
        f"color_ratio=139\n"
        f"shadow_distance=0\n"
        f"shadow_angle=45\n"
        f"shadow_color=0x000000\n"
        f"shadow_alpha=1\n"
        f"shadow_blur=0\n"
        f"\n"
        f"[pointer]\n"
        f"animated=true\n"
        f"x=975\n"
        f"y=384\n"
        f"\n"
        f"[video defaults]\n"
        f"path=\n"
        f"\n"
        f"[sounds]\n"
        f"game_sounds=true\n"
        f"wheel_click=true\n"
        f"\n"
        f"[navigation]\n"
        f"game_jump=50\n"
        f"use_indexes=false\n"
        f"jump_timer=400\n"
        f"remove_info_wheel=false\n"
        f"remove_info_text=false\n"
        f"use_last_game=false\n"
        f"last_game=\n"
        f"random_game=false\n"
        f"start_on_favorites=false\n"
        f"\n"
        f"[special Art A]\n"
        f"default=false\n"
        f"active=true\n"
        f"x = 512\n"
        f"y = 384\n"
        f"in = .4\n"
        f"out = .4\n"
        f"length = 3\n"
        f"delay = .1\n"
        f"type =normal\n"
        f"start =none\n"
        f"\n"
        f"[special Art B]\n"
        f"default=false\n"
        f"active=true\n"
        f"x = 512\n"
        f"y = 384\n"
        f"in = .4\n"
        f"out = .4\n"
        f"length = 3\n"
        f"delay = .1\n"
        f"type =fade\n"
        f"start =none\n"
        f"\n"
        f"[special Art C]\n"
        f"active=true\n"
        f"x=974\n"
        f"y=12\n"
        f"in=0\n"
        f"out=0\n"
        f"length=3\n"
        f"delay=0\n"
        f"type=fade\n"
        f"start=none\n"
        f"\n"
        f"[Game Text]\n"
        f"game_text_active=true\n"
        f"show_year=true\n"
        f"show_manf=true\n"
        f"show_description=true\n"
        f"text_color1=0xffffff\n"
        f"text_color2=0x0099cc\n"
        f"stroke_color=0x000000\n"
        f"text_font=Style1\n"
        f"text1_textsize=26\n"
        f"text1_strokesize=7\n"
        f"text1_x=32\n"
        f"text1_y=610\n"
        f"text2_textsize=36\n"
        f"text2_strokesize=8\n"
        f"text2_x=30\n"
        f"text2_y=640\n"
    )


def make_rl_emulators_ini(emulator_name: str, emu_path: str = "",
                           rom_path: str = "", rom_ext: str = "zip",
                           module: str = "", virtual: bool = False) -> str:
    """
    RocketLauncher/Settings/<sistema>/Emulators.ini — formato real observado.
    [ROMS] + [EmuladorNombre]
    """
    virtual_line = "Virtual_Emulator=true\n" if virtual else ""
    return (
        f"; Emulators.ini — {emulator_name}\n"
        f"; Generado por HyperSpin Manager\n"
        f"\n"
        f"[ROMS]\n"
        f"Default_Emulator={emulator_name}\n"
        f"Rom_Path={rom_path}\n"
        f"\n"
        f"[{emulator_name}]\n"
        f"Emu_Path={emu_path}\n"
        f"Rom_Extension={rom_ext}\n"
        f"Module={module}\n"
        f"{virtual_line}"
        f"Pause_Save_State_Keys=\n"
        f"Pause_Load_State_Keys=\n"
    )


def make_rl_rocketlauncher_ini(overrides: dict = None) -> str:
    """
    RocketLauncher/Settings/<sistema>/RocketLauncher.ini
    Todo use_global salvo los overrides que se pasen.
    Basado en el archivo real de sistema: Fade_In=true, Bezel_Enabled=true.
    """
    ovr = overrides or {}
    def v(key: str, default: str = "use_global") -> str:
        return ovr.get(key, default)

    return (
        f"; RocketLauncher.ini — Sistema\n"
        f"; Generado por HyperSpin Manager\n"
        f"; Valores 'use_global' heredan del Global RocketLauncher.ini\n"
        f"\n"
        f"[Settings]\n"
        f"Skipchecks=false\n"
        f"Rom_Match_Extension={v('Rom_Match_Extension')}\n"
        f"Block_Input={v('Block_Input')}\n"
        f"Error_Level_Reporting={v('Error_Level_Reporting')}\n"
        f"Lock_Launch={v('Lock_Launch')}\n"
        f"Screen_Rotation_Angle={v('Screen_Rotation_Angle')}\n"
        f"Mode_Rotation_Angle={v('Mode_Rotation_Angle')}\n"
        f"Set_Resolution={v('Set_Resolution')}\n"
        f"\n"
        f"[Desktop]\n"
        f"Hide_Cursor={v('Hide_Cursor')}\n"
        f"Hide_Desktop={v('Hide_Desktop')}\n"
        f"Hide_Taskbar={v('Hide_Taskbar')}\n"
        f"Hide_Emu={v('Hide_Emu')}\n"
        f"Hide_Front_End={v('Hide_Front_End')}\n"
        f"Suspend_Front_End={v('Suspend_Front_End')}\n"
        f"Cursor_Size={v('Cursor_Size')}\n"
        f"\n"
        f"[Exit]\n"
        f"Restore_Front_End_On_Exit={v('Restore_Front_End_On_Exit')}\n"
        f"Restore_Resolution_On_Exit={v('Restore_Resolution_On_Exit')}\n"
        f"Exit_Emulator_Key={v('Exit_Emulator_Key')}\n"
        f"\n"
        f"[Virtual Drive]\n"
        f"Virtual_Drive_Enabled={v('Virtual_Drive_Enabled')}\n"
        f"Virtual_Drive_Use_SCSI={v('Virtual_Drive_Use_SCSI')}\n"
        f"\n"
        f"[Fade]\n"
        f"Fade_In={v('Fade_In', 'use_global')}\n"
        f"Fade_In_Duration={v('Fade_In_Duration')}\n"
        f"Fade_In_Transition_Animation={v('Fade_In_Transition_Animation')}\n"
        f"Fade_In_Delay={v('Fade_In_Delay')}\n"
        f"Fade_In_Exit_Delay={v('Fade_In_Exit_Delay')}\n"
        f"Fade_Out={v('Fade_Out')}\n"
        f"Fade_Out_Extra_Screen={v('Fade_Out_Extra_Screen')}\n"
        f"Fade_Out_Duration={v('Fade_Out_Duration')}\n"
        f"Fade_Out_Transition_Animation={v('Fade_Out_Transition_Animation')}\n"
        f"Fade_Out_Delay={v('Fade_Out_Delay')}\n"
        f"Fade_Out_Exit_Delay={v('Fade_Out_Exit_Delay')}\n"
        f"\n"
        f"[Pause]\n"
        f"Pause_Enabled={v('Pause_Enabled')}\n"
        f"\n"
        f"[Bezel]\n"
        f"Bezel_Enabled={v('Bezel_Enabled', 'use_global')}\n"
        f"Bezel_Instruction_Cards_Enabled={v('Bezel_Instruction_Cards_Enabled')}\n"
        f"\n"
        f"[Statistics]\n"
        f"Statistics_Enabled={v('Statistics_Enabled')}\n"
        f"\n"
        f"[Keymapper]\n"
        f"Keymapper_Enabled={v('Keymapper_Enabled')}\n"
        f"Keymapper_AHK_Method={v('Keymapper_AHK_Method')}\n"
        f"Keymapper={v('Keymapper')}\n"
        f"JoyIDs_Enabled={v('JoyIDs_Enabled')}\n"
        f"\n"
        f"[7z]\n"
        f"7z_Enabled={v('7z_Enabled')}\n"
        f"7z_Extract_Path={v('7z_Extract_Path')}\n"
        f"7z_Delete_Temp={v('7z_Delete_Temp')}\n"
    )


def make_rl_bezel_ini() -> str:
    """RocketLauncher/Settings/<sistema>/Bezel.ini — todo use_global."""
    return (
        "; Bezel.ini — Sistema\n"
        "; Generado por HyperSpin Manager\n"
        "\n"
        "[Settings]\n"
        "Bezel_Supported_Image_Files=use_global\n"
        "Game_Monitor=use_global\n"
        "Bezel_Delay=use_global\n"
        "\n"
        "[Bezel Change]\n"
        "Bezel_Transition_Duration=use_global\n"
        "Bezel_Save_Selected=use_global\n"
        "Extra_FullScreen_Bezel=use_global\n"
        "\n"
        "[Background]\n"
        "Background_Change_Timer=use_global\n"
        "Background_Transition_Animation=use_global\n"
        "Background_Transition_Duration=use_global\n"
        "Use_Backgrounds=use_global\n"
        "\n"
        "[Bezel Change Keys]\n"
        "Next_Bezel_Key=use_global\n"
        "Previous_Bezel_Key=use_global\n"
        "\n"
        "[Instruction Cards General Settings]\n"
        "IC_Positions=use_global\n"
        "IC_Transition_Animation=use_global\n"
        "IC_Transition_Duration=use_global\n"
        "IC_Enable_Transition_Sound=use_global\n"
        "IC_Scale_Factor=use_global\n"
        "IC_Save_Selected=use_global\n"
    )


def make_rl_pause_ini() -> str:
    """
    RocketLauncher/Settings/<sistema>/Pause.ini
    Todo use_global (igual que el archivo real de sistema observado).
    """
    return (
        "; Pause.ini — Sistema\n"
        "; Generado por HyperSpin Manager\n"
        "; Todos los valores heredan del Global Pause.ini\n"
        "\n"
        "[General Options]\n"
        "Mute_when_Loading_Pause=use_global\n"
        "Mute_Sound=use_global\n"
        "Disable_Pause_Menu=use_global\n"
        "Force_Resolution_Change=use_global\n"
        "Controller_Menu_Enabled=use_global\n"
        "ChangeDisc_Menu_Enabled=use_global\n"
        "SaveandLoad_Menu_Enabled=use_global\n"
        "HighScore_Menu_Enabled=use_global\n"
        "Artwork_Menu_Enabled=use_global\n"
        "Guides_Menu_Enabled=use_global\n"
        "Manuals_Menu_Enabled=use_global\n"
        "History_Menu_Enabled=use_global\n"
        "Sound_Menu_Enabled=use_global\n"
        "Settings_Menu_Enabled=use_global\n"
        "Videos_Menu_Enabled=use_global\n"
        "Statistics_Menu_Enabled=use_global\n"
        "MovesList_Menu_Enabled=use_global\n"
        "Shutdown_Label_Enabled=use_global\n"
        "\n"
        "[Main Menu Appearance Options]\n"
        "Main_Menu_Items=use_global\n"
        "Pause_Base_Resolution_Width=use_global\n"
        "Pause_Base_Resolution_Height=use_global\n"
        "Enable_Global_Background=use_global\n"
        "Enable_Clock=use_global\n"
        "Main_Bar_Text_Font=use_global\n"
        "Main_Bar_Text_Font_Size=use_global\n"
        "Main_Menu_Labels=use_global\n"
    )


def make_rl_plugins_ini() -> str:
    """
    RocketLauncher/Settings/<sistema>/Plugins.ini
    Vacío por defecto — se hereda del Global Plugins.ini.
    """
    return (
        "; Plugins.ini — Sistema\n"
        "; Generado por HyperSpin Manager\n"
        "; Se hereda del Global Plugins.ini\n"
    )


def make_rl_games_ini() -> str:
    """RocketLauncher/Settings/<sistema>/Games.ini — plantilla comentada."""
    return (
        "# Games.ini — Reasignacion de emulador por juego\n"
        "# Generado por HyperSpin Manager\n"
        "# Formato:\n"
        "# [nombre_rom]\n"
        "# Emulator=OtroEmulador\n"
        "# System=OtroSistema\n"
    )


def make_rl_game_options_ini() -> str:
    """RocketLauncher/Settings/<sistema>/Game Options.ini — plantilla comentada."""
    return (
        "; Game Options.ini — Opciones por juego\n"
        "; Generado por HyperSpin Manager\n"
        "; Ejemplo:\n"
        "; [nombre_rom]\n"
        "; Bezel_Enabled=false\n"
    )


def make_joytokey_cfg(system_name: str, num_joysticks: int = 2) -> str:
    """
    Plantilla de perfil JoyToKey (.cfg) basada en el formato real de MAME.cfg.
    Genera un perfil base con todos los botones a 0 (sin asignar).
    """
    lines = [
        "{LICENSE_SECTION}",
        "[General]",
        "FileVersion=51",
        f"NumberOfJoysticks={num_joysticks}",
        "DisplayMode=2",
        "UseDiagonalInput=0",
        "UsePOV8Way=0",
        "Threshold=20",
        "Threshold2=20",
        "KeySendMode=0",
    ]
    for joy_n in range(1, num_joysticks + 1):
        lines.append(f"[Joystick {joy_n}]")
        for i in range(1, 9):
            lines.append(f"Axis{i}n=0")
            lines.append(f"Axis{i}p=0")
        for p in range(1, 3):
            for d in range(1, 9):
                lines.append(f"POV{p}-{d}=0")
        lines += [
            "Up-Right=0", "Up- Left=0", "Dn- Left=0", "Dn-Right=0",
            "Up-Right2=0", "Up- Left2=0", "Dn- Left2=0", "Dn-Right2=0",
        ]
        for b in range(1, 33):
            lines.append(f"Button{b:02d}=0")
    return "\n".join(lines) + "\n"


def make_hs_database_xml(system_name: str, games: list = None) -> str:
    """XML de base de datos HyperSpin — formato real sin <header>."""
    root   = ET.Element("menu")
    games  = games or []
    for g in sorted(games, key=lambda x: (x.get("description") or x.get("name", "")).lower()):
        name = g.get("name", "")
        if not name:
            continue
        attrs = {"name": name}
        if g.get("index"):  attrs["index"] = g["index"]
        if g.get("image"):  attrs["image"]  = g["image"]
        el = ET.SubElement(root, "game", **attrs)
        for field in ["description", "cloneof", "crc", "manufacturer",
                      "year", "genre", "rating"]:
            ET.SubElement(el, field).text = str(g.get(field, ""))
        enabled_val = g.get("enabled", True)
        ET.SubElement(el, "enabled").text = "Yes" if enabled_val else "No"

    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")
    import io
    buf = io.BytesIO()
    tree.write(buf, encoding="UTF-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


def add_system_to_main_menu(xml_path: str, system_name: str,
                             genre: str = "", manufacturer: str = "",
                             year: str = ""):
    """Añade una entrada <game> al All.xml / Main Menu.xml si no existe ya."""
    import re as _re
    if os.path.isfile(xml_path):
        with open(xml_path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        clean = _re.sub(r"<!--.*?-->", "", content, flags=_re.DOTALL)
        try:
            root = ET.fromstring(clean)
        except ET.ParseError:
            root = ET.Element("menu")
        # Verificar existencia
        for existing in root.findall("game"):
            if existing.get("name", "").lower() == system_name.lower():
                return  # ya existe
    else:
        root = ET.Element("menu")

    el = ET.SubElement(root, "game", name=system_name)
    if genre:        ET.SubElement(el, "genre").text        = genre
    if year:         ET.SubElement(el, "year").text         = year
    if manufacturer: ET.SubElement(el, "manufacturer").text = manufacturer

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    os.makedirs(os.path.dirname(xml_path) if os.path.dirname(xml_path) else ".", exist_ok=True)
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write("<?xml version='1.0' encoding='utf-8'?>\n")
        f.write(ET.tostring(root, encoding="unicode"))


def read_global_emulators(rl_dir: str) -> list:
    """Lee los emuladores del Global Emulators.ini."""
    ini_path = os.path.join(rl_dir, "Settings", "Global Emulators.ini")
    if not os.path.isfile(ini_path):
        return ["MAME-NEW", "MAME-OLD", "TeknoParrot", "PC-PS3Launcher"]
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    try:
        cfg.read(ini_path, encoding="utf-8")
    except Exception:
        return ["MAME"]
    return [s for s in cfg.sections() if s.lower() not in ("roms", "settings")]


def read_global_emulator_info(rl_dir: str, emulator_name: str) -> dict:
    """Lee los datos de un emulador del Global Emulators.ini."""
    ini_path = os.path.join(rl_dir, "Settings", "Global Emulators.ini")
    if not os.path.isfile(ini_path):
        return {}
    cfg = configparser.RawConfigParser()
    cfg.optionxform = str
    try:
        cfg.read(ini_path, encoding="utf-8")
    except Exception:
        return {}
    if cfg.has_section(emulator_name):
        module_raw = cfg.get(emulator_name, "Module", fallback="")
        return {
            "emu_path":      cfg.get(emulator_name, "Emu_Path",      fallback=""),
            "rom_extension": cfg.get(emulator_name, "Rom_Extension", fallback="zip"),
            "module_raw":    module_raw,
            "module_file":   Path(module_raw).name   if module_raw else "",
            "module_folder": Path(module_raw).parent.name if module_raw else "",
            "virtual":       cfg.get(emulator_name, "Virtual_Emulator", fallback="false").lower() == "true",
        }
    return {}


def read_available_modules(rl_dir: str) -> list:
    """Lista módulos .ahk disponibles en RocketLauncher/Modules/."""
    mods_path = os.path.join(rl_dir, "Modules")
    modules   = []
    if not os.path.isdir(mods_path):
        return modules
    for entry in sorted(os.listdir(mods_path)):
        mod_dir = os.path.join(mods_path, entry)
        if os.path.isdir(mod_dir):
            for f in sorted(os.listdir(mod_dir)):
                if f.endswith(".ahk"):
                    # Guardar como "Carpeta/archivo.ahk" para claridad
                    modules.append(f"{entry}/{f}")
    return modules


def read_joytokey_profiles(rl_dir: str) -> list:
    """Lista los perfiles JoyToKey existentes en Profiles/JoyToKey/."""
    joy_path = os.path.join(rl_dir, "Profiles", "JoyToKey")
    if not os.path.isdir(joy_path):
        return []
    return sorted([d for d in os.listdir(joy_path)
                   if os.path.isdir(os.path.join(joy_path, d))])


# =============================================================================
# WORKER DE CREACION
# =============================================================================

class CreateWorker(QThread):
    log      = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, data: dict, config: dict):
        super().__init__()
        self.data   = data
        self.config = config

    def run(self):
        try:
            self._create_all()
            self.finished.emit(True, "Sistema creado correctamente.")
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.finished.emit(False, str(e))

    def _mk(self, path: str):
        """Crea una carpeta y la registra en el log."""
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            self.log.emit(f"  📁 {os.path.relpath(path)}")

    def _write(self, path: str, content: str, overwrite: bool = False):
        """Escribe un archivo y lo registra en el log."""
        if os.path.isfile(path) and not overwrite:
            self.log.emit(f"  ↷  Omitido (ya existe): {os.path.basename(path)}")
            return
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self.log.emit(f"  📄 {os.path.relpath(path)}")

    def _create_all(self):
        d        = self.data
        cfg      = self.config
        hs_dir   = cfg.get("hyperspin_dir", "")
        rl_dir   = cfg.get("rocketlauncher_dir", "")
        rlui_dir = cfg.get("rocketlauncherui_dir", "")
        sys_name = d["system_name"]
        overwrite = d.get("overwrite_ini", False)

        self.progress.emit(3)
        self.log.emit(f"▶  Creando sistema: {sys_name}")

        # ──────────────────────────────────────────────────────────────────────
        # PASO 1 — HyperSpin/Media/<sistema>/  (estructura completa real)
        # ──────────────────────────────────────────────────────────────────────
        self.log.emit("── HyperSpin Media ──")
        hs_media = os.path.join(hs_dir, "Media", sys_name)
        for sub in [
            "Images/Wheel",
            "Images/Artwork1",
            "Images/Artwork2",
            "Images/Artwork3",
            "Images/Artwork4",
            "Images/Backgrounds",
            "Images/Genre/Wheel",
            "Images/Genre/Backgrounds",
            "Images/Letters",
            "Images/Other",
            "Images/Particle",
            "Images/Special",
            "Sound/Background Music",
            "Sound/System Exit",
            "Sound/System Start",
            "Sound/Wheel Sounds",
            "Themes",
            "Video",
            "Video/Override Transitions",
        ]:
            self._mk(os.path.join(hs_media, sub.replace("/", os.sep)))
        self.progress.emit(15)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 2 — RocketLauncher/Media/<sistema>/  (estructura completa real)
        # ──────────────────────────────────────────────────────────────────────
        self.log.emit("── RocketLauncher Media ──")
        rl_media = os.path.join(rl_dir, "Media")
        for sub in [
            f"Bezels/{sys_name}/_Default/Horizontal",
            f"Bezels/{sys_name}/_Default/Vertical",
            f"Fade/{sys_name}/_Default",
            f"Artwork/{sys_name}",
            f"Backgrounds/{sys_name}/_Default",
            f"Wheels/{sys_name}/_Default",
            f"Guides/{sys_name}",
            f"Manuals/{sys_name}/_Default",
            f"MultiGame/{sys_name}/_Default",
            f"Music/{sys_name}",
            f"Videos/{sys_name}/_Default",
        ]:
            self._mk(os.path.join(rl_media, sub.replace("/", os.sep)))
        self.progress.emit(28)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 3 — HyperSpin/Settings/<sistema>.ini
        # ──────────────────────────────────────────────────────────────────────
        self.log.emit("── HyperSpin Settings ──")
        hs_ini = os.path.join(hs_dir, "Settings", f"{sys_name}.ini")
        self._write(hs_ini, make_hs_system_ini(
            system_name=sys_name,
            exe_path=d.get("emu_path", ""),
            rom_path=d.get("rom_path", ""),
            rom_ext=d.get("rom_ext", "zip"),
        ), overwrite=overwrite)
        self.progress.emit(38)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 4 — RocketLauncher/Settings/<sistema>/  (todos los INIs reales)
        # ──────────────────────────────────────────────────────────────────────
        self.log.emit("── RocketLauncher Settings ──")
        rl_settings = os.path.join(rl_dir, "Settings", sys_name)
        self._mk(rl_settings)

        # Obtener info del emulador del Global para construir bien el Module path
        emu_name     = d.get("emulator", "MAME")
        emu_global   = read_global_emulator_info(rl_dir, emu_name)
        module_path  = d.get("module", emu_global.get("module_raw", ""))
        rom_ext      = d.get("rom_ext", emu_global.get("rom_extension", "zip"))
        emu_path_val = d.get("emu_path", emu_global.get("emu_path", ""))
        virtual      = emu_global.get("virtual", False) or d.get("is_virtual", False)

        # RL overrides según opciones del formulario
        overrides_dict = {}
        if d.get("fade_in"):    overrides_dict["Fade_In"]    = "true"
        if d.get("bezel_on"):   overrides_dict["Bezel_Enabled"] = "true"

        ini_files = {
            "Emulators.ini":    make_rl_emulators_ini(
                emulator_name=emu_name,
                emu_path=emu_path_val,
                rom_path=d.get("rom_path", ""),
                rom_ext=rom_ext,
                module=module_path,
                virtual=virtual,
            ),
            "RocketLauncher.ini": make_rl_rocketlauncher_ini(overrides=overrides_dict),
            "Bezel.ini":          make_rl_bezel_ini(),
            "Pause.ini":          make_rl_pause_ini(),
            "Plugins.ini":        make_rl_plugins_ini(),
            "Games.ini":          make_rl_games_ini(),
            "Game Options.ini":   make_rl_game_options_ini(),
        }
        for fname, content in ini_files.items():
            self._write(os.path.join(rl_settings, fname), content, overwrite=overwrite)
        self.progress.emit(55)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 5 — Perfil JoyToKey
        # ──────────────────────────────────────────────────────────────────────
        if d.get("create_joytokey"):
            self.log.emit("── Perfil JoyToKey ──")
            joy_dir = os.path.join(rl_dir, "Profiles", "JoyToKey", sys_name)
            self._mk(joy_dir)
            cfg_path = os.path.join(joy_dir, f"{sys_name}.cfg")
            self._write(cfg_path, make_joytokey_cfg(sys_name), overwrite=overwrite)
        self.progress.emit(65)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 6 — TeknoParrot / PCLauncher extras
        # ──────────────────────────────────────────────────────────────────────
        if d.get("is_teknoparrot") and d.get("tp_userprofiles"):
            self.log.emit("── TeknoParrot UserProfiles ──")
            tp_dir = os.path.join(d["tp_userprofiles"], sys_name)
            self._mk(tp_dir)

        if d.get("is_pclauncher") and d.get("pc_exe"):
            self.log.emit("── PCLauncher Games.ini ──")
            games_ini_path = os.path.join(rl_settings, "Games.ini")
            with open(games_ini_path, "a", encoding="utf-8") as f:
                f.write(f"\n; PCLauncher\n[{sys_name}]\nExe_Path={d['pc_exe']}\n")
        self.progress.emit(75)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 7 — Base de datos XML (HyperSpin)
        # ──────────────────────────────────────────────────────────────────────
        self.log.emit("── Base de datos XML ──")
        db_dir  = os.path.join(hs_dir, "Databases", sys_name)
        db_path = os.path.join(db_dir, f"{sys_name}.xml")
        games   = d.get("games", [])
        if games or not os.path.isfile(db_path) or overwrite:
            xml_content = make_hs_database_xml(sys_name, games)
            self._write(db_path, xml_content, overwrite=True)
        self.progress.emit(82)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 8 — Base de datos XML (RocketLauncherUI)
        # ──────────────────────────────────────────────────────────────────────
        if d.get("create_rlui_db") and rlui_dir and os.path.isdir(rlui_dir):
            self.log.emit("── RocketLauncherUI Database ──")
            rlui_db = os.path.join(rlui_dir, "Databases", sys_name, f"{sys_name}.xml")
            if not os.path.isfile(rlui_db) or overwrite:
                xml_content = make_hs_database_xml(sys_name, games)
                self._write(rlui_db, xml_content, overwrite=True)
        self.progress.emit(90)

        # ──────────────────────────────────────────────────────────────────────
        # PASO 9 — Añadir al Main Menu (All.xml + Categories.xml si existen)
        # ──────────────────────────────────────────────────────────────────────
        if d.get("add_main_menu"):
            self.log.emit("── Main Menu ──")
            mm_dir   = os.path.join(hs_dir, "Databases", "Main Menu")
            genre    = d.get("genre", "")
            manuf    = d.get("manufacturer", "")
            year_val = d.get("year", "")

            added_to = []
            for xml_name in ["All.xml", "Main Menu.xml"]:
                xml_path = os.path.join(mm_dir, xml_name)
                if os.path.isfile(xml_path):
                    add_system_to_main_menu(xml_path, sys_name, genre, manuf, year_val)
                    added_to.append(xml_name)
            if not added_to:
                # Crear Main Menu.xml si no existe ninguno
                add_system_to_main_menu(
                    os.path.join(mm_dir, "Main Menu.xml"), sys_name, genre, manuf, year_val)
                added_to.append("Main Menu.xml (nuevo)")

            cats_xml = os.path.join(mm_dir, "Categories.xml")
            if os.path.isfile(cats_xml):
                add_system_to_main_menu(cats_xml, sys_name, genre, manuf, year_val)
                added_to.append("Categories.xml")

            self.log.emit(f"  → Añadido a: {', '.join(added_to)}")
        self.progress.emit(97)

        self.log.emit(f"\n✓  Sistema '{sys_name}' creado correctamente.")
        self.progress.emit(100)


# =============================================================================
# MODULO UI
# =============================================================================

class CreateSystemTab(TabModule):
    tab_title = "➕ Crear sistema"
    tab_icon  = ""

    def __init__(self, parent):
        super().__init__(parent)
        self._config:  dict = {}
        self._games:   list = []
        self._worker:  Optional[CreateWorker] = None
        self._main_widget: Optional[QWidget]  = None

    def widget(self) -> QWidget:
        if self._main_widget is None:
            self._main_widget = self._build()
        return self._main_widget

    def load_data(self, config: dict):
        self._config = config
        if self._main_widget:
            self._populate_emulators()
            self._populate_modules()

    def save_data(self) -> dict:
        return {}

    # ── Construccion UI ────────────────────────────────────────────────────────

    def _build(self) -> QWidget:
        root = QWidget()
        lay  = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_topbar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle{background:#1e2330;}")
        splitter.addWidget(self._build_form())
        splitter.addWidget(self._build_log_panel())
        splitter.setSizes([680, 420])

        lay.addWidget(splitter, 1)
        return root

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background:#080a0f;border-bottom:1px solid #1e2330;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(8)

        title = QLabel("Crear nuevo sistema completo")
        title.setStyleSheet("font-size:15px;font-weight:700;color:#c8cdd8;")

        self.btn_create = QPushButton("✚  Crear sistema")
        self.btn_create.setObjectName("btn_success")
        self.btn_create.setFixedWidth(160)
        self.btn_create.clicked.connect(self._on_create)

        self.btn_reset = QPushButton("↺ Limpiar")
        self.btn_reset.setFixedWidth(90)
        self.btn_reset.clicked.connect(self._reset_form)

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(self.btn_reset)
        lay.addSpacing(8)
        lay.addWidget(self.btn_create)
        return bar

    def _build_form(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        lay     = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 20)
        lay.setSpacing(14)

        lay.addWidget(self._build_basic_group())
        lay.addWidget(self._build_emulator_group())
        lay.addWidget(self._build_roms_group())
        lay.addWidget(self._build_options_group())
        lay.addWidget(self._build_special_group())
        lay.addStretch()

        scroll.setWidget(content)
        return scroll

    # ── Grupos del formulario ─────────────────────────────────────────────────

    def _build_basic_group(self) -> QGroupBox:
        gb  = QGroupBox("Datos del sistema")
        lay = QGridLayout(gb)
        lay.setSpacing(8)
        lay.setColumnMinimumWidth(0, 150)
        lay.setColumnStretch(1, 1)

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet("color:#5a6278;font-size:12px;font-weight:600;")
            return l

        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Ej: Capcom Play System III")
        self.inp_name.textChanged.connect(self._validate_name)
        self.lbl_name_status = QLabel("")
        self.lbl_name_status.setStyleSheet("font-size:11px;")

        self.cmb_genre = QComboBox()
        self.cmb_genre.setEditable(True)
        for g in ["", "Arcades", "Consoles", "Handhelds", "Computers",
                  "Lightgun", "Utilities", "Other"]:
            self.cmb_genre.addItem(g)

        self.inp_manufacturer = QLineEdit()
        self.inp_manufacturer.setPlaceholderText("Ej: Capcom")
        self.inp_year = QLineEdit()
        self.inp_year.setPlaceholderText("Ej: 1996")
        self.inp_year.setMaximumWidth(100)

        lay.addWidget(lbl("Nombre del sistema *:"), 0, 0)
        lay.addWidget(self.inp_name,                 0, 1)
        lay.addWidget(self.lbl_name_status,          1, 1)
        lay.addWidget(lbl("Género:"),                2, 0)
        lay.addWidget(self.cmb_genre,                2, 1)
        lay.addWidget(lbl("Fabricante:"),            3, 0)
        lay.addWidget(self.inp_manufacturer,         3, 1)
        lay.addWidget(lbl("Año:"),                   4, 0)
        lay.addWidget(self.inp_year,                 4, 1)
        return gb

    def _build_emulator_group(self) -> QGroupBox:
        gb  = QGroupBox("Emulador y módulo")
        lay = QGridLayout(gb)
        lay.setSpacing(8)
        lay.setColumnMinimumWidth(0, 150)
        lay.setColumnStretch(1, 1)

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet("color:#5a6278;font-size:12px;font-weight:600;")
            return l

        def browse_btn(inp, file_filter=None, is_dir=False):
            btn = QPushButton("…")
            btn.setFixedWidth(28)
            btn.setFixedHeight(30)
            if is_dir:
                btn.clicked.connect(lambda: self._browse_dir(inp))
            else:
                btn.clicked.connect(lambda: self._browse_file(inp, file_filter or "Todos (*.*)"))
            return btn

        # Emulador (del Global)
        self.cmb_emulator = QComboBox()
        self.cmb_emulator.setEditable(True)
        self.cmb_emulator.currentTextChanged.connect(self._on_emulator_changed)

        # Módulo .ahk
        mod_row = QHBoxLayout()
        self.cmb_module = QComboBox()
        self.cmb_module.setEditable(True)
        self.cmb_module.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_refresh_mods = QPushButton("↻")
        btn_refresh_mods.setFixedWidth(28)
        btn_refresh_mods.setFixedHeight(30)
        btn_refresh_mods.clicked.connect(self._populate_modules)
        mod_row.addWidget(self.cmb_module)
        mod_row.addWidget(btn_refresh_mods)

        # Exe del emulador
        exe_row = QHBoxLayout()
        self.inp_emu_exe = QLineEdit()
        self.inp_emu_exe.setPlaceholderText("Ej: ..\\..\\emuladores\\mame.exe")
        exe_row.addWidget(self.inp_emu_exe)
        exe_row.addWidget(browse_btn(self.inp_emu_exe, "Ejecutables (*.exe)"))

        # Extension
        self.inp_rom_ext = QLineEdit("zip")
        self.inp_rom_ext.setPlaceholderText("zip|7z|chd")
        self.inp_rom_ext.setMaximumWidth(180)

        lay.addWidget(lbl("Emulador (Global):"),  0, 0)
        lay.addWidget(self.cmb_emulator,           0, 1)
        lay.addWidget(lbl("Módulo .ahk:"),         1, 0)
        lay.addLayout(mod_row,                      1, 1)
        lay.addWidget(lbl("Exe del emulador:"),    2, 0)
        lay.addLayout(exe_row,                      2, 1)
        lay.addWidget(lbl("Extensión ROM:"),       3, 0)
        lay.addWidget(self.inp_rom_ext,             3, 1)
        return gb

    def _build_roms_group(self) -> QGroupBox:
        gb  = QGroupBox("ROMs y base de datos")
        lay = QGridLayout(gb)
        lay.setSpacing(8)
        lay.setColumnMinimumWidth(0, 150)
        lay.setColumnStretch(1, 1)

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet("color:#5a6278;font-size:12px;font-weight:600;")
            return l

        rom_row = QHBoxLayout()
        self.inp_rom_path = QLineEdit()
        self.inp_rom_path.setPlaceholderText("Carpeta de ROMs del sistema")
        btn_rom = QPushButton("…")
        btn_rom.setFixedWidth(28)
        btn_rom.setFixedHeight(30)
        btn_rom.clicked.connect(lambda: self._browse_dir(self.inp_rom_path))
        rom_row.addWidget(self.inp_rom_path)
        rom_row.addWidget(btn_rom)

        btn_scan = QPushButton("📂 Escanear ROMs → XML")
        btn_scan.setObjectName("btn_primary")
        btn_scan.setFixedWidth(200)
        btn_scan.clicked.connect(self._scan_roms)

        btn_clear = QPushButton("Limpiar lista")
        btn_clear.clicked.connect(self._clear_games)

        self.lbl_games_count = QLabel("0 juegos")
        self.lbl_games_count.setStyleSheet("color:#3a4560;font-size:12px;")

        self.games_list = QListWidget()
        self.games_list.setFixedHeight(100)
        self.games_list.setStyleSheet(
            "QListWidget{background:#0a0d12;border:1px solid #1e2330;"
            "border-radius:6px;font-size:11px;color:#5a6278;}")

        lay.addWidget(lbl("Carpeta ROMs:"), 0, 0)
        lay.addLayout(rom_row,              0, 1)
        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_scan)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(self.lbl_games_count)
        lay.addLayout(btn_row, 1, 0, 1, 2)
        lay.addWidget(self.games_list, 2, 0, 1, 2)
        return gb

    def _build_options_group(self) -> QGroupBox:
        gb  = QGroupBox("Opciones de creación")
        lay = QVBoxLayout(gb)
        lay.setSpacing(6)

        def chk(text, attr, checked=True):
            c = QCheckBox(text)
            c.setChecked(checked)
            c.setStyleSheet("color:#6878a0;font-size:12px;")
            setattr(self, attr, c)
            return c

        lay.addWidget(chk("Sobreescribir archivos INI existentes",             "chk_overwrite",    False))
        lay.addWidget(chk("Añadir al Main Menu / All.xml",                     "chk_add_main_menu"))
        lay.addWidget(chk("Crear base de datos en RocketLauncherUI/Databases", "chk_rlui_db"))
        lay.addWidget(chk("Crear perfil JoyToKey (cfg plantilla)",             "chk_joytokey"))
        lay.addWidget(chk("Activar Fade_In en RocketLauncher.ini",             "chk_fade_in",      False))
        lay.addWidget(chk("Activar Bezel_Enabled en RocketLauncher.ini",       "chk_bezel",        True))
        return gb

    def _build_special_group(self) -> QGroupBox:
        gb  = QGroupBox("Opciones especiales")
        lay = QVBoxLayout(gb)
        lay.setSpacing(8)

        note = QLabel("TeknoParrot, PCLauncher y JoyToKey extra:")
        note.setStyleSheet("color:#3a4a68;font-size:12px;")
        lay.addWidget(note)

        # TeknoParrot
        self.chk_tp = QCheckBox("Sistema TeknoParrot")
        self.chk_tp.setStyleSheet("color:#8892a4;font-size:12px;font-weight:600;")
        self.chk_tp.toggled.connect(self._toggle_tp)
        self.tp_frame = QFrame()
        self.tp_frame.hide()
        tp_lay = QGridLayout(self.tp_frame)
        tp_lay.setSpacing(6)
        lbl_tp = QLabel("UserProfiles:")
        lbl_tp.setStyleSheet("color:#5a6278;font-size:12px;")
        tp_row = QHBoxLayout()
        self.inp_tp = QLineEdit()
        self.inp_tp.setPlaceholderText("TeknoParrot/UserProfiles")
        btn_tp = QPushButton("…")
        btn_tp.setFixedWidth(28)
        btn_tp.setFixedHeight(30)
        btn_tp.clicked.connect(lambda: self._browse_dir(self.inp_tp))
        tp_row.addWidget(self.inp_tp)
        tp_row.addWidget(btn_tp)
        tp_lay.addWidget(lbl_tp, 0, 0)
        tp_lay.addLayout(tp_row, 0, 1)

        # PCLauncher
        self.chk_pc = QCheckBox("Sistema PCLauncher")
        self.chk_pc.setStyleSheet("color:#8892a4;font-size:12px;font-weight:600;")
        self.chk_pc.toggled.connect(self._toggle_pc)
        self.pc_frame = QFrame()
        self.pc_frame.hide()
        pc_lay = QGridLayout(self.pc_frame)
        pc_lay.setSpacing(6)
        lbl_pc = QLabel("Exe del juego:")
        lbl_pc.setStyleSheet("color:#5a6278;font-size:12px;")
        pc_row = QHBoxLayout()
        self.inp_pc = QLineEdit()
        self.inp_pc.setPlaceholderText("Ruta al ejecutable")
        btn_pc = QPushButton("…")
        btn_pc.setFixedWidth(28)
        btn_pc.setFixedHeight(30)
        btn_pc.clicked.connect(lambda: self._browse_file(self.inp_pc, "Ejecutables (*.exe)"))
        pc_row.addWidget(self.inp_pc)
        pc_row.addWidget(btn_pc)
        pc_lay.addWidget(lbl_pc, 0, 0)
        pc_lay.addLayout(pc_row, 0, 1)

        lay.addWidget(self.chk_tp)
        lay.addWidget(self.tp_frame)
        lay.addWidget(self.chk_pc)
        lay.addWidget(self.pc_frame)
        return gb

    def _build_log_panel(self) -> QWidget:
        w   = QWidget()
        w.setStyleSheet("background:#0a0d12;border-left:1px solid #1e2330;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        hdr = QLabel("Log de creación")
        hdr.setStyleSheet(
            "font-size:11px;font-weight:700;color:#3a4560;"
            "letter-spacing:0.8px;text-transform:uppercase;")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("El log aparecerá aquí al crear el sistema…")
        self.log_view.setStyleSheet(
            "QTextEdit{background:#080a0f;border:1px solid #1e2330;"
            "border-radius:6px;color:#4a6080;"
            "font-family:Consolas,monospace;font-size:11px;padding:6px;}")

        self.create_progress = QProgressBar()
        self.create_progress.setValue(0)
        self.create_progress.setFixedHeight(4)
        self.create_progress.hide()
        self.create_progress.setStyleSheet(
            "QProgressBar{background:#0d0f14;border:none;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1b5e20,stop:1 #69f0ae);}")

        btn_clear = QPushButton("Limpiar log")
        btn_clear.setFixedWidth(100)
        btn_clear.clicked.connect(self.log_view.clear)

        lay.addWidget(hdr)
        lay.addWidget(self.log_view, 1)
        lay.addWidget(self.create_progress)
        lay.addWidget(btn_clear, 0, Qt.AlignRight)
        return w

    # ── Lógica ────────────────────────────────────────────────────────────────

    def _populate_emulators(self):
        rl_dir = self._config.get("rocketlauncher_dir", "")
        emus   = read_global_emulators(rl_dir) if rl_dir else []
        self.cmb_emulator.clear()
        self.cmb_emulator.addItems(emus if emus else ["MAME"])

    def _populate_modules(self):
        rl_dir  = self._config.get("rocketlauncher_dir", "")
        modules = read_available_modules(rl_dir) if rl_dir else []
        self.cmb_module.clear()
        self.cmb_module.addItems(modules if modules else [""])

    def _on_emulator_changed(self, text: str):
        """Al cambiar emulador, autorellenar módulo y exe desde el Global."""
        rl_dir = self._config.get("rocketlauncher_dir", "")
        if not rl_dir or not text:
            return
        info = read_global_emulator_info(rl_dir, text)
        if not info:
            return
        # Autorellenar módulo si está vacío
        if info.get("module_raw"):
            # Buscar en la lista
            folder_file = f"{info['module_folder']}/{info['module_file']}"
            idx = self.cmb_module.findText(folder_file)
            if idx >= 0:
                self.cmb_module.setCurrentIndex(idx)
            else:
                self.cmb_module.setCurrentText(info["module_raw"])
        # Autorellenar exe
        if info.get("emu_path") and not self.inp_emu_exe.text():
            self.inp_emu_exe.setText(info["emu_path"])
        # Autorellenar extensión
        if info.get("rom_extension"):
            self.inp_rom_ext.setText(info["rom_extension"])

    def _validate_name(self):
        name   = self.inp_name.text().strip()
        hs_dir = self._config.get("hyperspin_dir", "")
        if not name:
            self.lbl_name_status.setText("")
            return
        existing = os.path.join(hs_dir, "Databases", name) if hs_dir else ""
        if existing and os.path.isdir(existing):
            self.lbl_name_status.setText("⚠ Ya existe (se actualizará si marcas 'Sobreescribir')")
            self.lbl_name_status.setStyleSheet("color:#ffb74d;font-size:11px;")
        else:
            self.lbl_name_status.setText("✓ Nombre disponible")
            self.lbl_name_status.setStyleSheet("color:#69f0ae;font-size:11px;")

    def _toggle_tp(self, checked: bool):
        self.tp_frame.setVisible(checked)

    def _toggle_pc(self, checked: bool):
        self.pc_frame.setVisible(checked)

    def _scan_roms(self):
        folder = self.inp_rom_path.text().strip()
        if not folder or not os.path.isdir(folder):
            folder = QFileDialog.getExistingDirectory(
                self.parent, "Seleccionar carpeta de ROMs", "")
        if not folder:
            return
        self._games = []
        for f in sorted(os.listdir(folder)):
            if not os.path.isfile(os.path.join(folder, f)):
                continue
            if Path(f).suffix.lower() not in ROM_EXTENSIONS:
                continue
            stem = Path(f).stem
            self._games.append({
                "name": stem, "description": stem,
                "year": "", "manufacturer": "", "genre": "", "rating": "",
                "enabled": True,
            })
        self.games_list.clear()
        for g in self._games:
            self.games_list.addItem(g["name"])
        self.lbl_games_count.setText(f"{len(self._games)} juegos")

    def _clear_games(self):
        self._games = []
        self.games_list.clear()
        self.lbl_games_count.setText("0 juegos")

    def _reset_form(self):
        self.inp_name.clear()
        self.cmb_genre.setCurrentIndex(0)
        self.inp_manufacturer.clear()
        self.inp_year.clear()
        self.cmb_emulator.setCurrentIndex(0)
        self.cmb_module.setCurrentIndex(0)
        self.inp_emu_exe.clear()
        self.inp_rom_ext.setText("zip")
        self.inp_rom_path.clear()
        self.chk_overwrite.setChecked(False)
        self.chk_add_main_menu.setChecked(True)
        self.chk_rlui_db.setChecked(True)
        self.chk_joytokey.setChecked(True)
        self.chk_fade_in.setChecked(False)
        self.chk_bezel.setChecked(True)
        self.chk_tp.setChecked(False)
        self.chk_pc.setChecked(False)
        self._clear_games()
        self.log_view.clear()
        self.create_progress.hide()
        self.create_progress.setValue(0)
        self.lbl_name_status.setText("")

    # ── Acción de creación ─────────────────────────────────────────────────────

    def _on_create(self):
        name   = self.inp_name.text().strip()
        hs_dir = self._config.get("hyperspin_dir", "")
        rl_dir = self._config.get("rocketlauncher_dir", "")

        if not name:
            QMessageBox.warning(self.parent, "Nombre requerido",
                                "El nombre del sistema no puede estar vacío.")
            return
        if not hs_dir or not os.path.isdir(hs_dir):
            QMessageBox.critical(self.parent, "Configuración incompleta",
                                 "El directorio de HyperSpin no está configurado.")
            return
        if not rl_dir or not os.path.isdir(rl_dir):
            QMessageBox.critical(self.parent, "Configuración incompleta",
                                 "El directorio de RocketLauncher no está configurado.")
            return

        # Obtener el path completo del módulo seleccionado
        mod_raw = self.cmb_module.currentText().strip()
        # Si tiene el formato "Carpeta/archivo.ahk", convertir al path relativo real
        if "/" in mod_raw and not mod_raw.startswith("."):
            parts   = mod_raw.split("/", 1)
            mod_raw = f"..\\{parts[0]}\\{parts[1]}"

        data = {
            "system_name":     name,
            "genre":           self.cmb_genre.currentText().strip(),
            "manufacturer":    self.inp_manufacturer.text().strip(),
            "year":            self.inp_year.text().strip(),
            "emulator":        self.cmb_emulator.currentText().strip(),
            "module":          mod_raw,
            "emu_path":        self.inp_emu_exe.text().strip(),
            "rom_path":        self.inp_rom_path.text().strip(),
            "rom_ext":         self.inp_rom_ext.text().strip() or "zip",
            "games":           self._games,
            "overwrite_ini":   self.chk_overwrite.isChecked(),
            "add_main_menu":   self.chk_add_main_menu.isChecked(),
            "create_rlui_db":  self.chk_rlui_db.isChecked(),
            "create_joytokey": self.chk_joytokey.isChecked(),
            "fade_in":         self.chk_fade_in.isChecked(),
            "bezel_on":        self.chk_bezel.isChecked(),
            "is_teknoparrot":  self.chk_tp.isChecked(),
            "tp_userprofiles": self.inp_tp.text().strip() if self.chk_tp.isChecked() else "",
            "is_pclauncher":   self.chk_pc.isChecked(),
            "pc_exe":          self.inp_pc.text().strip() if self.chk_pc.isChecked() else "",
        }

        self.btn_create.setEnabled(False)
        self.create_progress.show()
        self.create_progress.setValue(0)
        self.log_view.clear()

        self._worker = CreateWorker(data, self._config)
        self._worker.log.connect(self.log_view.append)
        self._worker.progress.connect(self.create_progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, success: bool, message: str):
        self.btn_create.setEnabled(True)
        if success:
            self.create_progress.setValue(100)
            if self.parent:
                self.parent.statusBar().showMessage(
                    f"✓ Sistema '{self.inp_name.text()}' creado correctamente.", 6000)
            QMessageBox.information(self.parent, "Sistema creado", message)
        else:
            self.create_progress.hide()
            self.log_view.append(f"\n✗ Error: {message}")
            QMessageBox.critical(self.parent, "Error al crear", message)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _browse_dir(self, inp: QLineEdit):
        path = QFileDialog.getExistingDirectory(
            self.parent, "Seleccionar directorio",
            inp.text() or os.path.expanduser("~"))
        if path:
            inp.setText(path)

    def _browse_file(self, inp: QLineEdit, filt: str = "Todos (*.*)"):
        start = os.path.dirname(inp.text()) if inp.text() else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Seleccionar archivo", start, filt)
        if path:
            inp.setText(path)
