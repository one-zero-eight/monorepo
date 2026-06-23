from pypdf import PdfReader

from src.maps import maps_repo
from src.maps.pdf_export import A4_LONG, A4_SHORT, generate_all_maps_pdf, prepare_svg_for_pdf


def test_prepare_svg_for_pdf_keeps_map_layout():
    from src.maps.config import settings

    scene = next(s for s in maps_repo.get_all_scenes() if s.scene_id == "university-floor-1")
    map_svg = (settings.static_directory / scene.svg_file).read_text(encoding="utf-8")
    page = prepare_svg_for_pdf(scene, map_svg)

    assert scene.title in page
    assert 'id="title"' in page
    assert 'id="legend"' in page
    assert 'id="map-content"' in page
    if scene.pdf_export.orientation == "vertical":
        assert f'width="{A4_SHORT}"' in page
        assert f'height="{A4_LONG}"' in page
    else:
        assert f'width="{A4_LONG}"' in page
        assert f'height="{A4_SHORT}"' in page
    assert "preserveAspectRatio" not in page


def test_generate_all_maps_pdf_has_one_page_per_scene():
    from src.maps.config import settings

    scenes = maps_repo.get_all_scenes()
    pdf_path = generate_all_maps_pdf(settings.static_directory, scenes)
    assert len(PdfReader(str(pdf_path)).pages) == len(scenes)


def test_svg_legends_use_legend_group():
    from src.maps.config import settings

    for scene in maps_repo.get_all_scenes():
        svg = (settings.static_directory / scene.svg_file).read_text(encoding="utf-8")
        if scene.scene_id == "sport-complex":
            continue
        assert 'id="legend"' in svg, scene.scene_id


def test_map_svgs_have_title_group():
    from src.maps.config import settings

    for scene in maps_repo.get_all_scenes():
        svg = (settings.static_directory / scene.svg_file).read_text(encoding="utf-8")
        assert 'id="title"' in svg, scene.scene_id
        assert scene.title in svg, scene.scene_id


def test_map_svgs_have_no_export_overlay():
    from src.maps.config import settings

    for scene in maps_repo.get_all_scenes():
        svg = (settings.static_directory / scene.svg_file).read_text(encoding="utf-8")
        assert "export-overlay" not in svg, scene.scene_id
