from colorsys import hls_to_rgb

# RFC 7986 COLOR accepts CSS3 names, not arbitrary hexadecimal values.
_ICS_COLOR_PALETTE = {
    "black": (0, 0, 0),
    "silver": (192, 192, 192),
    "gray": (128, 128, 128),
    "white": (255, 255, 255),
    "maroon": (128, 0, 0),
    "red": (255, 0, 0),
    "purple": (128, 0, 128),
    "fuchsia": (255, 0, 255),
    "green": (0, 128, 0),
    "lime": (0, 255, 0),
    "olive": (128, 128, 0),
    "yellow": (255, 255, 0),
    "navy": (0, 0, 128),
    "blue": (0, 0, 255),
    "teal": (0, 128, 128),
    "aqua": (0, 255, 255),
}


def ics_color_name(color: str) -> str:
    """Approximate an RGB course color with a standards-compliant CSS3 name."""
    rgb = tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
    return min(
        _ICS_COLOR_PALETTE,
        key=lambda name: sum((value - target) ** 2 for value, target in zip(rgb, _ICS_COLOR_PALETTE[name])),
    )


def course_color(course: str, configured_color: str | None = None) -> str:
    if configured_color is not None:
        return configured_color

    key = course.strip() or "—"
    hash_value = 0
    for character in key:
        hash_value = (hash_value * 31 + ord(character)) & 0xFFFFFFFF
    hue = ((hash_value * 137.508) % 360.0) / 360.0
    mix = (hash_value >> 3) & 0xFF
    saturation = 0.45 + (mix % 4) * 0.08
    lightness = 0.78 + ((mix >> 2) % 5) * 0.03
    red, green, blue = hls_to_rgb(hue, lightness, saturation)
    return f"#{int(red * 255):02X}{int(green * 255):02X}{int(blue * 255):02X}"
