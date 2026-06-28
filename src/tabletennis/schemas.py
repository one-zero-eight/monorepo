from src.common_config import BaseSchema


class Player(BaseSchema):
    id: str
    name: str
    rating: int = 1000


class Game(BaseSchema):
    id: str
    player1_id: str
    player2_id: str
    score_player1: int
    score_player2: int
