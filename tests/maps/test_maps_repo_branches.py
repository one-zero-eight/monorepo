from src.maps import maps_repo
from src.maps.schemas import Area, Scene


def _scene(scene_id: str, areas: list[Area]) -> Scene:
    return Scene(scene_id=scene_id, title=scene_id, svg_file=f"{scene_id}.svg", areas=areas)


def test_prepare_for_search_branches():
    assert maps_repo.prepare_for_search(Area()) is None
    assert maps_repo.prepare_for_search(Area(title="A", description="B")) == "A B"


def test_search_sport_complex_floor_exact_and_fallback(monkeypatch):
    sport_complex = _scene(
        "sport-complex",
        [
            Area(svg_polygon_id="floor-0", title="Ground"),
            Area(svg_polygon_id="floor-2", title="Second"),
        ],
    )
    monkeypatch.setattr(maps_repo, "get_all_scenes", lambda: [sport_complex])

    exact = maps_repo.search_areas("[sc] floor 2")
    assert len(exact) == 1
    assert exact[0].scene_id == "sport-complex"
    assert exact[0].area.svg_polygon_id == "floor-2"

    fallback = maps_repo.search_areas("[sc] floor 9")
    assert len(fallback) == 1
    assert fallback[0].scene_id == "sport-complex"
    assert fallback[0].area.svg_polygon_id == "floor-0"


def test_search_music_branch(monkeypatch):
    sport_complex = _scene(
        "sport-complex",
        [
            Area(svg_polygon_id="x", title="Other"),
            Area(svg_polygon_id="music-room", title="Music room"),
        ],
    )
    monkeypatch.setattr(maps_repo, "get_all_scenes", lambda: [sport_complex])

    result = maps_repo.search_areas("music")
    assert len(result) == 1
    assert result[0].area.svg_polygon_id == "music-room"


def test_search_fuzzy_doc_fallback(monkeypatch):
    scene = _scene(
        "test-scene",
        [
            Area(svg_polygon_id="a1", title="Alpha room", description="quiet study"),
            Area(svg_polygon_id="a2", title="Beta room", description="sports"),
        ],
    )
    monkeypatch.setattr(maps_repo, "get_all_scenes", lambda: [scene])
    monkeypatch.setattr(maps_repo.fuzz, "partial_ratio", lambda *_: 0)
    monkeypatch.setattr(maps_repo.fuzz, "token_ratio", lambda q, d: 70 if "Alpha" in d else 10)

    result = maps_repo.search_areas("unmatched query")
    assert len(result) == 1
    assert result[0].scene_id == "test-scene"
    assert result[0].area.svg_polygon_id == "a1"
