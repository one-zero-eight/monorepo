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


class GeoControlPoint(BaseSchema):
    label: str
    "Human-readable note, e.g. 'garage entrance, NE corner'"
    lat: float
    "Real-world latitude (WGS84)"
    lon: float
    "Real-world longitude (WGS84)"
    x: float
    "Position of the same spot in the SVG user-space (viewBox units)"
    y: float
    "Position of the same spot in the SVG user-space (viewBox units)"


class GeoReference(BaseSchema):
    control_points: list[GeoControlPoint] = Field(default_factory=list)
    "At least 2 spread-out, non-collinear points to fit a 2D affine transform; fewer means no location dot"
    accuracy_threshold_m: float = 150
    "Hide the location dot when the browser's reported accuracy is worse than this (meters)"


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
    geo_reference: GeoReference | None = None
    "GPS-to-SVG calibration for the 'you are here' dot; null if the scene isn't georeferenced"


class SearchResult(BaseModel):
    scene_id: str
    "Id of corresponding scene"
    area: Area
    "Corresponding area object"
    area_index: int
    "Index of area in `scene.areas`"
