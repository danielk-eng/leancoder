"""Domain models for the shop."""
from dataclasses import dataclass, field


@dataclass
class Product:
    sku: str
    name: str
    price_cents: int
    tags: list = field(default_factory=list)

    def price(self) -> float:
        return self.price_cents / 100

    def has_tag(self, tag: str) -> bool:
        return tag.lower() in (t.lower() for t in self.tags)


@dataclass
class Order:
    order_id: int
    lines: list = field(default_factory=list)

    def total_cents(self) -> int:
        return sum(p.price_cents * qty for p, qty in self.lines)
