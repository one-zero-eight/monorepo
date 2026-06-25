from pydantic import BaseModel, Field

from src.common_config import BaseSchema


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


class PdfExport(BaseSchema):
    orientation: str = "horizontal"
    "Orientation of the PDF page (horizontal or vertical)"


class Scene(BaseSchema):
    scene_id: str
    "ID of the scene"
    title: str
    "Title of the scene"
    svg_file: str
    "Path to the SVG file in /static"
    pdf_export: PdfExport = Field(default_factory=PdfExport)
    "PDF export layout settings"
    areas: list[Area] = Field(default_factory=list)
    "Areas of the scene"


class SearchResult(BaseModel):
    scene_id: str
    "Id of corresponding scene"
    area: Area
    "Corresponding area object"
    area_index: int
    "Index of area in `scene.areas`"
