"""Helpers XML HyperSpin/RocketLauncherUI (sin Qt)."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any


_XML_CACHE: dict[tuple[str, str], tuple[float, int, Any]] = {}


def _get_cached(kind: str, xml_path: str):
    try:
        st = os.stat(xml_path)
    except OSError:
        return None
    key = (kind, os.path.abspath(xml_path))
    cached = _XML_CACHE.get(key)
    if not cached:
        return None
    cached_mtime, cached_size, cached_value = cached
    if cached_mtime == st.st_mtime and cached_size == st.st_size:
        return cached_value
    return None


def _set_cached(kind: str, xml_path: str, value: Any):
    try:
        st = os.stat(xml_path)
    except OSError:
        return
    key = (kind, os.path.abspath(xml_path))
    _XML_CACHE[key] = (st.st_mtime, st.st_size, value)


def clear_xml_cache():
    _XML_CACHE.clear()


def _normalize_enabled(val: str) -> bool:
    return str(val).strip().lower() in {"yes", "1", "true"}


def _parse_xml_safe(xml_path: str):
    if not xml_path or not os.path.isfile(xml_path):
        return None
    try:
        with open(xml_path, "r", encoding="utf-8-sig", errors="replace") as fh:
            content = fh.read()
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
        return ET.fromstring(content)
    except Exception:
        return None


def parse_xml_games(xml_path: str) -> list[dict]:
    cached = _get_cached("games", xml_path)
    if cached is not None:
        return [dict(row) for row in cached]

    games = []
    root = _parse_xml_safe(xml_path)
    if root is None:
        return games

    for game in root.findall("game"):
        name = game.get("name", "").strip()
        if not name:
            continue
        enabled_raw = game.get("enabled", "") or game.findtext("enabled", "")
        enabled = _normalize_enabled(enabled_raw) if enabled_raw else True
        games.append(
            {
                "name": name,
                "description": game.findtext("description", name).strip() or name,
                "cloneof": game.findtext("cloneof", "").strip(),
                "crc": game.findtext("crc", "").strip(),
                "manufacturer": game.findtext("manufacturer", "").strip(),
                "year": game.findtext("year", "").strip(),
                "genre": game.findtext("genre", "").strip(),
                "rating": game.findtext("rating", "").strip(),
                "enabled": enabled,
                "index": game.get("index", "").strip(),
                "image": game.get("image", "").strip(),
                "exe": game.get("exe", "").strip(),
            }
        )
    _set_cached("games", xml_path, tuple(games))
    return games


def parse_xml_systems(xml_path: str) -> list[dict]:
    cached = _get_cached("systems", xml_path)
    if cached is not None:
        return [dict(row) for row in cached]

    systems = []
    root = _parse_xml_safe(xml_path)
    if root is None:
        return systems

    for game in root.findall("game"):
        name = game.get("name", "").strip()
        if not name:
            continue
        enabled_raw = game.get("enabled", game.findtext("enabled", "1"))
        systems.append(
            {
                "name": name,
                "description": game.findtext("description", name).strip() or name,
                "genre": game.findtext("genre", "").strip(),
                "year": game.findtext("year", "").strip(),
                "manufacturer": game.findtext("manufacturer", "").strip(),
                "enabled": _normalize_enabled(enabled_raw),
                "exe": game.get("exe", "").strip(),
            }
        )
    _set_cached("systems", xml_path, tuple(systems))
    return systems


def save_xml_games(xml_path: str, games: list[dict], menu_name: str = "menu"):
    os.makedirs(os.path.dirname(xml_path) if os.path.dirname(xml_path) else ".", exist_ok=True)
    root = ET.Element(menu_name)

    for g in sorted(games, key=lambda row: (row.get("description") or row.get("name") or "").lower()):
        attrs = {"name": g.get("name", "")}
        if g.get("index"):
            attrs["index"] = g["index"]
        if g.get("image"):
            attrs["image"] = g["image"]
        el = ET.SubElement(root, "game", **attrs)
        ET.SubElement(el, "description").text = g.get("description") or g.get("name", "")
        ET.SubElement(el, "cloneof").text = g.get("cloneof", "")
        ET.SubElement(el, "crc").text = g.get("crc", "")
        ET.SubElement(el, "manufacturer").text = g.get("manufacturer", "")
        ET.SubElement(el, "year").text = g.get("year", "")
        ET.SubElement(el, "genre").text = g.get("genre", "")
        ET.SubElement(el, "rating").text = g.get("rating", "")
        ET.SubElement(el, "enabled").text = "Yes" if bool(g.get("enabled", True)) else "No"

    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")
    tree.write(xml_path, encoding="UTF-8", xml_declaration=True)
    clear_xml_cache()


def _append_system_element(parent: ET.Element, data: dict):
    attrs = {"name": data.get("name", "")}
    if data.get("exe"):
        attrs["exe"] = data["exe"]
    if not data.get("enabled", True):
        attrs["enabled"] = "0"
    el = ET.SubElement(parent, "game", **attrs)
    if data.get("genre"):
        ET.SubElement(el, "genre").text = data["genre"]
    if data.get("year"):
        ET.SubElement(el, "year").text = data["year"]
    if data.get("manufacturer"):
        ET.SubElement(el, "manufacturer").text = data["manufacturer"]


def save_xml_systems(xml_path: str, systems: list[dict], include_comments: bool = True):
    os.makedirs(os.path.dirname(xml_path) if os.path.dirname(xml_path) else ".", exist_ok=True)
    root = ET.Element("menu")

    if include_comments:
        from collections import defaultdict

        by_genre: dict[str, list] = defaultdict(list)
        without_genre: list[dict] = []
        for system in systems:
            genre = system.get("genre", "").strip()
            if genre:
                by_genre[genre].append(system)
            else:
                without_genre.append(system)

        for genre, rows in sorted(by_genre.items()):
            root.append(ET.Comment(f" ================= {genre.upper()} ================= "))
            for row in sorted(rows, key=lambda x: (x.get("year", ""), x.get("name", ""))):
                _append_system_element(root, row)
        for row in without_genre:
            _append_system_element(root, row)
    else:
        for row in sorted(systems, key=lambda x: x.get("name", "").lower()):
            _append_system_element(root, row)

    with open(xml_path, "w", encoding="utf-8") as fh:
        fh.write("<?xml version='1.0' encoding='utf-8'?>\n")
        fh.write(ET.tostring(root, encoding="unicode"))
    clear_xml_cache()


def xml_game_count(xml_path: str) -> int:
    root = _parse_xml_safe(xml_path)
    return len(root.findall("game")) if root is not None else -1
