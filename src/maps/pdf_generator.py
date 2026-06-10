import html
import io
import re

import cairosvg
from pypdf import PdfReader, PdfWriter, Transformation

from src.logging_ import logger

from . import maps_repo
from .config import settings

A4_SHORT = 595.27  # 210mm in points
A4_LONG = 841.89  # 297mm in points
MARGIN = 20


def fix_svg_namespaces(svg_content: str) -> str:
    """Inject missing common namespaces, expand viewBox, and stabilize text elements."""
    namespaces = {
        "xmlns:xlink": "http://www.w3.org/1999/xlink",
        "xmlns:inkscape": "http://www.inkscape.org/namespaces/inkscape",
        "xmlns:sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    }

    # 1. Inject namespaces and expand viewBox
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

    viewbox_match = re.search(r'viewBox="([^"]+)"', new_svg_tag)
    if viewbox_match:
        try:
            vx, vy, vw, vh = map(float, viewbox_match.group(1).split())
            margin = 200
            new_viewbox = f"{vx - margin} {vy - margin} {vw + 2 * margin} {vh + 2 * margin}"
            new_svg_tag = new_svg_tag.replace(viewbox_match.group(0), f'viewBox="{new_viewbox}"')
        except ValueError:
            pass

    svg_content = svg_content.replace(svg_tag, new_svg_tag, 1)

    # 2. Fix text-anchor: move from style to attribute
    def clean_tag(match):
        tag_name = match.group(1)
        attrs = match.group(2)
        style_match = re.search(r'style="([^"]*)"', attrs)
        if style_match:
            style = style_match.group(1)
            anchor_match = re.search(r'text-anchor\s*:\s*([^;"]+)', style)
            new_style = re.sub(r'(text-anchor|text-align)\s*:\s*[^;"]+;?', "", style).strip()
            attrs = attrs.replace(f'style="{style}"', f'style="{new_style}"')
            if anchor_match and "text-anchor=" not in attrs:
                attrs += f' text-anchor="{anchor_match.group(1).strip()}"'
        return f"<{tag_name} {attrs.strip()}>"

    svg_content = re.sub(r"<(text|tspan)\s+([^>]+)>", clean_tag, svg_content)

    # 3. Surgical Coordinate Deduplication and Conflict Resolution
    def process_text_block(match):
        attrs = match.group(1)
        content = match.group(2)

        tx = re.search(r'x="([^"]+)"', attrs)
        ty = re.search(r'y="([^"]+)"', attrs)
        parent_anchor = re.search(r'text-anchor="([^"]+)"', attrs)

        def process_tspan(t_match):
            t_attrs = t_match.group(1)
            t_inner = t_match.group(2)
            if tx and ty:
                # Remove tspan x/y only if BOTH match parent exactly (to avoid double offset)
                sx = re.search(r'x="([^"]+)"', t_attrs)
                sy = re.search(r'y="([^"]+)"', t_attrs)
                if sx and sx.group(1) == tx.group(1) and sy and sy.group(1) == ty.group(1):
                    # Use re.sub to remove only full attribute matches
                    t_attrs = re.sub(f'x="{re.escape(tx.group(1))}"', "", t_attrs)
                    t_attrs = re.sub(f'y="{re.escape(ty.group(1))}"', "", t_attrs)

            # If tspan anchor matches parent, remove it from tspan
            if parent_anchor:
                t_attrs = re.sub(f'text-anchor="{re.escape(parent_anchor.group(1))}"', "", t_attrs)

            return f"<tspan {t_attrs.strip()}>{t_inner}</tspan>"

        new_content = re.sub(r"<tspan\s+([^>]+)>(.*?)</tspan>", process_tspan, content, flags=re.DOTALL)
        return f"<text {attrs.strip()}>{new_content}</text>"

    svg_content = re.sub(r"<text\s+([^>]+)>(.*?)</text>", process_text_block, svg_content, flags=re.DOTALL)

    return svg_content


def generate_all_maps_pdf():
    scenes = maps_repo.get_all_scenes()
    static_dir = settings.static_directory
    output_path = static_dir / "all_maps.pdf"

    writer = PdfWriter()

    for scene in scenes:
        svg_path = static_dir / scene.svg_file
        if not svg_path.exists():
            continue

        try:
            with open(svg_path, encoding="utf-8") as f:
                content = f.read()

            fixed_content = fix_svg_namespaces(content)

            # 1. Get original dimensions
            temp_pdf_data = cairosvg.svg2pdf(bytestring=fixed_content.encode("utf-8"))
            temp_reader = PdfReader(io.BytesIO(temp_pdf_data))
            orig_page = temp_reader.pages[0]
            orig_w = float(orig_page.mediabox.width)
            orig_h = float(orig_page.mediabox.height)

            # 2. Determine Orientation and Page Dimensions
            is_vertical = scene.orientation == "vertical"
            p_width = A4_SHORT if is_vertical else A4_LONG
            p_height = A4_LONG if is_vertical else A4_SHORT

            title_font_size = scene.title_font_size
            title_font_family = scene.title_font_family
            legend_font_size = scene.legend_font_size
            legend_font_size_small = int(legend_font_size * 0.8)
            legend_item_height = scene.legend_item_height
            spacing = 10

            legend_height = len(scene.legend) * legend_item_height
            legend_width = scene.legend_width if scene.legend else 0

            # Default logic for fallback
            title_top_margin = 15 if scene.scene_id in ("sport-complex", "campus") else MARGIN

            if is_vertical:
                available_h = (
                    p_height
                    - MARGIN
                    - title_top_margin
                    - title_font_size
                    - spacing
                    - (legend_height + spacing if legend_height > 0 else 0)
                )
                available_w = p_width - 2 * MARGIN
                auto_scale = min(available_w / orig_w, available_h / orig_h)
                scale = scene.scale if scene.scale is not None else auto_scale
                new_w = orig_w * scale
                new_h = orig_h * scale

                def_map_x = (p_width - new_w) / 2
                def_map_y = title_top_margin + title_font_size + spacing + (available_h - new_h) / 2
                def_title_x = p_width / 2
                def_title_y = title_top_margin
                def_title_anchor = "middle"
                def_legend_x = (p_width - legend_width) / 2 if legend_width else 0
                def_legend_y = p_height - MARGIN - legend_height
            else:
                available_h = p_height - MARGIN - title_top_margin - title_font_size - spacing
                available_w = p_width - 2 * MARGIN - (legend_width + spacing if legend_width > 0 else 0)
                auto_scale = min(available_w / orig_w, available_h / orig_h)
                scale = scene.scale if scene.scale is not None else auto_scale
                new_w = orig_w * scale
                new_h = orig_h * scale

                def_map_x = MARGIN + (available_w - new_w) / 2
                def_map_y = title_top_margin + title_font_size + spacing + (available_h - new_h) / 2
                def_title_x = MARGIN
                def_title_y = title_top_margin
                def_title_anchor = "start"
                def_legend_x = MARGIN + available_w + spacing
                def_legend_y = def_map_y + 5

            # Use coordinates from YAML if provided
            map_x = scene.map_x if scene.map_x is not None else def_map_x
            map_y = scene.map_y if scene.map_y is not None else def_map_y
            title_x = scene.title_x if scene.title_x is not None else def_title_x
            title_y = scene.title_y if scene.title_y is not None else def_title_y
            legend_x = scene.legend_x if scene.legend_x is not None else def_legend_x
            legend_y = scene.legend_y if scene.legend_y is not None else def_legend_y
            title_anchor = def_title_anchor if scene.title_x is None else "start"

            # 3. Create Overlay (Title and Legend)
            legend_svg = ""
            if scene.legend:
                items_svg = ""
                for i, entry in enumerate(scene.legend):
                    y_offset = i * legend_item_height
                    # Center everything vertically in the legend_item_height
                    middle_y = legend_item_height / 2

                    if entry.emoji or entry.color:
                        # Icon/Emoji part
                        if entry.emoji:
                            # Emojis usually look better slightly larger than text
                            # We use a dedicated font family for emojis to avoid "tofu" boxes
                            # discretionary-ligatures and geometricPrecision help with ZWJ sequences
                            emoji_font = scene.legend_emoji_font_family
                            icon_html = f'<text x="0" y="{middle_y}" style="font-family: {emoji_font}; font-size: {legend_font_size + 2}px; font-variant-ligatures: discretionary-ligatures; text-rendering: optimizeLegibility; shape-rendering: geometricPrecision;" dominant-baseline="central" xml:space="preserve">{html.escape(entry.emoji)}</text>'
                        else:
                            rect_size = 10
                            rect_y = middle_y - rect_size / 2
                            icon_html = f'<rect x="0" y="{rect_y}" width="{rect_size}" height="{rect_size}" fill="{html.escape(entry.color or "black")}" stroke="black" stroke-width="0.5" />'

                        items_svg += f"""
                            <g transform="translate(0, {y_offset})">
                                {icon_html}
                                <text x="{scene.legend_icon_spacing}" y="{middle_y}" font-family="{title_font_family}" font-size="{legend_font_size}" fill="black" dominant-baseline="central">{html.escape(entry.legend_id)}</text>
                            </g>
                        """
                    else:
                        items_svg += f"""
                            <g transform="translate(0, {y_offset})">
                                <text x="0" y="{middle_y}" font-family="{title_font_family}" font-size="{legend_font_size_small}" fill="gray" dominant-baseline="central">{html.escape(entry.legend_id)}</text>
                            </g>
                        """
                legend_svg = f'<g transform="translate({legend_x}, {legend_y})">{items_svg}</g>'

            # Massive buffer to eliminate clipping forever
            # Coordinate (0,0) in SVG will be (0,0) on A4 page.
            buffer = 500
            overlay_svg = f"""
<svg width="{p_width + 2 * buffer}" height="{p_height + 2 * buffer}" viewBox="-{buffer} -{buffer} {p_width + 2 * buffer} {p_height + 2 * buffer}" xmlns="http://www.w3.org/2000/svg">
    <text x="{title_x}" y="{title_y}" font-family="{title_font_family}" font-size="{title_font_size}" font-weight="bold" fill="black" text-anchor="{title_anchor}" dominant-baseline="text-before-edge">{html.escape(scene.title)}</text>
    {legend_svg}
</svg>
"""
            overlay_pdf_data = cairosvg.svg2pdf(bytestring=overlay_svg.encode("utf-8"))
            overlay_page = PdfReader(io.BytesIO(overlay_pdf_data)).pages[0]

            # 4. Create base white page
            base_white_svg = f'<svg width="{p_width}" height="{p_height}" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="white" /></svg>'
            base_pdf_data = cairosvg.svg2pdf(bytestring=base_white_svg.encode("utf-8"))
            base_page = PdfReader(io.BytesIO(base_pdf_data)).pages[0]

            # 5. Combine everything
            new_page = writer.add_blank_page(width=p_width, height=p_height)
            new_page.merge_page(base_page)

            # Map FIRST
            tx = map_x
            ty = p_height - map_y - orig_h * scale
            transformation = Transformation().scale(scale, scale).translate(tx, ty)

            map_pdf_data = cairosvg.svg2pdf(bytestring=fixed_content.encode("utf-8"))
            map_page = PdfReader(io.BytesIO(map_pdf_data)).pages[0]

            new_page.merge_transformed_page(map_page, transformation)

            # Overlay SECOND
            # Merge with offset to align our virtual (0,0) with PDF (0,0)
            # The overlay_page dimensions are (p_width+2*buffer, p_height+2*buffer)
            # Its content starts at -buffer.
            new_page.merge_translated_page(overlay_page, -buffer, -buffer)

        except Exception:
            logger.exception("Failed to process map SVG %s", svg_path)
            continue

    with open(output_path, "wb") as f:
        writer.write(f)

    return output_path
