"""
Tests for CodeRepository.

Uses a temporary JSON file so each test gets a clean slate,
consistent with the existing LogRepository tests.
"""

from pathlib import Path

import pytest

from app.repository import CodeRepository


@pytest.fixture()
def repo(tmp_path: Path) -> CodeRepository:
    return CodeRepository(tmp_path / "data.json")


# --- create_code ---

def test_create_code_stores_code(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    assert repo.validate_token("any") is False  # code exists but has no token yet


def test_create_code_allows_token_generation_afterwards(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    token = repo.generate_token("ABC123")
    assert token is not None


# --- record_login ---

def test_record_login_returns_true_for_existing_code(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    assert repo.record_login("ABC123") is True


def test_record_login_returns_false_for_unknown_code(repo: CodeRepository) -> None:
    assert repo.record_login("NOPE99") is False


# --- generate_token ---

def test_generate_token_returns_none_for_unknown_code(repo: CodeRepository) -> None:
    assert repo.generate_token("NOPE99") is None


def test_generate_token_returns_a_token_for_valid_code(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    token = repo.generate_token("ABC123")
    assert token is not None
    assert len(token) == 64  # secrets.token_hex(32)


def test_generate_token_is_idempotent(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    token1 = repo.generate_token("ABC123")
    token2 = repo.generate_token("ABC123")
    assert token1 == token2


def test_two_codes_get_different_tokens(repo: CodeRepository) -> None:
    repo.create_code("CODE_A")
    repo.create_code("CODE_B")
    token_a = repo.generate_token("CODE_A")
    token_b = repo.generate_token("CODE_B")
    assert token_a != token_b


# --- validate_token ---

def test_validate_token_returns_false_for_unknown_token(repo: CodeRepository) -> None:
    assert repo.validate_token("not-a-real-token") is False


def test_validate_token_returns_true_for_valid_token(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    token = repo.generate_token("ABC123")
    assert repo.validate_token(token) is True  # type: ignore[arg-type]


def test_validate_token_returns_false_for_code_without_token(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    assert repo.validate_token("ABC123") is False


# --- get_code_for_token ---

def test_get_code_for_token_returns_none_for_unknown_token(repo: CodeRepository) -> None:
    assert repo.get_code_for_token("unknown") is None


def test_get_code_for_token_returns_correct_code(repo: CodeRepository) -> None:
    repo.create_code("ABC123")
    token = repo.generate_token("ABC123")
    assert repo.get_code_for_token(token) == "ABC123"  # type: ignore[arg-type]


def test_get_code_for_token_isolates_users(repo: CodeRepository) -> None:
    repo.create_code("CODE_A")
    repo.create_code("CODE_B")
    token_a = repo.generate_token("CODE_A")
    assert repo.get_code_for_token(token_a) == "CODE_A"  # type: ignore[arg-type]
