from collections import defaultdict
from pathlib import Path

import yaml

from src.room_booking.config import settings
from src.room_booking.config_schema import AccessToRoom, Room

rooms_path = Path(__file__).resolve().parents[2] / "rooms.yaml"


def load_rooms(path: Path) -> list[Room]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [Room.model_validate(room) for room in data.get("rooms", [])]


rooms = load_rooms(rooms_path)


class RoomsRepository:
    rooms: list[Room]
    room_by_id: dict[str, Room]
    room_by_email: dict[str, Room]
    access_lists: dict[str, list[AccessToRoom]]
    email_x_access_list: dict[str, dict[str, AccessToRoom]]
    "{user email x {room_id: AccessToRoom}}"

    def __init__(self, rooms: list[Room], access_lists: dict[str, list[AccessToRoom]]):
        self.rooms = rooms
        self.room_by_id = {room.id: room for room in self.rooms}
        self.room_by_email = {room.resource_email: room for room in self.rooms}
        self.access_lists = access_lists
        self.email_x_access_list = defaultdict(dict)

        for room_id, access_list in access_lists.items():
            for access_to_room in access_list:
                self.email_x_access_list[access_to_room.email][room_id] = access_to_room

        self.validate_access_lists()

    def validate_access_lists(self):
        existing_room_ids = {room.id for room in self.rooms}
        for room_id in self.access_lists:
            if room_id not in existing_room_ids:
                raise ValueError(f"Room {room_id} not found in rooms")

    def get_all(self, include_red: bool = False) -> list[Room]:
        return [room for room in self.rooms if room.access_level != "red" or include_red]

    def get_by_id(self, room_id: str) -> Room | None:
        return self.room_by_id.get(room_id)

    def get_by_ids(self, room_ids: list[str]) -> list[Room | None]:
        return [self.get_by_id(room_id) for room_id in room_ids]

    def get_by_email(self, email: str) -> Room | None:
        return self.room_by_email.get(email)

    def get_access_list_for_user(self, user_email: str) -> dict[str, AccessToRoom]:
        return self.email_x_access_list.get(user_email, {})

    def get_access_list_for_room(self, room_id: str) -> list[AccessToRoom]:
        return self.access_lists.get(room_id, [])

    def user_has_access_to_room(self, user_email: str, room_id: str) -> bool:
        return room_id in self.email_x_access_list.get(user_email, {})


room_repository: RoomsRepository = RoomsRepository(rooms, settings.access_lists)
