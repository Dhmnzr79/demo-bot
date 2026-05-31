from __future__ import annotations

from orchestration.route_guards import (
    is_duplicate_question,
    is_obvious_noise,
    norm_dup_text,
    normalize_question_text,
)


def test_normalize_question_text_truncates() -> None:
    q, truncated = normalize_question_text("  hello  ")
    assert q == "hello"
    assert truncated is False


def test_is_obvious_noise_repeated_chars() -> None:
    assert is_obvious_noise("!!!!!!")
    assert not is_obvious_noise("имплантация")


def test_is_duplicate_question() -> None:
    st = {
        "hist": [
            {"role": "user", "content": "Сколько стоит имплантация?"},
        ]
    }
    assert is_duplicate_question(st, "Сколько стоит имплантация?")


def test_norm_dup_text() -> None:
    assert norm_dup_text("  Ёлка! ") == "елка"
