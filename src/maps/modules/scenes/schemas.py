from pydantic import BaseModel

from src.config_schema import Area


class SearchResult(BaseModel):
    scene_id: str
    "Id of corresponding scene"
    area: Area
    "Corresponding area object"
    area_index: int
    "Index of area in `scene.areas`"
