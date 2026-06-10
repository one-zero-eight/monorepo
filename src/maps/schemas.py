from pydantic import BaseModel, Field, model_validator

from src.common_config import BaseSchema


class LegendEntry(BaseSchema):
    legend_id: str
    "ID of the legend"
    color: str | None = None
    "Color of the legend"
    emoji: str | None = None
    "Emoji for the legend"
    legend: str | None = None
    "Description of the legend (may contain multiple lines)"

    @model_validator(mode="after")
    def set_legend_as_legend_id(self):
        if self.legend is None:
            self.legend = self.legend_id
        return self


class Area(BaseSchema):
    svg_polygon_id: str | None = None
    "ID of the polygon in the SVG"
    title: str | None = None
    "Title of the area"
    ru_title: str | None = None
    "Title in Russian"
    legend_id: str | None = None
    "ID of the legend (if any)"
    description: str | None = None
    "Description of the area"
    people: list[str] = Field(default_factory=list)
    "List of people for this area"
    prioritized: bool = False
    "Priority for multi-floor areas"
    room_booking_id: str | None = None
    "ID of the room in Room Booking API (if any)"
    scene_pointer: str | None = None
    "Maps scene name with which the area is associated"


class Scene(BaseSchema):
    scene_id: str
    "ID of the scene"
    title: str
    "Title of the scene"
    svg_file: str
    "Path to the SVG file in /static"
    orientation: str = "horizontal"
    "Orientation of the scene (horizontal or vertical)"
    map_x: float | None = None
    "X coordinate of the map"
    map_y: float | None = None
    "Y coordinate of the map"
    title_x: float | None = None
    "X coordinate of the title"
    title_y: float | None = None
    "Y coordinate of the title"
    title_font_size: int = 20
    "Font size of the title"
    title_font_family: str = "sans-serif"
    "Font family of the title"
    legend_emoji_font_family: str = "'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', 'Twemoji Mozilla', 'EmojiOne Color', 'Symbola', 'Android Emoji', sans-serif"
    "Font family for emojis in the legend"
    legend_x: float | None = None
    "X coordinate of the legend"
    legend_y: float | None = None
    "Y coordinate of the legend"
    legend_font_size: int = 10
    "Font size of the legend"
    legend_item_height: int = 15
    "Height of each legend item"
    legend_icon_spacing: int = 25
    "Spacing between the icon (color/emoji) and the text"
    legend_width: int = 200
    "Width of the legend"
    scale: float | None = None
    "Scale of the map"
    legend: list[LegendEntry] = Field(default_factory=list)
    "Legend of the scene"
    areas: list[Area] = Field(default_factory=list)
    "Areas of the scene"


class SearchResult(BaseModel):
    scene_id: str
    "Id of corresponding scene"
    area: Area
    "Corresponding area object"
    area_index: int
    "Index of area in `scene.areas`"
