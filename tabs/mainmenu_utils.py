"""
utils/mainmenu_utils.py
=======================
Utilidades para la gestión del Main Menu y MainMenuChanger en HyperSpin.

ARQUITECTURA LOGICA
-------------------
HyperSpin usa dos modos de Main Menu:

  MODO CLASICO:
    Databases/Main Menu/Main Menu.xml   -> lista de sistemas
    Media/Main Menu/Images/             -> wheels de sistemas
    Media/Main Menu/Themes/             -> temas de sistemas

  MODO MAINMENUCHANGER (con All.xml + Categories.xml):
    Databases/Main Menu/All.xml         -> todos los sistemas
    Databases/Main Menu/Categories.xml  -> menu principal (categorias)
    MainMenuChanger/Media/Mode3/Main Menu/
        Images/  -> se copia a -> HyperSpin/Media/Main Menu/Images/
        Themes/  -> se copia a -> HyperSpin/Media/Main Menu/Themes/

REGLA CLAVE:
  - All.xml   contiene TODOS los sistemas (fuente de verdad)
  - Categories.xml  contiene los filtros/generos como entradas <game>
    y se usa como menu principal mientras All.xml sirve de fuente completa.

Referencia: https://hyperspin-fe.com/files/file/11400-main-menu-changer/
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional
from collections import defaultdict
from datetime import datetime

import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# --- Constantes ---------------------------------------------------------------

MMC_MEDIA_REL      = os.path.join("Media", "Mode3", "Main Menu")
HS_MAIN_MENU_DB    = os.path.join("Databases", "Main Menu")
HS_MAIN_MENU_MEDIA = os.path.join("Media", "Main Menu")

CANONICAL_GENRES = [
    "Arcade", "Console", "Computer", "Handheld",
    "Pinball", "Slot Machine", "Other",
]

MAJOR_MANUFACTURERS = [
    "Nintendo", "Sega", "Sony", "Microsoft", "Atari",
    "Capcom", "Konami", "Namco", "SNK", "Taito",
    "Williams", "Midway", "Bally", "Data East",
    "Acclaim", "Activision", "Electronic Arts", "NEC",
]


# =============================================================================
# 1. DETECCION DE MAINMENUCHANGER
# =============================================================================

class MainMenuInfo:
    """
    Contenedor con el estado completo del Main Menu detectado.

    Atributos:
        mode            "classic" | "mainmenuchanger"
        hs_dir          directorio raiz de HyperSpin
        mmc_dir         directorio raiz de MainMenuChanger (si existe)
        all_xml         ruta a All.xml (si existe)
        categories_xml  ruta a Categories.xml (si existe)
        main_menu_xml   ruta a Main Menu.xml (si existe)
        mmc_source_images  carpeta fuente de imagenes MMC
        mmc_source_themes  carpeta fuente de temas MMC
        hs_dest_images  carpeta destino de imagenes en HyperSpin
        hs_dest_themes  carpeta destino de temas en HyperSpin
    """

    def __init__(self, hs_dir: str, mmc_dir: str = ""):
        self.hs_dir  = hs_dir
        self.mmc_dir = mmc_dir
        db_base      = os.path.join(hs_dir, HS_MAIN_MENU_DB)

        self.all_xml        = os.path.join(db_base, "All.xml")
        self.categories_xml = os.path.join(db_base, "Categories.xml")
        self.main_menu_xml  = os.path.join(db_base, "Main Menu.xml")

        if mmc_dir:
            mmc_media = os.path.join(mmc_dir, MMC_MEDIA_REL)
            self.mmc_source_images = os.path.join(mmc_media, "Images")
            self.mmc_source_themes = os.path.join(mmc_media, "Themes")
        else:
            self.mmc_source_images = ""
            self.mmc_source_themes = ""

        hs_media = os.path.join(hs_dir, HS_MAIN_MENU_MEDIA)
        self.hs_dest_images = os.path.join(hs_media, "Images")
        self.hs_dest_themes = os.path.join(hs_media, "Themes")

    @property
    def mode(self) -> str:
        if self.has_mainmenuchanger or (self.has_all_xml and self.has_categories_xml):
            return "mainmenuchanger"
        return "classic"

    @property
    def has_mainmenuchanger(self) -> bool:
        return bool(self.mmc_dir) and os.path.isdir(self.mmc_dir)

    @property
    def has_all_xml(self) -> bool:
        return os.path.isfile(self.all_xml)

    @property
    def has_categories_xml(self) -> bool:
        return os.path.isfile(self.categories_xml)

    @property
    def has_main_menu_xml(self) -> bool:
        return os.path.isfile(self.main_menu_xml)

    @property
    def has_mmc_images(self) -> bool:
        return bool(self.mmc_source_images) and os.path.isdir(self.mmc_source_images)

    @property
    def has_mmc_themes(self) -> bool:
        return bool(self.mmc_source_themes) and os.path.isdir(self.mmc_source_themes)

    def summary(self) -> str:
        lines = [
            f"Modo:           {self.mode.upper()}",
            f"All.xml:        {'OK' if self.has_all_xml else 'FALTA'}",
            f"Categories.xml: {'OK' if self.has_categories_xml else 'FALTA'}",
            f"Main Menu.xml:  {'OK' if self.has_main_menu_xml else 'FALTA'}",
            f"MMC instalado:  {'SI' if self.has_mainmenychanger else 'NO'}",
            f"MMC Images:     {'OK' if self.has_mmc_images else 'FALTA'}",
            f"MMC Themes:     {'OK' if self.has_mmc_themes else 'FALTA'}",
        ]
        return "\n".join(lines)

    # fix typo in property name for summary
    @property
    def has_mainmenychanger(self) -> bool:
        return self.has_mainmenuchanger


def detect_mainmenu(hs_dir: str, mmc_dir: str = "") -> MainMenuInfo:
    """
    Analiza los directorios y devuelve un objeto MainMenuInfo con toda
    la informacion de estado del Main Menu.

    Args:
        hs_dir:  directorio raiz de HyperSpin
        mmc_dir: directorio raiz de MainMenuChanger (vacio = no instalado)

    Returns:
        MainMenuInfo con todo el estado detectado
    """
    return MainMenuInfo(hs_dir, mmc_dir)


def is_mainmenuchanger_installed(hs_dir: str, mmc_dir: str = "") -> bool:
    """
    Comprobacion rapida: es MainMenuChanger esta activo?

    Condiciones para True:
      - El directorio de MMC existe Y contiene Media/Mode3/Main Menu
      - O bien: existen tanto All.xml como Categories.xml en Databases/Main Menu

    Args:
        hs_dir:  directorio raiz de HyperSpin
        mmc_dir: directorio raiz de MainMenuChanger

    Returns:
        bool
    """
    return detect_mainmenu(hs_dir, mmc_dir).mode == "mainmenuchanger"


# =============================================================================
# 2. COPIA DE MEDIA MMC -> HYPERSPIN
# =============================================================================

class CopyResult:
    """Resultado detallado de una operacion de copia."""

    def __init__(self):
        self.copied:   list = []
        self.skipped:  list = []
        self.errors:   list = []
        self.warnings: list = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def total(self) -> int:
        return len(self.copied) + len(self.skipped)

    def summary(self) -> str:
        lines = [
            f"Copiados:  {len(self.copied)}",
            f"Omitidos:  {len(self.skipped)}",
            f"Errores:   {len(self.errors)}",
        ]
        if self.warnings:
            lines.append(f"Avisos:    {len(self.warnings)}")
        return "\n".join(lines)


def copy_mmc_media_to_hyperspin(
    info: "MainMenuInfo",
    overwrite: bool = False,
    copy_images: bool = True,
    copy_themes: bool = True,
    progress_callback=None,
) -> CopyResult:
    """
    Copia las carpetas Images y Themes de MainMenuChanger/Media/Mode3/Main Menu
    al directorio HyperSpin/Media/Main Menu, tal como indica el manual de MMC.

    Args:
        info:              objeto MainMenuInfo (obtener con detect_mainmenu())
        overwrite:         si True, sobreescribe archivos existentes
        copy_images:       copiar subcarpeta Images
        copy_themes:       copiar subcarpeta Themes
        progress_callback: callable(copied, total, filename) para informar progreso

    Returns:
        CopyResult con el detalle de la operacion
    """
    result = CopyResult()

    if not info.has_mainmenuchanger:
        result.errors.append(
            "MainMenuChanger no encontrado en: {}".format(
                info.mmc_dir or "(no configurado)"))
        return result

    pairs = []
    if copy_images and info.mmc_source_images:
        pairs.append((info.mmc_source_images, info.hs_dest_images, "Images"))
    if copy_themes and info.mmc_source_themes:
        pairs.append((info.mmc_source_themes, info.hs_dest_themes, "Themes"))

    if not pairs:
        result.warnings.append("No hay carpetas seleccionadas para copiar.")
        return result

    # Inventariar todos los archivos para calcular progreso
    all_files = []
    for src, dst, label in pairs:
        if not os.path.isdir(src):
            result.warnings.append("Carpeta fuente no existe: {}".format(src))
            continue
        for root, _, files in os.walk(src):
            for f in files:
                all_files.append((root, f, src, dst))

    total = len(all_files)
    done  = 0

    for src_root, filename, base_src, base_dst in all_files:
        rel_path  = os.path.relpath(os.path.join(src_root, filename), base_src)
        src_file  = os.path.join(src_root, filename)
        dest_file = os.path.join(base_dst, rel_path)

        try:
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            if os.path.isfile(dest_file) and not overwrite:
                result.skipped.append(rel_path)
            else:
                shutil.copy2(src_file, dest_file)
                result.copied.append(rel_path)
        except Exception as e:
            result.errors.append("{}: {}".format(rel_path, e))
            logger.error("Error copiando {} -> {}: {}".format(src_file, dest_file, e))

        done += 1
        if progress_callback:
            try:
                progress_callback(done, total, filename)
            except Exception:
                pass

    logger.info(
        "MMC->HS copy: {} copiados, {} omitidos, {} errores".format(
            len(result.copied), len(result.skipped), len(result.errors)))
    return result


def verify_mmc_media_sync(info: "MainMenuInfo") -> dict:
    """
    Comprueba si la media de MMC esta sincronizada con HyperSpin.

    Returns:
        dict con claves:
          "images_synced": bool
          "themes_synced": bool
          "images_missing": list  archivos en MMC pero no en HS
          "themes_missing": list
          "images_extra":   list  archivos en HS pero no en MMC
          "themes_extra":   list
    """
    def _file_sets(folder: str) -> set:
        if not os.path.isdir(folder):
            return set()
        result_set = set()
        for root, _, files in os.walk(folder):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), folder)
                result_set.add(rel)
        return result_set

    mmc_imgs = _file_sets(info.mmc_source_images)
    hs_imgs  = _file_sets(info.hs_dest_images)
    mmc_thm  = _file_sets(info.mmc_source_themes)
    hs_thm   = _file_sets(info.hs_dest_themes)

    return {
        "images_synced":  mmc_imgs <= hs_imgs,
        "themes_synced":  mmc_thm  <= hs_thm,
        "images_missing": sorted(mmc_imgs - hs_imgs),
        "themes_missing": sorted(mmc_thm  - hs_thm),
        "images_extra":   sorted(hs_imgs  - mmc_imgs),
        "themes_extra":   sorted(hs_thm   - mmc_thm),
    }


# =============================================================================
# 3. PARSEO Y ESCRITURA DE XML
# =============================================================================

def _make_header_element(listname: str, version: str = "1.0") -> ET.Element:
    """Crea el elemento <header> estandar de HyperSpin."""
    header = ET.Element("header")
    ET.SubElement(header, "listname").text       = listname
    ET.SubElement(header, "lastlistupdate").text = datetime.now().strftime("%Y-%m-%d")
    ET.SubElement(header, "listversion").text    = version
    ET.SubElement(header, "exporterversion").text = "HyperSpin Manager"
    return header


def _game_element(name: str, description: str = "", genre: str = "",
                  manufacturer: str = "", year: str = "", rating: str = "",
                  enabled: str = "1", cloneof: str = "") -> ET.Element:
    """Crea un elemento <game> completo para XML de HyperSpin."""
    el = ET.Element("game", name=name, index="", image="")
    for tag, val in [
        ("description",  description or name),
        ("cloneof",      cloneof),
        ("crc",          ""),
        ("manufacturer", manufacturer),
        ("year",         year),
        ("genre",        genre),
        ("rating",       rating),
        ("enabled",      enabled),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def parse_hyperspin_xml(xml_path: str) -> tuple:
    """
    Parsea cualquier XML de HyperSpin (Main Menu, sistemas, etc.)

    Returns:
        (header_dict, games_list)
        header_dict: diccionario con los campos del <header>
        games_list:  lista de dicts con todos los atributos de cada <game>
    """
    header_info = {}
    games       = []

    if not xml_path or not os.path.isfile(xml_path):
        return header_info, games

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        hdr = root.find("header")
        if hdr is not None:
            for child in hdr:
                header_info[child.tag] = child.text or ""

        for game_el in root.findall("game"):
            g = {
                "name":         game_el.get("name", ""),
                "index":        game_el.get("index", ""),
                "image":        game_el.get("image", ""),
                "description":  game_el.findtext("description", ""),
                "cloneof":      game_el.findtext("cloneof", ""),
                "crc":          game_el.findtext("crc", ""),
                "manufacturer": game_el.findtext("manufacturer", ""),
                "year":         game_el.findtext("year", ""),
                "genre":        game_el.findtext("genre", ""),
                "rating":       game_el.findtext("rating", ""),
                "enabled":      game_el.findtext("enabled", "1"),
            }
            games.append(g)

    except ET.ParseError as e:
        logger.error("Error parseando {}: {}".format(xml_path, e))

    return header_info, games


def write_hyperspin_xml(xml_path: str, listname: str, games: list,
                        sort: bool = True) -> bool:
    """
    Escribe una lista de juegos a un XML de HyperSpin con formato correcto.

    Args:
        xml_path: ruta de destino
        listname: nombre de la lista (para el <header>)
        games:    lista de dicts con campos del juego
        sort:     ordenar alfabeticamente por description

    Returns:
        True si exito
    """
    try:
        os.makedirs(os.path.dirname(xml_path), exist_ok=True)
        root = ET.Element("menu")
        root.append(_make_header_element(listname))

        sorted_games = (
            sorted(games, key=lambda g: g.get("description", g.get("name", "")).lower())
            if sort else games
        )

        for g in sorted_games:
            root.append(_game_element(
                name=g.get("name", ""),
                description=g.get("description", ""),
                genre=g.get("genre", ""),
                manufacturer=g.get("manufacturer", ""),
                year=g.get("year", ""),
                rating=g.get("rating", ""),
                enabled=g.get("enabled", "1"),
                cloneof=g.get("cloneof", ""),
            ))

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)
        logger.info("XML escrito: {} ({} entradas)".format(xml_path, len(games)))
        return True

    except Exception as e:
        logger.error("Error escribiendo {}: {}".format(xml_path, e))
        return False


# =============================================================================
# 4. CONVERSION MAIN MENU.XML <-> ALL.XML + CATEGORIES.XML
# =============================================================================

class ConversionResult:
    """Resultado de una conversion XML."""

    def __init__(self):
        self.success        = False
        self.source_path    = ""
        self.output_paths   = []
        self.systems_count  = 0
        self.genres_found   = []
        self.warnings       = []
        self.error          = ""

    def summary(self) -> str:
        status = "OK" if self.success else "ERROR"
        lines  = [
            "Resultado:   {}".format(status),
            "Sistemas:    {}".format(self.systems_count),
            "Generos:     {}".format(", ".join(self.genres_found) or "(ninguno)"),
        ]
        for p in self.output_paths:
            lines.append("-> {}".format(p))
        if self.error:
            lines.append("Error: {}".format(self.error))
        for w in self.warnings:
            lines.append("Aviso: {}".format(w))
        return "\n".join(lines)


def main_menu_xml_to_all_and_categories(
    info: "MainMenuInfo",
    genre_field: str = "genre",
    overwrite: bool = False,
) -> ConversionResult:
    """
    Convierte Main Menu.xml al par (All.xml + Categories.xml) del
    formato MainMenuChanger.

    - All.xml:        copia exacta de Main Menu.xml (o fusion si ya existe)
    - Categories.xml: una entrada <game> por genero unico encontrado
                      con name=genre y description=genre

    Args:
        info:        objeto MainMenuInfo
        genre_field: campo a usar para agrupar ("genre" o "manufacturer")
        overwrite:   si False y los archivos existen, fusiona en vez de reemplazar

    Returns:
        ConversionResult
    """
    result = ConversionResult()
    result.source_path = info.main_menu_xml

    if not info.has_main_menu_xml:
        result.error = "No se encontro Main Menu.xml en: {}".format(info.main_menu_xml)
        return result

    _, systems = parse_hyperspin_xml(info.main_menu_xml)
    result.systems_count = len(systems)

    if not systems:
        result.warnings.append("Main Menu.xml esta vacio o no contiene sistemas.")

    # -- All.xml -----------------------------------------------------------------
    if info.has_all_xml and not overwrite:
        _, existing = parse_hyperspin_xml(info.all_xml)
        existing_names = {s["name"] for s in existing}
        to_add = [s for s in systems if s["name"] not in existing_names]
        merged = existing + to_add
        if to_add:
            result.warnings.append(
                "All.xml: fusionados {} sistemas nuevos (ya existian {})".format(
                    len(to_add), len(existing_names)))
        systems_for_all = merged
    else:
        systems_for_all = systems

    if not write_hyperspin_xml(info.all_xml, "All", systems_for_all):
        result.error = "Error escribiendo All.xml"
        return result
    result.output_paths.append(info.all_xml)

    # -- Categories.xml ----------------------------------------------------------
    genres = sorted({
        s.get(genre_field, "").strip()
        for s in systems
        if s.get(genre_field, "").strip()
    })
    if not genres:
        genres = list(CANONICAL_GENRES)
        result.warnings.append(
            "No se encontraron valores en campo '{}'. Usando generos predeterminados.".format(
                genre_field))
    result.genres_found = genres

    if info.has_categories_xml and not overwrite:
        _, existing_cats = parse_hyperspin_xml(info.categories_xml)
        existing_genre_names = {c["name"] for c in existing_cats}
        categories = list(existing_cats)
        for genre in genres:
            if genre not in existing_genre_names:
                categories.append({
                    "name": genre, "description": genre,
                    "genre": genre, "manufacturer": "",
                    "year": "", "rating": "", "enabled": "1",
                })
    else:
        categories = [
            {"name": g, "description": g, "genre": g, "manufacturer": "",
             "year": "", "rating": "", "enabled": "1"}
            for g in genres
        ]

    if not write_hyperspin_xml(info.categories_xml, "Categories", categories, sort=True):
        result.error = "Error escribiendo Categories.xml"
        return result
    result.output_paths.append(info.categories_xml)

    result.success = True
    logger.info("Conversion completada: {} sistemas, {} generos".format(
        result.systems_count, len(genres)))
    return result


def all_and_categories_to_main_menu_xml(
    info: "MainMenuInfo",
    use_all_xml: bool = True,
    overwrite: bool = True,
) -> ConversionResult:
    """
    Operacion inversa: convierte All.xml (o Categories.xml) de vuelta
    a un Main Menu.xml clasico.

    Args:
        info:         objeto MainMenuInfo
        use_all_xml:  si True usa All.xml como fuente; si False usa Categories.xml
        overwrite:    sobreescribir Main Menu.xml si existe

    Returns:
        ConversionResult
    """
    result = ConversionResult()
    source = info.all_xml if use_all_xml else info.categories_xml
    result.source_path = source

    if not os.path.isfile(source):
        result.error = "Archivo fuente no encontrado: {}".format(source)
        return result

    _, systems = parse_hyperspin_xml(source)
    result.systems_count = len(systems)

    if info.has_main_menu_xml and not overwrite:
        _, existing = parse_hyperspin_xml(info.main_menu_xml)
        existing_names = {s["name"] for s in existing}
        to_add  = [s for s in systems if s["name"] not in existing_names]
        systems = existing + to_add
        if to_add:
            result.warnings.append("Fusionados {} sistemas nuevos.".format(len(to_add)))

    if not write_hyperspin_xml(info.main_menu_xml, "Main Menu", systems):
        result.error = "Error escribiendo Main Menu.xml"
        return result

    result.output_paths.append(info.main_menu_xml)
    result.success = True
    return result


# =============================================================================
# 5. GENERACION DE FILTROS
# =============================================================================

def extract_filters(systems: list) -> dict:
    """
    Extrae todos los valores posibles de los campos clave de la lista de sistemas,
    util para construir filtros y sub-wheels.

    Args:
        systems: lista de dicts de sistemas (salida de parse_hyperspin_xml)

    Returns:
        dict con:
          "genres":            {genre: [system_name, ...]}
          "manufacturers":     {manufacturer: [system_name, ...]}
          "years":             {year: [system_name, ...]}
          "all_genres":        lista ordenada de generos unicos
          "all_manufacturers": lista ordenada de fabricantes unicos
    """
    genres        = defaultdict(list)
    manufacturers = defaultdict(list)
    years         = defaultdict(list)

    for s in systems:
        name = s.get("name", "")
        g    = s.get("genre", "").strip()
        m    = s.get("manufacturer", "").strip()
        y    = s.get("year", "").strip()
        if g: genres[g].append(name)
        if m: manufacturers[m].append(name)
        if y: years[y].append(name)

    return {
        "genres":            dict(genres),
        "manufacturers":     dict(manufacturers),
        "years":             dict(years),
        "all_genres":        sorted(genres.keys()),
        "all_manufacturers": sorted(manufacturers.keys()),
    }


def create_genre_filter_xml(
    info: "MainMenuInfo",
    genre: str,
    source_xml: str = "",
    output_path: str = "",
) -> ConversionResult:
    """
    Crea un XML de filtro que contiene solo los sistemas de un genero concreto.
    El archivo resultante se guarda en:
        HyperSpin/Databases/Main Menu/<genre>.xml

    Args:
        info:        MainMenuInfo
        genre:       genero a filtrar
        source_xml:  fuente de sistemas (por defecto: All.xml)
        output_path: destino (por defecto: Databases/Main Menu/<genre>.xml)

    Returns:
        ConversionResult
    """
    result = ConversionResult()
    src = source_xml or (info.all_xml if info.has_all_xml else info.main_menu_xml)
    result.source_path = src

    if not os.path.isfile(src):
        result.error = "Fuente no encontrada: {}".format(src)
        return result

    _, all_systems = parse_hyperspin_xml(src)
    filtered = [
        s for s in all_systems
        if s.get("genre", "").strip().lower() == genre.strip().lower()
    ]
    if not filtered:
        result.warnings.append("No hay sistemas con genero '{}'.".format(genre))

    dest = output_path or os.path.join(info.hs_dir, HS_MAIN_MENU_DB, "{}.xml".format(genre))

    if not write_hyperspin_xml(dest, genre, filtered):
        result.error = "Error escribiendo filtro: {}".format(dest)
        return result

    result.success       = True
    result.systems_count = len(filtered)
    result.genres_found  = [genre]
    result.output_paths  = [dest]
    return result


def create_all_genre_filters(
    info: "MainMenuInfo",
    source_xml: str = "",
    output_dir: str = "",
    progress_callback=None,
) -> dict:
    """
    Crea un archivo de filtro XML por cada genero encontrado en All.xml.

    Args:
        info:              MainMenuInfo
        source_xml:        fuente (por defecto All.xml)
        output_dir:        directorio de salida (por defecto Databases/Main Menu/)
        progress_callback: callable(done, total, genre)

    Returns:
        dict {genre: ConversionResult}
    """
    src = source_xml or (info.all_xml if info.has_all_xml else info.main_menu_xml)
    if not os.path.isfile(src):
        return {}

    _, systems = parse_hyperspin_xml(src)
    genres     = extract_filters(systems)["all_genres"]
    results    = {}
    total      = len(genres)

    for i, genre in enumerate(genres):
        out = os.path.join(
            output_dir or os.path.join(info.hs_dir, HS_MAIN_MENU_DB),
            "{}.xml".format(genre)
        )
        results[genre] = create_genre_filter_xml(
            info, genre, source_xml=src, output_path=out)
        if progress_callback:
            try:
                progress_callback(i + 1, total, genre)
            except Exception:
                pass

    logger.info("Filtros de genero creados: {}".format(len(results)))
    return results


def create_manufacturer_filter_xml(
    info: "MainMenuInfo",
    manufacturer: str,
    source_xml: str = "",
    output_path: str = "",
) -> ConversionResult:
    """
    Crea un XML de filtro por fabricante.

    Args:
        info:         MainMenuInfo
        manufacturer: fabricante a filtrar
        source_xml:   fuente de sistemas
        output_path:  destino del archivo XML

    Returns:
        ConversionResult
    """
    result = ConversionResult()
    src = source_xml or (info.all_xml if info.has_all_xml else info.main_menu_xml)
    result.source_path = src

    if not os.path.isfile(src):
        result.error = "Fuente no encontrada: {}".format(src)
        return result

    _, all_systems = parse_hyperspin_xml(src)
    filtered = [
        s for s in all_systems
        if manufacturer.lower() in s.get("manufacturer", "").lower()
    ]
    if not filtered:
        result.warnings.append("No hay sistemas con fabricante '{}'.".format(manufacturer))

    dest = output_path or os.path.join(
        info.hs_dir, HS_MAIN_MENU_DB, "{}.xml".format(manufacturer))

    if not write_hyperspin_xml(dest, manufacturer, filtered):
        result.error = "Error escribiendo: {}".format(dest)
        return result

    result.success       = True
    result.systems_count = len(filtered)
    result.output_paths  = [dest]
    return result


# =============================================================================
# 6. SUB-WHEELS
# =============================================================================

def create_subwheel(
    info: "MainMenuInfo",
    subwheel_name: str,
    systems: list,
    genre: str = "",
    all_source_xml: str = "",
) -> ConversionResult:
    """
    Crea un sub-wheel: un XML que agrupa sistemas especificos bajo un nombre
    personalizado. Util para crear wheels como "Capcom Classics",
    "Sega 16-bit", "Juegos con Lightgun", etc.

    El XML resultante se guarda en:
        HyperSpin/Databases/Main Menu/<subwheel_name>.xml

    Args:
        info:            MainMenuInfo
        subwheel_name:   nombre del sub-wheel (tambien sera el nombre del XML)
        systems:         lista de nombres de sistemas a incluir
        genre:           genre tag para el sub-wheel (opcional)
        all_source_xml:  fuente completa para obtener metadatos de los sistemas

    Returns:
        ConversionResult
    """
    result = ConversionResult()

    systems_meta = {}
    src = all_source_xml or (info.all_xml if info.has_all_xml else "")
    if src and os.path.isfile(src):
        _, all_sys = parse_hyperspin_xml(src)
        systems_meta = {s["name"]: s for s in all_sys}

    games = []
    for sys_name in systems:
        if sys_name in systems_meta:
            g = dict(systems_meta[sys_name])
        else:
            g = {
                "name": sys_name, "description": sys_name,
                "genre": genre, "manufacturer": "",
                "year": "", "rating": "", "enabled": "1",
            }
        games.append(g)

    dest = os.path.join(info.hs_dir, HS_MAIN_MENU_DB, "{}.xml".format(subwheel_name))
    if not write_hyperspin_xml(dest, subwheel_name, games):
        result.error = "Error escribiendo sub-wheel: {}".format(dest)
        return result

    result.success       = True
    result.systems_count = len(games)
    result.output_paths  = [dest]
    result.genres_found  = [genre] if genre else []
    logger.info("Sub-wheel creado: {} ({} sistemas)".format(dest, len(games)))
    return result


def create_subwheel_from_genre(
    info: "MainMenuInfo",
    genre: str,
    subwheel_name: str = "",
    source_xml: str = "",
) -> ConversionResult:
    """
    Crea un sub-wheel a partir de todos los sistemas de un genero.
    Atajo de create_subwheel() + filtro automatico.

    Args:
        info:          MainMenuInfo
        genre:         genero a usar como fuente
        subwheel_name: nombre del XML (por defecto = genre)
        source_xml:    fuente (por defecto All.xml)

    Returns:
        ConversionResult
    """
    src = source_xml or (info.all_xml if info.has_all_xml else info.main_menu_xml)
    _, all_sys = parse_hyperspin_xml(src)
    filtered   = [s["name"] for s in all_sys
                  if s.get("genre", "").strip().lower() == genre.strip().lower()]
    name       = subwheel_name or genre
    return create_subwheel(info, name, filtered, genre=genre, all_source_xml=src)


def create_subwheel_from_manufacturer(
    info: "MainMenuInfo",
    manufacturer: str,
    subwheel_name: str = "",
    source_xml: str = "",
) -> ConversionResult:
    """
    Crea un sub-wheel a partir de todos los sistemas de un fabricante.

    Args:
        info:          MainMenuInfo
        manufacturer:  fabricante a usar como fuente
        subwheel_name: nombre del XML (por defecto = manufacturer)
        source_xml:    fuente (por defecto All.xml)

    Returns:
        ConversionResult
    """
    src = source_xml or (info.all_xml if info.has_all_xml else info.main_menu_xml)
    _, all_sys = parse_hyperspin_xml(src)
    filtered   = [s["name"] for s in all_sys
                  if manufacturer.lower() in s.get("manufacturer", "").lower()]
    name       = subwheel_name or manufacturer
    return create_subwheel(info, name, filtered, all_source_xml=src)


def list_subwheels(info: "MainMenuInfo") -> list:
    """
    Lista todos los archivos XML en Databases/Main Menu/ que no son
    los archivos principales (All.xml, Categories.xml, Main Menu.xml).
    Cada uno es un potencial sub-wheel o filtro.

    Returns:
        lista de dicts con:
          "name":    nombre del sub-wheel (sin .xml)
          "path":    ruta completa
          "count":   numero de entradas
    """
    db_dir  = os.path.join(info.hs_dir, HS_MAIN_MENU_DB)
    exclude = {"all", "categories", "main menu"}
    result  = []

    if not os.path.isdir(db_dir):
        return result

    for f in sorted(os.listdir(db_dir)):
        if not f.endswith(".xml"):
            continue
        name = f[:-4]
        if name.lower() in exclude:
            continue
        path = os.path.join(db_dir, f)
        _, games = parse_hyperspin_xml(path)
        result.append({
            "name":  name,
            "path":  path,
            "count": len(games),
        })
    return result


# =============================================================================
# 7. EDICION DE CATEGORIES.XML
# =============================================================================

def add_category(
    info: "MainMenuInfo",
    category_name: str,
    genre: str = "",
    create_if_missing: bool = True,
) -> bool:
    """
    Anade una nueva categoria a Categories.xml. Si el archivo no existe
    y create_if_missing=True, lo crea desde cero.

    Args:
        info:               MainMenuInfo
        category_name:      nombre de la categoria
        genre:              valor de <genre>
        create_if_missing:  crear Categories.xml si no existe

    Returns:
        True si exito
    """
    categories = []
    if info.has_categories_xml:
        _, categories = parse_hyperspin_xml(info.categories_xml)
    elif not create_if_missing:
        logger.warning("Categories.xml no existe y create_if_missing=False")
        return False

    if any(c["name"].lower() == category_name.lower() for c in categories):
        logger.info("Categoria ya existe: {}".format(category_name))
        return True

    categories.append({
        "name":        category_name,
        "description": category_name,
        "genre":       genre or category_name,
        "manufacturer": "",
        "year":        "",
        "rating":      "",
        "enabled":     "1",
    })
    return write_hyperspin_xml(info.categories_xml, "Categories", categories, sort=True)


def remove_category(info: "MainMenuInfo", category_name: str) -> bool:
    """
    Elimina una categoria de Categories.xml por nombre.

    Args:
        info:           MainMenuInfo
        category_name:  nombre a eliminar

    Returns:
        True si exito
    """
    if not info.has_categories_xml:
        return False
    _, categories = parse_hyperspin_xml(info.categories_xml)
    new_cats = [c for c in categories if c["name"].lower() != category_name.lower()]
    if len(new_cats) == len(categories):
        logger.warning("Categoria no encontrada: {}".format(category_name))
        return False
    return write_hyperspin_xml(info.categories_xml, "Categories", new_cats, sort=True)


def edit_category(
    info: "MainMenuInfo",
    category_name: str,
    new_values: dict,
) -> bool:
    """
    Edita los campos de una categoria existente en Categories.xml.

    Args:
        info:           MainMenuInfo
        category_name:  nombre de la categoria a editar
        new_values:     dict con los campos a actualizar (name, genre, etc.)

    Returns:
        True si exito
    """
    if not info.has_categories_xml:
        return False
    _, categories = parse_hyperspin_xml(info.categories_xml)
    found = False
    for cat in categories:
        if cat["name"].lower() == category_name.lower():
            cat.update(new_values)
            found = True
            break
    if not found:
        logger.warning("Categoria no encontrada para edicion: {}".format(category_name))
        return False
    return write_hyperspin_xml(info.categories_xml, "Categories", categories, sort=True)


def reorder_categories(info: "MainMenuInfo", ordered_names: list) -> bool:
    """
    Reordena las categorias en Categories.xml segun la lista proporcionada.
    Las categorias que no esten en ordered_names se anaden al final.

    Args:
        info:          MainMenuInfo
        ordered_names: lista de nombres en el orden deseado

    Returns:
        True si exito
    """
    if not info.has_categories_xml:
        return False
    _, categories = parse_hyperspin_xml(info.categories_xml)
    cat_dict  = {c["name"]: c for c in categories}
    ordered   = [cat_dict[n] for n in ordered_names if n in cat_dict]
    remaining = [c for c in categories if c["name"] not in ordered_names]
    return write_hyperspin_xml(info.categories_xml, "Categories", ordered + remaining, sort=False)


def sync_categories_with_all(info: "MainMenuInfo") -> dict:
    """
    Asegura coherencia entre All.xml y Categories.xml:
    detecta generos en All.xml que no tienen categoria y
    categorias huerfanas (sin sistemas en All.xml).

    Returns:
        dict con:
          "genres_without_category": list
          "orphan_categories":       list
          "ok":                      bool
    """
    if not info.has_all_xml:
        return {"error": "All.xml no encontrado"}
    _, all_systems = parse_hyperspin_xml(info.all_xml)
    genres_in_all  = {s.get("genre", "").strip() for s in all_systems if s.get("genre")}

    cats_names = set()
    if info.has_categories_xml:
        _, cats = parse_hyperspin_xml(info.categories_xml)
        cats_names = {c["name"] for c in cats}

    without_cat = sorted(genres_in_all - cats_names)
    orphans     = sorted(cats_names - genres_in_all)
    return {
        "genres_without_category": without_cat,
        "orphan_categories":       orphans,
        "ok":                      not without_cat and not orphans,
    }


def add_system_to_all_xml(
    info: "MainMenuInfo",
    system: dict,
    overwrite_if_exists: bool = False,
) -> bool:
    """
    Anade o actualiza un sistema en All.xml.

    Args:
        info:                MainMenuInfo
        system:              dict con campos del sistema (name, genre, etc.)
        overwrite_if_exists: si True, actualiza la entrada existente

    Returns:
        True si exito
    """
    systems = []
    if info.has_all_xml:
        _, systems = parse_hyperspin_xml(info.all_xml)

    idx = next(
        (i for i, s in enumerate(systems)
         if s["name"].lower() == system["name"].lower()), None)

    if idx is not None:
        if overwrite_if_exists:
            systems[idx] = system
        else:
            logger.info("Sistema ya existe en All.xml: {}".format(system["name"]))
            return True
    else:
        systems.append(system)

    return write_hyperspin_xml(info.all_xml, "All", systems)


def remove_system_from_all_xml(info: "MainMenuInfo", system_name: str) -> bool:
    """
    Elimina un sistema de All.xml por nombre.

    Returns:
        True si exito
    """
    if not info.has_all_xml:
        return False
    _, systems = parse_hyperspin_xml(info.all_xml)
    new_sys = [s for s in systems if s["name"].lower() != system_name.lower()]
    if len(new_sys) == len(systems):
        logger.warning("Sistema no encontrado en All.xml: {}".format(system_name))
        return False
    return write_hyperspin_xml(info.all_xml, "All", new_sys)


# =============================================================================
# 8. UTILIDADES DE BACKUP
# =============================================================================

def backup_main_menu_xmls(info: "MainMenuInfo", backup_dir: str = "") -> list:
    """
    Crea copias de seguridad con timestamp de todos los XMLs del Main Menu.

    Args:
        info:       MainMenuInfo
        backup_dir: directorio de backups (por defecto crea _backups/ junto a los XML)

    Returns:
        lista de rutas de backup creadas
    """
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_dir = os.path.join(info.hs_dir, HS_MAIN_MENU_DB)
    bk_dir = backup_dir or os.path.join(db_dir, "_backups")
    os.makedirs(bk_dir, exist_ok=True)

    backed_up = []
    for xml_path in [info.all_xml, info.categories_xml, info.main_menu_xml]:
        if os.path.isfile(xml_path):
            name, ext = os.path.splitext(os.path.basename(xml_path))
            dest = os.path.join(bk_dir, "{}_{}{}".format(name, ts, ext))
            try:
                shutil.copy2(xml_path, dest)
                backed_up.append(dest)
                logger.info("Backup: {}".format(dest))
            except Exception as e:
                logger.error("Error en backup de {}: {}".format(xml_path, e))
    return backed_up


# =============================================================================
# 9. PUNTO DE ENTRADA DE ALTO NIVEL
# =============================================================================

def full_mainmenu_setup(
    hs_dir: str,
    mmc_dir: str = "",
    overwrite: bool = False,
    progress_callback=None,
) -> dict:
    """
    Funcion de alto nivel que ejecuta el flujo completo de configuracion
    del Main Menu. Util para llamar desde la pestana de configuracion
    o al crear un sistema nuevo.

    Flujo:
        1. Detectar estado actual
        2. Si MMC instalado -> copiar media
        3. Crear/actualizar All.xml desde Main Menu.xml (si es necesario)
        4. Crear/actualizar Categories.xml con generos encontrados
        5. Crear filtros de genero
        6. Devolver informe

    Args:
        hs_dir:            directorio raiz de HyperSpin
        mmc_dir:           directorio raiz de MainMenuChanger (vacio = no usar)
        overwrite:         sobreescribir archivos existentes
        progress_callback: callable(step, total, message)

    Returns:
        dict con todos los resultados de cada paso
    """
    report = {}
    info   = detect_mainmenu(hs_dir, mmc_dir)
    report["info"] = info.summary()

    steps = []
    if mmc_dir:
        steps.append(("copy_mmc_media",       "Copiar media MMC"))
    if info.has_main_menu_xml and not info.has_all_xml:
        steps.append(("convert_to_all",       "Convertir a All.xml + Categories.xml"))
    steps.append(    ("create_genre_filters", "Crear filtros de genero"))

    total = len(steps)
    for i, (step_id, step_label) in enumerate(steps):
        if progress_callback:
            try:
                progress_callback(i + 1, total, step_label)
            except Exception:
                pass

        if step_id == "copy_mmc_media":
            res = copy_mmc_media_to_hyperspin(info, overwrite=overwrite)
            report["copy_mmc_media"] = res.summary()

        elif step_id == "convert_to_all":
            res = main_menu_xml_to_all_and_categories(info, overwrite=overwrite)
            report["convert_to_all"] = res.summary()

        elif step_id == "create_genre_filters":
            filter_results = create_all_genre_filters(info)
            ok = sum(1 for r in filter_results.values() if r.success)
            report["create_genre_filters"] = "{}/{} filtros: {}".format(
                ok, len(filter_results), ", ".join(filter_results.keys()))

    report["sync_check"] = sync_categories_with_all(info)
    return report
