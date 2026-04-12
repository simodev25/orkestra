"""Tests for app.utils.strings."""
import pytest
from app.utils.strings import dedupe_str_list


def test_dedupe_empty_input():
    assert dedupe_str_list(None) == []
    assert dedupe_str_list([]) == []


def test_dedupe_strips_whitespace():
    result = dedupe_str_list(["  hello ", "hello", "world  "])
    assert result == ["hello", "world"]


def test_dedupe_removes_blank_strings():
    result = dedupe_str_list(["", "  ", "valid"])
    assert result == ["valid"]


def test_dedupe_preserves_order():
    result = dedupe_str_list(["c", "a", "b", "a", "c"])
    assert result == ["c", "a", "b"]


def test_dedupe_accepts_generator():
    result = dedupe_str_list(x for x in ["a", "b", "a"])
    assert result == ["a", "b"]
