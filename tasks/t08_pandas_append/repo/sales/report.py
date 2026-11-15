"""Build a sales report table."""
import pandas as pd

from .clean import normalize


def add_row(df, row):
    return df.append(normalize(row), ignore_index=True)


def build_report(rows):
    df = pd.DataFrame(columns=["name", "qty"])
    for row in rows:
        df = add_row(df, row)
    return df


def total_qty(df) -> int:
    return int(df["qty"].sum())
