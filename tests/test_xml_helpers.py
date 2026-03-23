from pathlib import Path

from core.xml_helpers import clear_xml_cache, parse_xml_games, parse_xml_systems


def test_parse_xml_games_preserves_enabled_and_attrs(tmp_path: Path):
    xml = tmp_path / "games.xml"
    xml.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<menu>
  <game name='game1' enabled='Yes' index='01' image='img1'>
    <description>Game One</description>
  </game>
  <game name='game2' enabled='No'>
    <description>Game Two</description>
  </game>
</menu>
""",
        encoding="utf-8",
    )

    rows = parse_xml_games(str(xml))
    assert rows[0]["enabled"] is True
    assert rows[0]["index"] == "01"
    assert rows[0]["image"] == "img1"
    assert rows[1]["enabled"] is False


def test_parse_xml_systems_cache_invalidation_by_mtime(tmp_path: Path):
    clear_xml_cache()
    xml = tmp_path / "systems.xml"
    xml.write_text("<menu><game name='SystemA' enabled='Yes'/></menu>", encoding="utf-8")
    first = parse_xml_systems(str(xml))
    assert first[0]["name"] == "SystemA"

    xml.write_text("<menu><game name='SystemB' enabled='No'/></menu>", encoding="utf-8")
    second = parse_xml_systems(str(xml))
    assert second[0]["name"] == "SystemB"
    assert second[0]["enabled"] is False
