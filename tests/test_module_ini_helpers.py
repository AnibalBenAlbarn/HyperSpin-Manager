from pathlib import Path

from core.module_ini_helpers import (
    append_pclauncher_game,
    append_teknoparrot_game,
    parse_pclauncher_games_ini,
    parse_teknoparrot_games_ini,
    remove_games_from_module_ini,
)


def test_pclauncher_extended_fields_roundtrip(tmp_path: Path):
    ini = tmp_path / "PC Games.ini"
    append_pclauncher_game(
        str(ini),
        game_name="Street Fighter V",
        application=r"E:\\Games\\SFV\\sfv.exe",
        fade_title="SFV ahk_class UnrealWindow",
        exit_method="TaskKill",
        app_wait_exe="sfv.exe",
        post_launch=r"E:\\tools\\launch_helper.exe",
        post_exit=r"E:\\tools\\cleanup.bat",
        fullscreen=True,
        fade_title_timeout=5000,
    )

    rows = parse_pclauncher_games_ini(str(ini))
    assert len(rows) == 1
    row = rows[0]
    assert row["app_wait_exe"] == "sfv.exe"
    assert row["post_launch"].endswith("launch_helper.exe")
    assert row["fullscreen"].lower() == "true"


def test_teknoparrot_parser_reads_expected_fields(tmp_path: Path):
    ini = tmp_path / "Namco.ini"
    append_teknoparrot_game(
        str(ini),
        game_name="Initial D Arcade Stage 8",
        short_name="idas8",
        profile_path=r"E:\\TeknoParrot\\UserProfiles\\idas8.xml",
        game_path=r"E:\\roms\\idas8.zip",
    )
    rows = parse_teknoparrot_games_ini(str(ini))
    assert rows[0]["short_name"] == "idas8"
    assert "--profile=" in rows[0]["command_line"]


def test_remove_games_from_module_ini_preserves_preamble(tmp_path: Path):
    ini = tmp_path / "Module.ini"
    ini.write_text(
        "; header\n; keep me\n[Game A]\nApplication=a.exe\n\n[Game B]\nApplication=b.exe\n",
        encoding="utf-8",
    )

    removed = remove_games_from_module_ini(str(ini), {"game b"})
    content = ini.read_text(encoding="utf-8")
    assert removed == 1
    assert "; header" in content
    assert "[Game A]" in content
    assert "[Game B]" not in content
