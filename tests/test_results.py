"""Tests for the generic Result value type (NFR-1.1, TS-1)."""

import pytest

from agentic_dev_loop.results import Result


class TestResultOk:
    def test_ok_carries_value(self):
        r = Result.ok("done")
        assert r.is_ok()
        assert not r.is_err()
        assert r.value == "done"
        assert r.error is None

    def test_ok_none_value_is_valid(self):
        r = Result.ok(None)
        assert r.is_ok()
        assert r.value is None

    def test_unwrap_returns_value(self):
        assert Result.ok(42).unwrap() == 42

    def test_ok_results_are_equal(self):
        assert Result.ok("x") == Result.ok("x")

    def test_ok_matches_pattern(self):
        r = Result.ok("x")
        match r:
            case Result(value="x", error=None):
                pass
            case _:
                pytest.fail("ok Result did not match (value, None) pattern")


class TestResultErr:
    def test_err_carries_error(self):
        r = Result.err("no_verdict")
        assert r.is_err()
        assert not r.is_ok()
        assert r.error == "no_verdict"
        assert r.value is None

    def test_unwrap_raises_on_error(self):
        with pytest.raises(ValueError, match="no_verdict"):
            Result.err("no_verdict").unwrap()

    def test_err_results_are_equal(self):
        assert Result.err("x") == Result.err("x")

    def test_err_matches_pattern(self):
        r = Result.err("ambiguous")
        match r:
            case Result(value=None, error="ambiguous"):
                pass
            case _:
                pytest.fail("err Result did not match (None, error) pattern")
