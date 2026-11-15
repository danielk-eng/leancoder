"""Leaderboard rendering."""


def top_players(scores, n):
    """Return [(name, score)] for the n best players, best first.

    Ties are broken alphabetically by name.
    """
    ranked = sorted(scores.items(), key=lambda kv: kv[1])
    return ranked[:n]


def render(rows):
    lines = []
    for i, (name, score) in enumerate(rows, start=1):
        lines.append(f"{i:>2}. {name:<10} {score:>5}")
    return "\n".join(lines)


def rank_of(scores, name):
    for i, (n, _) in enumerate(top_players(scores, len(scores)), start=1):
        if n == name:
            return i
    return None
