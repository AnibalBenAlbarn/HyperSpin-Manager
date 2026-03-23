"""
tabs/create_system.py
CreateSystemTab — Crea sistemas completos en HyperSpin + RocketLauncher de golpe

CREA TODO de una vez para un sistema nuevo:

HyperSpin:
  Settings/<Sistema>.ini
  Databases/<Sistema>/<Sistema>.xml
  Databases/Main Menu/All.xml     — añade entrada
  Media/<Sistema>/Images/Wheel|Artwork1-4|Backgrounds|Genre/…|Letters|Other|Particle|Special
                  Sound/Background Music|System Exit|System Start|Wheel Sounds
                  Themes/   Video/Override Transitions/

RocketLauncher:
  Settings/<Sistema>/RocketLauncher.ini  — use_global salvo overrides
  Settings/<Sistema>/Emulators.ini       — [ROMS] + [EmuladorNombre]
  Settings/<Sistema>/Bezel.ini           — todo use_global
  Settings/<Sistema>/Pause.ini           — todo use_global
  Settings/<Sistema>/Plugins.ini
  Settings/<Sistema>/Games.ini           — reasignación de emulador (siempre)
  Settings/<Sistema>/Game Options.ini
  Settings/<Sistema>/<Sistema>.ini       — INI PROPIO DEL MÓDULO (PCLauncher/TeknoParrot)
                                           ← se llama igual que el sistema, NO Games.ini
                                           ← PC Games.ini, Namco System 246-256.ini, etc.
  Media/Bezels/<Sistema>/_Default/Horizontal|Vertical/
  Media/Fade/<Sistema>/_Default/
  Media/Artwork/<Sistema>/
  Media/Backgrounds/<Sistema>/_Default/
  Media/Wheels/<Sistema>/_Default/
  Media/Guides/<Sistema>/
  Media/Manuals/<Sistema>/_Default/
  Media/MultiGame/<Sistema>/_Default/
  Media/Music/<Sistema>/
  Media/Videos/<Sistema>/_Default/
  Profiles/JoyToKey/<Sistema>/<Sistema>.cfg

RocketLauncherUI:
  Databases/<Sistema>/<Sistema>.xml
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
WINDOWS_INVALID_NAME_CHARS = set('<>:"/\\|?*')

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
    """
    RocketLauncher/Settings/<sistema>/Games.ini
    Plantilla comentada para reasignar emulador por juego.
    NOTA: Para PCLauncher y TeknoParrot se usa un archivo distinto.
    """
    return (
        "# Games.ini — Reasignacion de emulador o sistema por juego\n"
        "# Generado por HyperSpin Manager\n"
        "#\n"
        "# Formato para reasignar emulador:\n"
        "#   [nombre_rom]\n"
        "#   Emulator=OtroEmulador\n"
        "#\n"
        "# Formato para redirigir a otro sistema:\n"
        "#   [nombre_rom]\n"
        "#   System=OtroSistema\n"
    )


def make_rl_game_options_ini() -> str:
    """RocketLauncher/Settings/<sistema>/Game Options.ini — plantilla comentada."""
    return (
        "; Game Options.ini — Opciones especificas por juego\n"
        "; Generado por HyperSpin Manager\n"
        ";\n"
        "; Ejemplo — desactivar bezel para un juego:\n"
        ";   [nombre_rom]\n"
        ";   Bezel_Enabled=false\n"
        ";\n"
        "; Ejemplo — rotar pantalla para un juego vertical:\n"
        ";   [nombre_rom]\n"
        ";   Screen_Rotation_Angle=90\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# PCLauncher — Games.ini
#
# Formato real observado (PC_Games.ini):
#   [Nombre del juego en HyperSpin]    ← debe coincidir con el name del XML
#   Application=E:\ruta\al\exe.exe     ← ruta absoluta O relativa con ..\..\
#   FadeTitle=Titulo ahk_class ClaseVentana   ← opcional, para detectar la ventana
#   ExitMethod=InGame                  ← opcional: InGame | Send Alt+F4 | TaskKill
#   AppWaitExe=nombre.exe              ← opcional: exe a esperar si difiere del Application
#   PostLaunch=ruta\a\exe.exe          ← opcional: ejecutar tras lanzar el juego
#   PostExit=ruta\a\bat.bat            ← opcional: ejecutar al salir
#   Fullscreen=true                    ← opcional: forzar pantalla completa
#   FadeTitleTimeout=6000              ← opcional: ms a esperar la ventana de fade
# ─────────────────────────────────────────────────────────────────────────────

def make_pclauncher_games_ini_entry(
        game_name: str,
        application: str,
        fade_title: str = "",
        exit_method: str = "InGame",
        app_wait_exe: str = "",
        post_launch: str = "",
        post_exit: str = "",
        fullscreen: bool = False,
        fade_title_timeout: int = 0,
) -> str:
    """
    Genera una entrada del Games.ini de PCLauncher para un juego.

    IMPORTANTE: el [nombre] debe ser exactamente el campo `name` del XML de HyperSpin.
    """
    lines = [f"[{game_name}]", f"Application={application}"]
    if fade_title:
        lines.append(f"FadeTitle={fade_title}")
    if exit_method:
        lines.append(f"ExitMethod={exit_method}")
    if app_wait_exe:
        lines.append(f"AppWaitExe={app_wait_exe}")
    if fullscreen:
        lines.append("Fullscreen=true")
    if fade_title_timeout > 0:
        lines.append(f"FadeTitleTimeout={fade_title_timeout}")
    if post_launch:
        lines.append(f"PostLaunch={post_launch}")
    if post_exit:
        lines.append(f"PostExit={post_exit}")
    return "\n".join(lines) + "\n"


def make_pclauncher_games_ini_template(system_name: str) -> str:
    """
    Plantilla inicial de Games.ini para un sistema PCLauncher.
    Incluye cabecera explicativa con todos los campos posibles.
    """
    return (
        f"; Games.ini — PCLauncher — {system_name}\n"
        f"; Generado por HyperSpin Manager\n"
        f";\n"
        f"; FORMATO DE CADA JUEGO:\n"
        f";   [Nombre exacto del juego en el XML de HyperSpin]\n"
        f";   Application=E:\\ruta\\al\\juego.exe           (OBLIGATORIO)\n"
        f";   FadeTitle=Titulo ahk_class ClaseVentana      (recomendado)\n"
        f";   ExitMethod=InGame                            (InGame | Send Alt+F4 | TaskKill)\n"
        f";   AppWaitExe=nombre.exe                        (si difiere del exe de Application)\n"
        f";   PostLaunch=ruta\\exe.exe                      (lanzar tras iniciar el juego)\n"
        f";   PostExit=ruta\\archivo.bat                    (ejecutar al salir)\n"
        f";   Fullscreen=true                              (opcional)\n"
        f";   FadeTitleTimeout=6000                        (ms, opcional)\n"
        f";\n"
        f"; RUTAS RELATIVAS: se calculan desde la carpeta de RocketLauncher\n"
        f";   Ej: ..\\..\\4-PC\\MiJuego\\game.exe\n"
        f";\n"
        f"; Añade tus juegos debajo:\n"
    )


def append_pclauncher_game(games_ini_path: str, game_name: str,
                            application: str, fade_title: str = "",
                            exit_method: str = "InGame",
                            app_wait_exe: str = "", post_launch: str = "",
                            post_exit: str = "", fullscreen: bool = False,
                            fade_title_timeout: int = 0) -> bool:
    """
    Añade o actualiza una entrada en el Games.ini de PCLauncher.
    Si el juego ya existe lo sobreescribe; si no, lo añade al final.
    Devuelve True si tuvo que sobreescribir una entrada existente.
    """
    entry = make_pclauncher_games_ini_entry(
        game_name, application, fade_title, exit_method,
        app_wait_exe, post_launch, post_exit, fullscreen, fade_title_timeout)

    if not os.path.isfile(games_ini_path):
        with open(games_ini_path, "w", encoding="utf-8") as f:
            f.write(make_pclauncher_games_ini_template("PCLauncher") + "\n" + entry)
        return False

    # Leer existente y buscar si ya hay una entrada con ese nombre
    with open(games_ini_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    section_header = f"[{game_name}]"
    if section_header in content:
        import re as _re
        # Coincide desde [NombreJuego] hasta el inicio de la siguiente sección
        # (línea que empieza con [ sin ser un comentario ; )
        # Usamos lookahead para no consumir la siguiente sección
        pattern = _re.compile(
            r"(?m)^\[" + _re.escape(game_name) + r"\].*?(?=^\[(?![^\]]*#)|\Z)",
            _re.DOTALL | _re.MULTILINE)
        replacement = entry
        new_content = pattern.sub(lambda m: replacement, content, count=1)
        with open(games_ini_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    else:
        with open(games_ini_path, "a", encoding="utf-8") as f:
            f.write("\n" + entry)
        return False


def get_module_ini_path(rl_dir: str, system_name: str) -> str:
    """
    Devuelve la ruta del INI propio del módulo para un sistema.
    PCLauncher y TeknoParrot usan: Settings/<Sistema>/<Sistema>.ini
    Ej: Settings/PC Games/PC Games.ini
        Settings/Namco System 246-256/Namco System 246-256.ini
    """
    return os.path.join(rl_dir, "Settings", system_name, f"{system_name}.ini")


def _read_ini_skip_preamble(ini_path: str) -> configparser.RawConfigParser:
    """
    Lee un INI que puede tener líneas de comentario/cabecera antes del primer [section].
    configparser falla silenciosamente con contenido pre-sección; esta función lo elimina.
    """
    cfg = configparser.RawConfigParser(strict=False)
    cfg.optionxform = str
    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # Saltar líneas que no son secciones ni claves (antes del primer [section])
        import re as _re
        first_section = next(
            (i for i, l in enumerate(lines) if _re.match(r"^\s*\[[^\]]+\]", l)), None)
        if first_section is not None:
            content = "".join(lines[first_section:])
        else:
            content = "".join(lines)
        cfg.read_string(content)
    except Exception:
        pass
    return cfg


def parse_pclauncher_games_ini(games_ini_path: str) -> list:
    """
    Lee un Games.ini de PCLauncher y devuelve lista de dicts.
    Soporta archivos con cabecera de comentarios antes del primer juego.
    Campos: name, application, fade_title, exit_method, app_wait_exe,
            post_launch, post_exit, fullscreen, fade_title_timeout
    """
    games = []
    if not os.path.isfile(games_ini_path):
        return games
    cfg = _read_ini_skip_preamble(games_ini_path)
    for section in cfg.sections():
        games.append({
            "name":               section,
            "application":        cfg.get(section, "Application",        fallback=""),
            "fade_title":         cfg.get(section, "FadeTitle",          fallback=""),
            "exit_method":        cfg.get(section, "ExitMethod",         fallback=""),
            "app_wait_exe":       cfg.get(section, "AppWaitExe",         fallback=""),
            "post_launch":        cfg.get(section, "PostLaunch",         fallback=""),
            "post_exit":          cfg.get(section, "PostExit",           fallback=""),
            "fullscreen":         cfg.get(section, "Fullscreen",         fallback=""),
            "fade_title_timeout": cfg.get(section, "FadeTitleTimeout",   fallback=""),
        })
    return games


# ─────────────────────────────────────────────────────────────────────────────
# TeknoParrot — Games.ini del sistema
#
# Formato real observado (Namco System 246-256.ini, Namco System 357-369.ini):
#   [Nombre del juego en HyperSpin]
#   ShortName = acedriv3                              ← nombre corto / ROM name
#   FadeTitle = Play! - [ NRALOAD0 ] - TeknoParrot ahk_class Qt5152QWindowIcon
#   CommandLine = TeknoParrotUi.exe --startMinimized --profile="ruta\perfil.xml"
#   GamePath = E:\ARCADE\2-ROMS\...\acedriv3.zip     ← ruta al archivo de ROM
#
# DIFERENCIAS con PCLauncher:
#   - ShortName = el nombre corto (= rom name en HyperSpin XML)
#   - CommandLine en vez de Application (lanza TeknoParrotUi con parámetros)
#   - GamePath = ruta a la ROM (no al exe)
#   - FadeTitle usa "Qt5152QWindowIcon" o "Qt692QWindowIcon"
# ─────────────────────────────────────────────────────────────────────────────

# Clase de ventana por versión de TeknoParrot
TP_WINDOW_CLASS = {
    "new":    "Qt5152QWindowIcon",  # TP moderno
    "rpcs3":  "Qt692QWindowIcon",   # TP con RPCS3 (Namco 357-369)
    "old":    "Qt5QWindowIcon",
}
TP_DEFAULT_FADE = "Play! - [ {short} ] - TeknoParrot ahk_class Qt5152QWindowIcon"


def make_teknoparrot_games_ini_entry(
        game_name: str,
        short_name: str,
        profile_path: str,
        game_path: str = "",
        fade_title: str = "",
        tp_exe: str = "TeknoParrotUi.exe",
        window_class: str = "Qt5152QWindowIcon",
) -> str:
    """
    Genera una entrada del Games.ini de TeknoParrot para un juego.

    IMPORTANTE:
      - game_name: debe coincidir exactamente con el `name` del XML de HyperSpin
      - short_name: el nombre corto del juego (= rom name, coincide con el .xml del UserProfile)
      - profile_path: ruta COMPLETA al .xml del UserProfile de TeknoParrot
      - game_path: ruta a la ROM/iso/zip del juego
    """
    if not fade_title:
        fade_title = f"Play! - [ {short_name} ] - TeknoParrot ahk_class {window_class}"
    command_line = f'{tp_exe} --startMinimized --profile="{profile_path}"'
    lines = [
        f"[{game_name}]",
        f"ShortName = {short_name}",
        f"FadeTitle = {fade_title}",
        f"CommandLine = {command_line}",
    ]
    if game_path:
        lines.append(f"GamePath = {game_path}")
    return "\n".join(lines) + "\n"


def make_teknoparrot_games_ini_template(system_name: str) -> str:
    """
    Plantilla inicial de Games.ini para un sistema TeknoParrot.
    """
    return (
        f"; Games.ini — TeknoParrot — {system_name}\n"
        f"; Generado por HyperSpin Manager\n"
        f";\n"
        f"; FORMATO DE CADA JUEGO:\n"
        f";   [Nombre exacto del juego en el XML de HyperSpin]\n"
        f";   ShortName = romname                   (nombre corto = nombre del .xml en UserProfiles)\n"
        f";   FadeTitle = Play! - [ romname ] - TeknoParrot ahk_class Qt5152QWindowIcon\n"
        f";   CommandLine = TeknoParrotUi.exe --startMinimized --profile=\"ruta\\romname.xml\"\n"
        f";   GamePath = E:\\ARCADE\\2-ROMS\\sistema\\romname.zip\n"
        f";\n"
        f"; Para juegos RPCS3 (Namco 357-369) cambiar la clase de ventana:\n"
        f";   FadeTitle = RPCS3 via TeknoParrot ahk_class Qt692QWindowIcon\n"
        f";\n"
        f"; Los UserProfiles (.xml) van en:\n"
        f";   TeknoParrot\\UserProfiles\\romname.xml\n"
        f";\n"
        f"; Añade tus juegos debajo:\n"
    )


def append_teknoparrot_game(games_ini_path: str, game_name: str,
                             short_name: str, profile_path: str,
                             game_path: str = "", fade_title: str = "",
                             tp_exe: str = "TeknoParrotUi.exe",
                             window_class: str = "Qt5152QWindowIcon") -> bool:
    """
    Añade o actualiza una entrada en el Games.ini de TeknoParrot.
    Devuelve True si sobreescribió una entrada existente.
    """
    entry = make_teknoparrot_games_ini_entry(
        game_name, short_name, profile_path, game_path,
        fade_title, tp_exe, window_class)

    if not os.path.isfile(games_ini_path):
        with open(games_ini_path, "w", encoding="utf-8") as f:
            f.write(make_teknoparrot_games_ini_template("TeknoParrot") + "\n" + entry)
        return False

    with open(games_ini_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    section_header = f"[{game_name}]"
    if section_header in content:
        import re as _re
        pattern = _re.compile(
            r"(?m)^\[" + _re.escape(game_name) + r"\].*?(?=^\[(?![^\]]*#)|\Z)",
            _re.DOTALL | _re.MULTILINE)
        replacement = entry
        new_content = pattern.sub(lambda m: replacement, content, count=1)
        with open(games_ini_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    else:
        with open(games_ini_path, "a", encoding="utf-8") as f:
            f.write("\n" + entry)
        return False


def parse_teknoparrot_games_ini(games_ini_path: str) -> list:
    """
    Lee un Games.ini de TeknoParrot y devuelve lista de dicts.
    Soporta archivos con cabecera de comentarios antes del primer juego.
    Campos: name, short_name, fade_title, command_line, game_path
    """
    games = []
    if not os.path.isfile(games_ini_path):
        return games
    cfg = _read_ini_skip_preamble(games_ini_path)
    for section in cfg.sections():
        games.append({
            "name":         section,
            "short_name":   cfg.get(section, "ShortName",    fallback="").strip(),
            "fade_title":   cfg.get(section, "FadeTitle",    fallback="").strip(),
            "command_line": cfg.get(section, "CommandLine",  fallback="").strip(),
            "game_path":    cfg.get(section, "GamePath",     fallback="").strip(),
        })
    return games


def detect_tp_window_class(games_ini_path: str) -> str:
    """
    Detecta la clase de ventana TeknoParrot leyendo las entradas existentes.
    Útil para saber si es un sistema RPCS3 (Qt692) o normal (Qt5152).
    """
    games = parse_teknoparrot_games_ini(games_ini_path)
    for g in games:
        ft = g.get("fade_title", "")
        if "Qt692" in ft:
            return "Qt692QWindowIcon"
        if "Qt5152" in ft:
            return "Qt5152QWindowIcon"
    return "Qt5152QWindowIcon"  # default


# Reutilizar implementación compartida de helpers de módulo.
from core.module_ini_helpers import (
    append_pclauncher_game as append_pclauncher_game,
    append_teknoparrot_game as append_teknoparrot_game,
    detect_tp_window_class as detect_tp_window_class,
    parse_pclauncher_games_ini as parse_pclauncher_games_ini,
    parse_teknoparrot_games_ini as parse_teknoparrot_games_ini,
)
from core.rl_ini_helpers import get_module_ini_path as get_module_ini_path


def make_rl_emulators_ini_pclauncher(system_name: str, rl_dir: str = "") -> str:
    r"""
    Emulators.ini especializado para sistemas PCLauncher.
    Basado en el formato real del Global Emulators.ini:
      [PC-PS3Launcher]
      Emu_Path=..\..\3-EMULADORES\Dummy.bat
      Rom_Extension=bat|exe
      Module=..\PCLauncher\PCLauncher.ahk
      Virtual_Emulator=true
    """
    dummy_path = os.path.join(rl_dir, "..\\..\\3-EMULADORES\\Dummy.bat") if rl_dir else \
                 "..\\..\\3-EMULADORES\\Dummy.bat"
    return (
        f"; Emulators.ini — {system_name} (PCLauncher)\n"
        f"; Generado por HyperSpin Manager\n"
        f"\n"
        f"[ROMS]\n"
        f"Default_Emulator=PC-PS3Launcher\n"
        f"Rom_Path=\n"
        f"\n"
        f"[PC-PS3Launcher]\n"
        f"Emu_Path=..\\..\\3-EMULADORES\\Dummy.bat\n"
        f"Rom_Extension=bat|exe\n"
        f"Module=..\\PCLauncher\\PCLauncher.ahk\n"
        f"Virtual_Emulator=true\n"
        f"Pause_Save_State_Keys=\n"
        f"Pause_Load_State_Keys=\n"
    )


def make_rl_emulators_ini_teknoparrot(system_name: str,
                                       tp_exe_path: str = "") -> str:
    r"""
    Emulators.ini especializado para sistemas TeknoParrot.
    Basado en el formato real del Global Emulators.ini:
      [TeknoParrot]
      Emu_Path=..\..\3-EMULADORES\1-PLACAS ARCADE\TEKNOPARROT\TeknoParrotUi.exe
      Rom_Extension=
      Module=TeknoParrot.ahk
      Virtual_Emulator=true
    """
    if not tp_exe_path:
        tp_exe_path = "..\\..\\3-EMULADORES\\1-PLACAS ARCADE\\TEKNOPARROT\\TeknoParrotUi.exe"
    return (
        f"; Emulators.ini — {system_name} (TeknoParrot)\n"
        f"; Generado por HyperSpin Manager\n"
        f"\n"
        f"[ROMS]\n"
        f"Default_Emulator=TeknoParrot\n"
        f"Rom_Path=\n"
        f"\n"
        f"[TeknoParrot]\n"
        f"Emu_Path={tp_exe_path}\n"
        f"Rom_Extension=\n"
        f"Module=TeknoParrot.ahk\n"
        f"Virtual_Emulator=true\n"
        f"Pause_Save_State_Keys=\n"
        f"Pause_Load_State_Keys=\n"
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

        # Emulators.ini — usar plantilla especializada para TP y PCLauncher
        is_tp  = d.get("is_teknoparrot", False)
        is_pc  = d.get("is_pclauncher", False)
        if is_tp:
            emulators_ini_content = make_rl_emulators_ini_teknoparrot(
                sys_name, tp_exe_path=d.get("tp_exe_path", ""))
        elif is_pc:
            emulators_ini_content = make_rl_emulators_ini_pclauncher(sys_name, rl_dir)
        else:
            emulators_ini_content = make_rl_emulators_ini(
                emulator_name=emu_name,
                emu_path=emu_path_val,
                rom_path=d.get("rom_path", ""),
                rom_ext=rom_ext,
                module=module_path,
                virtual=virtual,
            )

        # Games.ini estándar de RL (reasignación de emulador — siempre se crea)
        # El INI del módulo es DISTINTO y se llama <NombreSistema>.ini
        ini_files = {
            "Emulators.ini":    emulators_ini_content,
            "RocketLauncher.ini": make_rl_rocketlauncher_ini(overrides=overrides_dict),
            "Bezel.ini":          make_rl_bezel_ini(),
            "Pause.ini":          make_rl_pause_ini(),
            "Plugins.ini":        make_rl_plugins_ini(),
            "Games.ini":          make_rl_games_ini(),      # siempre: reasignación RL
            "Game Options.ini":   make_rl_game_options_ini(),
        }
        for fname, content in ini_files.items():
            self._write(os.path.join(rl_settings, fname), content, overwrite=overwrite)

        # INI PROPIO DEL MÓDULO — se llama igual que el sistema
        # PCLauncher lee:  Settings/<Sistema>/<Sistema>.ini
        # TeknoParrot lee: Settings/<Sistema>/<Sistema>.ini
        # El módulo lo busca por el nombre del sistema en su propia carpeta de Settings
        if is_pc:
            module_ini_path = os.path.join(rl_settings, f"{sys_name}.ini")
            self._write(module_ini_path, make_pclauncher_games_ini_template(sys_name),
                        overwrite=overwrite)
            self.log.emit(f"  📄 INI módulo PCLauncher: {sys_name}.ini")
        elif is_tp:
            module_ini_path = os.path.join(rl_settings, f"{sys_name}.ini")
            self._write(module_ini_path, make_teknoparrot_games_ini_template(sys_name),
                        overwrite=overwrite)
            self.log.emit(f"  📄 INI módulo TeknoParrot: {sys_name}.ini")
        else:
            module_ini_path = ""

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
        # PASO 6 — PCLauncher / TeknoParrot — añadir juegos al INI del módulo
        # El INI del módulo se llama <NombreSistema>.ini (NO Games.ini)
        # Ej: Settings/PC Games/PC Games.ini
        #     Settings/Namco System 246-256/Namco System 246-256.ini
        # ──────────────────────────────────────────────────────────────────────
        module_ini = os.path.join(rl_settings, f"{sys_name}.ini")

        if d.get("is_pclauncher") and d.get("pc_games"):
            self.log.emit(f"── PCLauncher — {sys_name}.ini ──")
            for pc_game in d.get("pc_games", []):
                name = pc_game.get("name", "")
                app  = pc_game.get("application", "")
                if not name or not app:
                    continue
                was_updated = append_pclauncher_game(
                    module_ini,
                    game_name=name,
                    application=app,
                    fade_title=pc_game.get("fade_title", ""),
                    exit_method=pc_game.get("exit_method", "InGame"),
                    app_wait_exe=pc_game.get("app_wait_exe", ""),
                    post_launch=pc_game.get("post_launch", ""),
                    post_exit=pc_game.get("post_exit", ""),
                    fullscreen=pc_game.get("fullscreen", False),
                    fade_title_timeout=int(pc_game.get("fade_title_timeout", 0) or 0),
                )
                action = "actualizado" if was_updated else "añadido"
                self.log.emit(f"  🎮 [{name}] {action}")
            self.log.emit(f"  → {module_ini}")

        elif d.get("is_teknoparrot") and d.get("tp_games"):
            self.log.emit(f"── TeknoParrot — {sys_name}.ini ──")
            tp_exe          = d.get("tp_exe_path", "TeknoParrotUi.exe")
            tp_userprofiles = d.get("tp_userprofiles", "")

            for tp_game in d.get("tp_games", []):
                name       = tp_game.get("name", "")
                short_name = tp_game.get("short_name", "")
                if not name or not short_name:
                    continue
                if tp_userprofiles:
                    profile_path = os.path.join(tp_userprofiles, f"{short_name}.xml")
                else:
                    profile_path = tp_game.get("profile_path", f"{short_name}.xml")

                was_updated = append_teknoparrot_game(
                    module_ini,
                    game_name=name,
                    short_name=short_name,
                    profile_path=profile_path,
                    game_path=tp_game.get("game_path", ""),
                    fade_title=tp_game.get("fade_title", ""),
                    tp_exe=tp_exe,
                    window_class=tp_game.get("window_class", "Qt5152QWindowIcon"),
                )
                action = "actualizado" if was_updated else "añadido"
                self.log.emit(f"  🎮 [{name}] ShortName={short_name} {action}")
            self.log.emit(f"  → {module_ini}")

        elif d.get("is_pclauncher") and d.get("pc_exe"):
            # Modo simple: un juego inicial desde el formulario
            self.log.emit(f"── PCLauncher — {sys_name}.ini (juego inicial) ──")
            append_pclauncher_game(
                module_ini,
                game_name=sys_name,
                application=d["pc_exe"],
                fade_title=d.get("pc_fade_title", ""),
                exit_method=d.get("pc_exit_method", "InGame"),
            )
            self.log.emit(f"  🎮 [{sys_name}] añadido")

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
        gb  = QGroupBox("Opciones especiales — TeknoParrot y PCLauncher")
        lay = QVBoxLayout(gb)
        lay.setSpacing(8)

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet("color:#5a6278;font-size:12px;")
            return l

        def browse_dir(inp):
            btn = QPushButton("…"); btn.setFixedWidth(28); btn.setFixedHeight(30)
            btn.clicked.connect(lambda: self._browse_dir(inp))
            return btn

        def browse_file(inp, filt="Ejecutables (*.exe)"):
            btn = QPushButton("…"); btn.setFixedWidth(28); btn.setFixedHeight(30)
            btn.clicked.connect(lambda: self._browse_file(inp, filt))
            return btn

        # ── TeknoParrot ───────────────────────────────────────────────────────
        self.chk_tp = QCheckBox("Sistema TeknoParrot (Virtual emulator)")
        self.chk_tp.setStyleSheet("color:#4fc3f7;font-size:12px;font-weight:700;")
        self.chk_tp.toggled.connect(self._toggle_tp)

        self.tp_frame = QFrame()
        self.tp_frame.hide()
        tp_lay = QGridLayout(self.tp_frame)
        tp_lay.setSpacing(6)
        tp_lay.setColumnMinimumWidth(0, 140)
        tp_lay.setColumnStretch(1, 1)

        tp_exe_row = QHBoxLayout()
        self.inp_tp_exe = QLineEdit()
        self.inp_tp_exe.setPlaceholderText("...\\TEKNOPARROT\\TeknoParrotUi.exe")
        tp_exe_row.addWidget(self.inp_tp_exe)
        tp_exe_row.addWidget(browse_file(self.inp_tp_exe))

        tp_profiles_row = QHBoxLayout()
        self.inp_tp = QLineEdit()
        self.inp_tp.setPlaceholderText("TeknoParrot\\UserProfiles\\")
        tp_profiles_row.addWidget(self.inp_tp)
        tp_profiles_row.addWidget(browse_dir(self.inp_tp))

        self.cmb_tp_wclass = QComboBox()
        self.cmb_tp_wclass.addItems([
            "Qt5152QWindowIcon — TeknoParrot moderno",
            "Qt692QWindowIcon — RPCS3 via TeknoParrot (Namco 357-369)",
            "Qt5QWindowIcon — TeknoParrot antiguo",
        ])

        tp_note = QLabel(
            "ℹ  El Games.ini usa: [NombreJuego] ShortName, FadeTitle, CommandLine, GamePath\n"
            "   Añade juegos individualmente usando la pestaña 🗂 Sistemas → ⚙ INI Audit")
        tp_note.setStyleSheet("color:#3a4560;font-size:11px;")
        tp_note.setWordWrap(True)

        tp_lay.addWidget(lbl("TeknoParrotUi.exe:"), 0, 0)
        tp_lay.addLayout(tp_exe_row,                 0, 1)
        tp_lay.addWidget(lbl("UserProfiles dir:"),  1, 0)
        tp_lay.addLayout(tp_profiles_row,            1, 1)
        tp_lay.addWidget(lbl("Clase ventana:"),     2, 0)
        tp_lay.addWidget(self.cmb_tp_wclass,         2, 1)
        tp_lay.addWidget(tp_note,                    3, 0, 1, 2)

        # ── PCLauncher ────────────────────────────────────────────────────────
        self.chk_pc = QCheckBox("Sistema PCLauncher (juegos PC)")
        self.chk_pc.setStyleSheet("color:#ffb74d;font-size:12px;font-weight:700;")
        self.chk_pc.toggled.connect(self._toggle_pc)

        self.pc_frame = QFrame()
        self.pc_frame.hide()
        pc_lay = QGridLayout(self.pc_frame)
        pc_lay.setSpacing(6)
        pc_lay.setColumnMinimumWidth(0, 140)
        pc_lay.setColumnStretch(1, 1)

        # Juego inicial (opcional)
        pc_app_row = QHBoxLayout()
        self.inp_pc = QLineEdit()
        self.inp_pc.setPlaceholderText("E:\\ARCADE\\4-PC\\MiJuego\\game.exe  (opcional)")
        pc_app_row.addWidget(self.inp_pc)
        pc_app_row.addWidget(browse_file(self.inp_pc))

        self.inp_pc_fadetitle = QLineEdit()
        self.inp_pc_fadetitle.setPlaceholderText(
            "Titulo ahk_class UnityWndClass  (opcional)")

        self.cmb_pc_exit = QComboBox()
        self.cmb_pc_exit.addItems([
            "InGame", "Send Alt+F4", "TaskKill", "CloseMainWindow",
        ])

        self.inp_pc_appwait = QLineEdit()
        self.inp_pc_appwait.setPlaceholderText("game.exe  (si difiere del exe principal)")
        self.inp_pc_appwait.setMaximumWidth(260)

        pc_note = QLabel(
            "ℹ  Games.ini usa: [NombreJuego] Application, FadeTitle, ExitMethod, AppWaitExe…\n"
            "   Para añadir más juegos edita el Games.ini desde 🗂 Sistemas → ⚙ INI Audit")
        pc_note.setStyleSheet("color:#3a4560;font-size:11px;")
        pc_note.setWordWrap(True)

        pc_lay.addWidget(lbl("Application (exe):"), 0, 0)
        pc_lay.addLayout(pc_app_row,                 0, 1)
        pc_lay.addWidget(lbl("FadeTitle:"),          1, 0)
        pc_lay.addWidget(self.inp_pc_fadetitle,       1, 1)
        pc_lay.addWidget(lbl("ExitMethod:"),         2, 0)
        pc_lay.addWidget(self.cmb_pc_exit,            2, 1)
        pc_lay.addWidget(lbl("AppWaitExe:"),         3, 0)
        pc_lay.addWidget(self.inp_pc_appwait,         3, 1)
        pc_lay.addWidget(pc_note,                    4, 0, 1, 2)

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
        invalid = sorted({ch for ch in name if ch in WINDOWS_INVALID_NAME_CHARS})
        if invalid:
            chars = " ".join(invalid)
            self.lbl_name_status.setText(f"✗ Nombre inválido. No se permiten: {chars}")
            self.lbl_name_status.setStyleSheet("color:#ef9a9a;font-size:11px;")
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
        if checked:
            # Auto-poblar desde el Global Emulators.ini
            rl_dir = self._config.get("rocketlauncher_dir", "")
            if rl_dir:
                info = read_global_emulator_info(rl_dir, "TeknoParrot")
                if info.get("emu_path") and not self.inp_tp_exe.text():
                    self.inp_tp_exe.setText(info["emu_path"])
            # Auto-poblar UserProfiles dir desde el ini si ya existe
            if not self.inp_tp.text() and rl_dir:
                tp_profiles = os.path.join(rl_dir, "Profiles", "JoyToKey", "Teknoparrot")
                # Intentar calcular la ruta de UserProfiles de TP desde el exe
                tp_exe = self.inp_tp_exe.text()
                if tp_exe:
                    tp_up = os.path.join(os.path.dirname(tp_exe), "UserProfiles")
                    if os.path.isdir(tp_up):
                        self.inp_tp.setText(tp_up)
            # Si es un sistema de Namco 357-369, seleccionar clase Qt692
            sys_name = self.inp_name.text().lower()
            if any(x in sys_name for x in ["357", "369", "rpcs3"]):
                self.cmb_tp_wclass.setCurrentIndex(1)

    def _toggle_pc(self, checked: bool):
        self.pc_frame.setVisible(checked)
        if checked:
            # Cambiar emulador a PCLauncher automáticamente
            rl_dir = self._config.get("rocketlauncher_dir", "")
            if rl_dir:
                emus = read_global_emulators(rl_dir)
                for emu in emus:
                    if "pclauncher" in emu.lower() or "ps3launcher" in emu.lower():
                        idx = self.cmb_emulator.findText(emu)
                        if idx >= 0:
                            self.cmb_emulator.setCurrentIndex(idx)
                        break
            # Desactivar campos de ROM que no aplican
            self.inp_rom_ext.setText("bat|exe")
            self.inp_rom_path.setPlaceholderText("(no aplica para PCLauncher)")

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
        # TeknoParrot
        self.chk_tp.setChecked(False)
        if hasattr(self, "inp_tp_exe"):     self.inp_tp_exe.clear()
        if hasattr(self, "inp_tp"):         self.inp_tp.clear()
        if hasattr(self, "cmb_tp_wclass"):  self.cmb_tp_wclass.setCurrentIndex(0)
        # PCLauncher
        self.chk_pc.setChecked(False)
        if hasattr(self, "inp_pc"):            self.inp_pc.clear()
        if hasattr(self, "inp_pc_fadetitle"):  self.inp_pc_fadetitle.clear()
        if hasattr(self, "cmb_pc_exit"):       self.cmb_pc_exit.setCurrentIndex(0)
        if hasattr(self, "inp_pc_appwait"):    self.inp_pc_appwait.clear()
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
        invalid = sorted({ch for ch in name if ch in WINDOWS_INVALID_NAME_CHARS})
        if invalid:
            QMessageBox.warning(
                self.parent,
                "Nombre inválido",
                "El nombre del sistema contiene caracteres no válidos para Windows:\n"
                f"{' '.join(invalid)}\n\n"
                "No se creó ningún archivo.",
            )
            return
        if not hs_dir or not os.path.isdir(hs_dir):
            QMessageBox.critical(self.parent, "Configuración incompleta",
                                 "El directorio de HyperSpin no está configurado.")
            return
        if not rl_dir or not os.path.isdir(rl_dir):
            QMessageBox.critical(self.parent, "Configuración incompleta",
                                 "El directorio de RocketLauncher no está configurado.")
            return

        # PCLauncher: construir lista de juegos si hay un exe inicial
        pc_games = []
        if self.chk_pc.isChecked() and self.inp_pc.text().strip():
            sys_n = self.inp_name.text().strip()
            pc_games = [{
                "name":        sys_n,
                "application": self.inp_pc.text().strip(),
                "fade_title":  self.inp_pc_fadetitle.text().strip(),
                "exit_method": self.cmb_pc_exit.currentText(),
                "app_wait_exe": self.inp_pc_appwait.text().strip(),
            }]

        # TeknoParrot: extraer clase de ventana del combo
        tp_wclass_map = {0: "Qt5152QWindowIcon", 1: "Qt692QWindowIcon", 2: "Qt5QWindowIcon"}
        tp_wclass = tp_wclass_map.get(self.cmb_tp_wclass.currentIndex(), "Qt5152QWindowIcon") \
                    if hasattr(self, "cmb_tp_wclass") else "Qt5152QWindowIcon"

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
            # TeknoParrot
            "is_teknoparrot":  self.chk_tp.isChecked(),
            "tp_exe_path":     self.inp_tp_exe.text().strip() if self.chk_tp.isChecked() else "",
            "tp_userprofiles": self.inp_tp.text().strip()     if self.chk_tp.isChecked() else "",
            "tp_window_class": tp_wclass,
            "tp_games":        [],  # se pueden añadir desde el gestor de sistemas
            # PCLauncher
            "is_pclauncher":   self.chk_pc.isChecked(),
            "pc_exe":          self.inp_pc.text().strip() if self.chk_pc.isChecked() else "",
            "pc_games":        pc_games,
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
