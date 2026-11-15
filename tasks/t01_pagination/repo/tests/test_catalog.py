from shop.catalog import paginate, search
from shop.models import Product


def test_first_page():
    assert paginate(list(range(1, 11)), 1, 3) == [1, 2, 3]


def test_last_partial_page():
    assert paginate(list(range(1, 11)), 4, 3) == [10]


def test_page_out_of_range_is_empty():
    assert paginate(list(range(1, 11)), 5, 3) == []


def test_search_is_case_insensitive():
    ps = [Product("a", "Red Mug", 500), Product("b", "Blue Plate", 900)]
    assert [p.sku for p in search(ps, "mug")] == ["a"]
