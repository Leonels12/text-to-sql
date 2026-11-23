"""The comparator decides what counts as correct, so it needs its own tests."""
from src.evaluate import results_match


def test_same_rows_same_order():
    assert results_match([(1, "a"), (2, "b")], [(1, "a"), (2, "b")], order_matters=True)


def test_order_ignored_when_it_does_not_matter():
    assert results_match([(1,), (2,)], [(2,), (1,)], order_matters=False)


def test_order_checked_when_it_matters():
    assert not results_match([(1,), (2,)], [(2,), (1,)], order_matters=True)


def test_floats_rounded_to_two_decimals():
    assert results_match([(5.651941747,)], [(5.652,)], order_matters=False)
    assert not results_match([(5.65,)], [(5.66,)], order_matters=False)


def test_missing_row_is_wrong():
    assert not results_match([(1,), (2,)], [(1,)], order_matters=False)


def test_duplicate_rows_count():
    # Counter, not set: a result with a row twice is different from once.
    assert not results_match([(1,), (1,)], [(1,)], order_matters=False)


def test_extra_column_is_wrong():
    assert not results_match([("Rock",)], [("Rock", 1297)], order_matters=False)
