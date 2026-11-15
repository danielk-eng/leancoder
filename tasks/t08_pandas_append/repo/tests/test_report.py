from sales.report import build_report, total_qty

ROWS = [{"name": " apple ", "qty": "3"}, {"name": "pear", "qty": 2}]


def test_rows_and_columns():
    df = build_report(ROWS)
    assert list(df.columns) == ["name", "qty"]
    assert len(df) == 2
    assert list(df["name"]) == ["Apple", "Pear"]


def test_total():
    assert total_qty(build_report(ROWS)) == 5


def test_empty():
    assert len(build_report([])) == 0
