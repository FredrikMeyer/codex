"""
Tests for POST /events and GET /events endpoints.

Each usage is stored as an individual event with timestamp, type, count,
and attributes such as preventive. Events are identified by a client-generated
UUID that makes saves idempotent.
"""

from pathlib import Path

import pytest

from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    """Create test client with temporary data file."""
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def auth_token(client):
    """Generate a valid token for testing."""
    code = client.post("/generate-code").get_json()["code"]
    token = client.post("/generate-token", json={"code": code}).get_json()["token"]
    return client, code, token


def _valid_event(**overrides):
    base = {
        "id": "abc-123",
        "date": "2026-02-21",
        "timestamp": "2026-02-21T14:30:00.000Z",
        "type": "ventoline",
        "count": 2,
        "preventive": False,
    }
    return {**base, **overrides}


# --- Authentication ---

def test_post_events_requires_token(client):
    """POST /events returns 401 without a token."""
    response = client.post("/events", json={"event": _valid_event()})
    assert response.status_code == 401


def test_get_events_requires_token(client):
    """GET /events returns 401 without a token."""
    response = client.get("/events")
    assert response.status_code == 401


# --- Happy path ---

def test_post_event_saves_and_get_returns_it(auth_token):
    """A saved event is returned by GET /events."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events", json={"event": _valid_event()}, headers=headers)

    response = test_client.get("/events", headers=headers)
    assert response.status_code == 200
    events = response.get_json()["events"]
    assert len(events) == 1
    ev = events[0]
    assert ev["id"] == "abc-123"
    assert ev["date"] == "2026-02-21"
    assert ev["timestamp"] == "2026-02-21T14:30:00.000Z"
    assert ev["type"] == "ventoline"
    assert ev["count"] == 2
    assert ev["preventive"] is False
    assert "received_at" in ev


def test_post_event_with_preventive_true(auth_token):
    """preventive flag is stored and returned correctly."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events", json={"event": _valid_event(preventive=True)}, headers=headers)

    events = test_client.get("/events", headers=headers).get_json()["events"]
    assert events[0]["preventive"] is True


def test_get_events_returns_empty_for_new_user(auth_token):
    """GET /events returns empty list when user has no events."""
    test_client, _, token = auth_token
    response = test_client.get("/events", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.get_json()["events"] == []


def test_get_events_excludes_other_users(auth_token):
    """Events from other users are not returned."""
    test_client, _, token1 = auth_token
    headers1 = {"Authorization": f"Bearer {token1}"}

    code2 = test_client.post("/generate-code").get_json()["code"]
    token2 = test_client.post("/generate-token", json={"code": code2}).get_json()["token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    test_client.post("/events", json={"event": _valid_event(id="user1-event")}, headers=headers1)
    test_client.post("/events", json={"event": _valid_event(id="user2-event")}, headers=headers2)

    events = test_client.get("/events", headers=headers1).get_json()["events"]
    assert len(events) == 1
    assert events[0]["id"] == "user1-event"


# --- Idempotency ---

def test_posting_same_id_twice_stores_only_one_event(auth_token):
    """Posting an event with a duplicate id is a no-op (idempotent)."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events", json={"event": _valid_event()}, headers=headers)
    test_client.post("/events", json={"event": _valid_event()}, headers=headers)

    events = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(events) == 1


def test_posting_different_ids_stores_multiple_events(auth_token):
    """Events with distinct ids are all stored."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events", json={"event": _valid_event(id="id-1")}, headers=headers)
    test_client.post("/events", json={"event": _valid_event(id="id-2")}, headers=headers)

    events = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(events) == 2


# --- Validation ---

def test_missing_event_field_returns_400(auth_token):
    """POST /events without 'event' key returns 400."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events", json={"not_event": {}}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400


def test_invalid_type_returns_400(auth_token):
    """type must be 'spray' or 'ventoline'."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events",
        json={"event": _valid_event(type="inhaler")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "type" in response.get_json()["error"].lower()


def test_count_zero_returns_400(auth_token):
    """count must be at least 1."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events",
        json={"event": _valid_event(count=0)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_count_negative_returns_400(auth_token):
    """count must be positive."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events",
        json={"event": _valid_event(count=-1)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_invalid_date_format_returns_400(auth_token):
    """date must be YYYY-MM-DD."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events",
        json={"event": _valid_event(date="21-02-2026")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "date" in response.get_json()["error"].lower()


def test_invalid_timestamp_returns_400(auth_token):
    """timestamp must be a valid ISO 8601 datetime."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events",
        json={"event": _valid_event(timestamp="not-a-timestamp")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "timestamp" in response.get_json()["error"].lower()


def test_spray_type_is_accepted(auth_token):
    """type='spray' is a valid event type."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events",
        json={"event": _valid_event(type="spray")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
