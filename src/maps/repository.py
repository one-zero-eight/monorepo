from pathlib import Path
from re import escape, search

import yaml
from rapidfuzz import fuzz, utils

from src.logging_ import logger

from .schemas import Area, Scene, SearchResult

scenes_path = Path(__file__).resolve().parent / "scenes.yaml"


def load_scenes(path: Path) -> list[Scene]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return [Scene.model_validate(scene) for scene in data.get("scenes", [])]


scenes = load_scenes(scenes_path)


def prepare_for_search(area: Area) -> str | None:
    fields = [area.title, area.description]
    filtered_fields = [field for field in fields if field is not None]

    if not filtered_fields:
        return None

    return " ".join(filtered_fields)


class SceneRepository:
    def get_all(self) -> list[Scene]:
        return scenes

    def search(self, query: str):
        all_scenes = self.get_all()
        result = []

        query_clean = query.lower().strip()

        if "[sc]" in query_clean or "[ск]" in query_clean:
            all_scenes = [scene for scene in all_scenes if scene.scene_id == "sport-complex"]
            if "floor" in query_clean:
                ground_floor = list()
                for index, area in enumerate(all_scenes[0].areas):
                    if f"floor-{''.join(filter(str.isdigit, query_clean))}" == area.svg_polygon_id:
                        return [SearchResult(scene_id="sport-complex", area_index=index, area=area)]
                    if area.svg_polygon_id == "floor-0":
                        ground_floor = index, area
                return [SearchResult(scene_id="sport-complex", area_index=ground_floor[0], area=ground_floor[1])]

        if "муз" in query_clean or "music" in query_clean:
            for scene in all_scenes:
                for index, area in enumerate(scene.areas):
                    if area.svg_polygon_id == "music-room":
                        return [SearchResult(scene_id=scene.scene_id, area_index=index, area=area)]

        for scene in all_scenes:
            logger.debug(scene.areas)

            for index, area in enumerate(scene.areas):
                for title in filter(None, (area.title, area.ru_title)):
                    if search(rf"\b{escape(query_clean)}", title.lower().strip()):
                        if area.prioritized:
                            return [SearchResult(scene_id=scene.scene_id, area_index=index, area=area)]

                        result.append(SearchResult(scene_id=scene.scene_id, area_index=index, area=area))

        if result:
            return result

        people_results: list[tuple[float, Scene, int]] = []
        for scene in all_scenes:
            for index, area in enumerate(scene.areas):
                for person in area.people:
                    score = fuzz.partial_ratio(query_clean, person.lower())
                    people_results.append((score, scene, index))
        if people_results:
            score, scene, index = max(people_results, key=lambda x: x[0])
            if score > 70:
                return [SearchResult(scene_id=scene.scene_id, area_index=index, area=scene.areas[index])]

        for scene in all_scenes:
            logger.debug(scene.areas)
            concatenated_fields = [prepare_for_search(area) for area in scene.areas]

            if not concatenated_fields:
                continue

            matches = [fuzz.token_ratio(query, doc, processor=utils.default_process) for doc in concatenated_fields]
            logger.debug(matches)

            for index, score in enumerate(matches):
                if score >= 60:
                    print(scene.areas[index].title)
                    result.append(SearchResult(scene_id=scene.scene_id, area_index=index, area=scene.areas[index]))

        return result


scene_repository: SceneRepository = SceneRepository()
