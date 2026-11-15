"""Catalog browsing helpers."""
from .models import Product


def paginate(items, page, per_page):
    """Return the items on a 1-based `page`."""
    start = page * per_page
    end = start + per_page
    return items[start:end]


def search(products, term):
    term = term.lower()
    return [p for p in products if term in p.name.lower()]


def sort_by_price(products, descending=False):
    return sorted(products, key=lambda p: p.price_cents, reverse=descending)


def by_tag(products, tag):
    return [p for p in products if p.has_tag(tag)]
