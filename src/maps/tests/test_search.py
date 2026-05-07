from unittest import TestCase

import pytest

from ..repository import scene_repository

# [
#   (query, [(scene-id, svg-polygon-id), ...]),
#   ...
# ]
cases = [
    # Exact match (simple case, without postfixes
    ("305", [("university-floor-3", "305")]),
    ("404", [("university-floor-4", "404")]),
    ("3.2", [("university-floor-3", "3.2"), ("sport-complex", "3.2")]),
    # Postfixes (a, b, c)
    ("504a", [("university-floor-5", "504a")]),
    ("309a", [("university-floor-3", "309a")]),
    ("411", [("university-floor-4", "411"), ("university-floor-4", "411a")]),  # exact match + postfix
    ("309", [("university-floor-3", "309"), ("university-floor-3", "309a")]),  # exact match + postfix
    ("450", [("university-floor-4", "450"), ("university-floor-4", "450a")]),  # exact match + postfix
    ("504", [("university-floor-5", "504a"), ("university-floor-5", "504b"), ("university-floor-5", "504c")]),
    # 105 and 105a case is tricky, we have 105 on Floor 1 and 105a on Floor -1
    ("105", [("university-floor-1", "105")]),
    ("105a", [("university-floor-0", "105a")]),
    #
    (("Canteen", "Столовая"), [("university-floor-1", "canteen")]),
    (("Reading Hall", "Читалка"), [("university-floor-1", "reading-hall-1")]),
    (("Green Stairs", "Зелёные Ступеньки"), [("university-floor-3", "green-stairs")]),
    (("Garage", "Гараж"), [("university-floor-0", "garage-0")]),  # Garage should be Floor -1
    # People
    (("Reza", "Реза"), [("university-floor-5", "506")]),
    (("Frolov", "Фролов"), [("university-floor-4", "464")]),
    (("Konyukhov", "Конюхов"), [("university-floor-4", "464")]),
    (("Maslovskaya", "Масловская"), [("university-floor-4", "465")]),
    (("Khan", "Хан"), [("university-floor-4", "466")]),
    (("Burmyakov", "Бурмяков"), [("university-floor-4", "467")]),
    (("Zlatanov", "Златанов"), [("university-floor-4", "471")]),
    (("Succi", "Суччи"), [("university-floor-4", "474")]),
    (("Ciancarini", "Чанкарини"), [("university-floor-4", "474")]),
    (("Ivanov", "Иванов"), [("university-floor-4", "475")]),
    (("Leplat", "Леплат"), [("university-floor-4", "401")]),
    (("Maloletov", "Малолетов"), [("university-floor-4", "401")]),
    (("Zouev", "Зуев"), [("university-floor-4", "404")]),
    (("Saduov", "Садуов"), [("university-floor-4", "405")]),
    (("Mazzara", "Маццара"), [("university-floor-4", "407")]),
    (("Gelvanovsky", "Гелвановский"), [("university-floor-4", "405")]),
    (("Lukmanov", "Лукманов"), [("university-floor-4", "410")]),
    (("Kholodov", "Холодов"), [("university-floor-4", "411")]),
    (("Mayorga", "Майорга"), [("university-floor-4", "411a")]),
]


@pytest.mark.parametrize("inputs, desired", cases, ids=[str(x) for x, _ in cases])
def test_location_parser(inputs, desired: list[tuple[str, str]]):
    # desired - list of svg_polygon_id
    if isinstance(inputs, str):
        inputs = (inputs,)
    _ = TestCase()
    _.maxDiff = None

    for input_ in inputs:
        results = scene_repository.search(input_)
        to_compare = {(result.scene_id, result.area.svg_polygon_id) for result in results}
        _.assertSetEqual(set(desired), to_compare)
