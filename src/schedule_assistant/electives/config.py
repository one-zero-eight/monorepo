from pydantic import BaseModel


class Elective(BaseModel):
    """
    How it will be in innohassle event group name: spring26-bs2-ru-ввтус
    - semester alias: spring26
    - sheet name: bs2-ru
    - elective alias: ввтус
    """

    alias: str
    "Alias for elective, how it will be as part in innohassle event group name. Most probably same as short name"
    short_name: str
    "Short name of elective, exactly how it is written in the schedule"
    name: str | None = None
    "Name of elective"
    instructor: str | None = None
    "Instructor of elective"
    elective_type: str | None = None
    "Type of elective"


class Target(BaseModel):
    sheet_name: str


class Tag(BaseModel):
    alias: str
    type: str
    name: str


class ElectivesParserConfig(BaseModel):
    targets: list[Target]

    semester_tag: Tag
    spreadsheet_id: str
    electives: list[Elective]
