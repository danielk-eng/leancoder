from reviews.stats import mean_rating, histogram, share_positive


def test_fraction():
    assert mean_rating([1, 2]) == 1.5


def test_integer_mean():
    assert mean_rating([4, 4, 4]) == 4


def test_empty_is_zero():
    assert mean_rating([]) == 0.0


def test_histogram():
    assert histogram([5, 5, 1])[5] == 2


def test_share_positive():
    assert share_positive([5, 4, 1, 1]) == 0.5
