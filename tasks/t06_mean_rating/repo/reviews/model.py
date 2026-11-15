"""Review data model."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Review:
    author: str
    stars: int
    text: str = ""

    def __post_init__(self):
        if not 1 <= self.stars <= 5:
            raise ValueError("stars must be 1..5")
