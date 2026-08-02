import io
import re
from pathlib import Path

import cairosvg
from pypdf import PdfReader, PdfWriter

from src.logging_ import logger

from .schemas import Scene

A4_SHORT = 595.27  # 210mm in points
A4_LONG = 841.89  # 297mm in points


def fix_svg_namespaces(svg_content: str) -> str:
    """Inject missing common namespaces."""
    namespaces = {
        "xmlns:xlink": "http://www.w3.org/1999/xlink",
        "xmlns:inkscape": "http://www.inkscape.org/namespaces/inkscape",
        "xmlns:sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    }

    svg_tag_match = re.search(r"<svg[^>]*>", svg_content, re.IGNORECASE)
    if not svg_tag_match:
        return svg_content

    svg_tag = svg_tag_match.group(0)
    new_svg_tag = svg_tag
    for prefix, url in namespaces.items():
        if prefix not in svg_tag:
            if new_svg_tag.endswith("/>"):
                new_svg_tag = new_svg_tag[:-2].strip() + f' {prefix}="{url}"/>'
            else:
                new_svg_tag = new_svg_tag[:-1].strip() + f' {prefix}="{url}">'

    return svg_content.replace(svg_tag, new_svg_tag, 1)


def _set_root_page_size(svg_content: str, page_w: float, page_h: float) -> str:
    svg_tag_match = re.search(r"<svg[^>]*>", svg_content, re.IGNORECASE)
    if not svg_tag_match:
        raise ValueError("SVG has no root element")

    svg_tag = svg_tag_match.group(0)
    if re.search(r'\swidth="', svg_tag):
        new_tag = re.sub(r'\swidth="[^"]*"', f' width="{page_w}"', svg_tag, count=1)
    else:
        new_tag = svg_tag[:-1].rstrip() + f' width="{page_w}">'

    if re.search(r'\sheight="', new_tag):
        new_tag = re.sub(r'\sheight="[^"]*"', f' height="{page_h}"', new_tag, count=1)
    else:
        new_tag = new_tag[:-1].rstrip() + f' height="{page_h}">'

    return svg_content.replace(svg_tag, new_tag, 1)


def _ensure_white_background(svg_content: str) -> str:
    if re.search(r'<rect[^>]+width="100%"[^>]+height="100%"[^>]+fill="white"', svg_content):
        return svg_content
    return re.sub(
        r"(<svg[^>]*>)",
        r'\1<rect width="100%" height="100%" fill="white"/>',
        svg_content,
        count=1,
        flags=re.IGNORECASE,
    )


def _page_size(scene: Scene) -> tuple[float, float]:
    vertical = scene.pdf_export.orientation == "vertical"
    if vertical:
        return A4_SHORT, A4_LONG
    return A4_LONG, A4_SHORT


def prepare_svg_for_pdf(scene: Scene, map_svg: str) -> str:
    """Scale the map SVG to an A4 page without changing its layout."""
    page_w, page_h = _page_size(scene)
    content = fix_svg_namespaces(map_svg)
    content = _set_root_page_size(content, page_w, page_h)
    return _ensure_white_background(content)


def generate_all_maps_pdf(static_dir: Path, scenes: list[Scene]) -> Path:
    output_path = static_dir / "all_maps.pdf"
    writer = PdfWriter()
    rendered = 0

    for scene in scenes:
        svg_path = static_dir / scene.svg_file
        if not svg_path.exists():
            logger.warning("Skipping map SVG for %s: file not found at %s", scene.scene_id, svg_path)
            continue

        try:
            raw_content = svg_path.read_text(encoding="utf-8")
            page_svg = prepare_svg_for_pdf(scene, raw_content)
            pdf_data = cairosvg.svg2pdf(bytestring=page_svg.encode("utf-8"))
            writer.add_page(PdfReader(io.BytesIO(pdf_data)).pages[0])
            rendered += 1
        except Exception:  # noqa: BLE001
            logger.exception("Failed to process map SVG %s", svg_path)
            continue

    if rendered == 0:
        raise RuntimeError("No map SVGs could be rendered to PDF")

    with open(output_path, "wb") as f:
        writer.write(f)

    if rendered != len(scenes):
        logger.warning("Rendered %s of %s map PDF pages", rendered, len(scenes))

    return output_path
