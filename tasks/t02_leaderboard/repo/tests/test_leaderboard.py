from game.leaderboard import top_players, rank_of

SCORES = {"zed": 30, "amy": 50, "bob": 30, "cat": 10}


def test_best_first():
    assert top_players(SCORES, 2) == [("amy", 50), ("bob", 30)]


def test_ties_alphabetical():
    assert [n for n, _ in top_players(SCORES, 3)] == ["amy", "bob", "zed"]


def test_rank_of():
    assert rank_of(SCORES, "cat") == 4
