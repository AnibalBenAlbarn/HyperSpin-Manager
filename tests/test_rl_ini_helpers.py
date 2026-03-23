from pathlib import Path

from core.rl_ini_helpers import parse_rl_emulators_ini, read_rl_folder_from_rlui_ini


def test_parse_rl_emulators_ini_realistic_sections(tmp_path: Path):
    ini = tmp_path / "Emulators.ini"
    ini.write_text(
        """[ROMS]
Default_Emulator=MAME-OLD
Rom_Path=..\\..\\2-ROMS\\Arcade

[MAME-OLD]
Emu_Path=..\\..\\3-EMULADORES\\MAME\\mame.exe
Rom_Extension=zip
Module=..\\MAME\\MAME-new.ahk
Virtual_Emulator=true
""",
        encoding="utf-8",
    )

    parsed = parse_rl_emulators_ini(str(ini))
    assert parsed["default_emulator"] == "MAME-OLD"
    emu = parsed["emulators"]["MAME-OLD"]
    assert emu["module_file"] == "MAME-new.ahk"
    assert emu["module_folder"] == "MAME"
    assert emu["virtual"] is True


def test_parse_rl_emulators_ini_without_sections(tmp_path: Path):
    ini = tmp_path / "Emulators.ini"
    ini.write_text(
        "Default_Emulator=MAME-OLD\nRom_Path=..\\ROMS\n",
        encoding="utf-8",
    )
    parsed = parse_rl_emulators_ini(str(ini))
    assert parsed["default_emulator"] == "MAME-OLD"
    assert parsed["rom_path"] == "..\\ROMS"


def test_read_rl_folder_from_rlui_ini_with_bom_and_preamble(tmp_path: Path):
    ini = tmp_path / "RocketLauncherUI.ini"
    ini.write_text(
        "\ufeff; comment before sections\njunk line without equals\nRL_Folder=..\\RocketLauncher\n",
        encoding="utf-8",
    )
    assert read_rl_folder_from_rlui_ini(str(ini)) == "..\\RocketLauncher"
