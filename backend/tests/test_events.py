"""
Tests for POST /events, POST /events/batch, DELETE /events, and GET /events endpoints.

Each usage is stored as an event with timestamp, type, count,
and attributes such as preventive. Events are identified by a client-generated
UUID that makes saves idempotent.
"""

from pathlib import Path

import pytest

from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    """Create test client with temporary data file and in-memory SQLite."""
    data_file = tmp_path / "data.json"
    app = create_app(data_file, db_file=":memory:")
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


# --- POST /events authentication ---

def test_post_events_requires_token(client):
    """POST /events returns 401 without a token."""
    response = client.post("/events", json={"event": _valid_event()})
    assert response.status_code == 401


# --- GET /events authentication ---

def test_get_events_requires_token(client):
    """GET /events returns 401 without a token."""
    response = client.get("/events")
    assert response.status_code == 401


# --- POST /events happy path ---

def test_post_event_saves_and_get_returns_it(auth_token):
    """A saved event is returned by GET /events."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events", json={"event": _valid_event()}, headers=headers)

    events = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(events) == 1
    ev = events[0]
    assert ev["id"] == "abc-123"
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


def test_posting_same_id_twice_stores_only_one_event(auth_token):
    """Posting an event with a duplicate id is a no-op (idempotent)."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events", json={"event": _valid_event()}, headers=headers)
    test_client.post("/events", json={"event": _valid_event()}, headers=headers)

    events = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(events) == 1


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


# --- GET /events happy path ---

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

    test_client.post("/events/batch", json={"events": [_valid_event(id="user1-event")]}, headers=headers1)
    test_client.post("/events/batch", json={"events": [_valid_event(id="user2-event")]}, headers=headers2)

    events = test_client.get("/events", headers=headers1).get_json()["events"]
    assert len(events) == 1
    assert events[0]["id"] == "user1-event"


# --- Batch endpoint ---

def test_batch_post_requires_token(client):
    """POST /events/batch returns 401 without a token."""
    response = client.post("/events/batch", json={"events": [_valid_event()]})
    assert response.status_code == 401


def test_batch_post_round_trips_all_fields(auth_token):
    """A saved event is returned with all fields intact by GET /events."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events/batch", json={"events": [_valid_event(preventive=True)]}, headers=headers)

    events = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(events) == 1
    ev = events[0]
    assert ev["id"] == "abc-123"
    assert ev["date"] == "2026-02-21"
    assert ev["timestamp"] == "2026-02-21T14:30:00.000Z"
    assert ev["type"] == "ventoline"
    assert ev["count"] == 2
    assert ev["preventive"] is True
    assert "received_at" in ev


def test_batch_post_saves_multiple_events(auth_token):
    """POST /events/batch saves all events and GET returns them."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}
    events = [_valid_event(id="batch-1"), _valid_event(id="batch-2"), _valid_event(id="batch-3")]

    response = test_client.post("/events/batch", json={"events": events}, headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {"saved": 3, "duplicates": 0}
    stored = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(stored) == 3


def test_batch_post_skips_duplicates(auth_token):
    """POST /events/batch reports duplicates without storing them twice."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}
    events = [_valid_event(id="dup-1"), _valid_event(id="dup-2")]

    test_client.post("/events/batch", json={"events": events}, headers=headers)
    response = test_client.post("/events/batch", json={"events": events}, headers=headers)

    assert response.get_json() == {"saved": 0, "duplicates": 2}
    stored = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(stored) == 2


def test_batch_post_partial_duplicates(auth_token):
    """POST /events/batch saves only new events when some are duplicates."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events/batch", json={"events": [_valid_event(id="existing")]}, headers=headers)
    response = test_client.post(
        "/events/batch",
        json={"events": [_valid_event(id="existing"), _valid_event(id="new-one")]},
        headers=headers,
    )

    assert response.get_json() == {"saved": 1, "duplicates": 1}


def test_batch_post_invalid_event_returns_400(auth_token):
    """POST /events/batch returns 400 if any event fails validation."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}
    events = [_valid_event(id="ok"), _valid_event(id="bad", type="inhaler")]

    response = test_client.post("/events/batch", json={"events": events}, headers=headers)

    assert response.status_code == 400
    assert "type" in response.get_json()["error"].lower()


def test_batch_post_missing_events_key_returns_400(auth_token):
    """POST /events/batch without 'events' key returns 400."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events/batch", json={"not_events": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400


def test_batch_post_empty_list_returns_zero(auth_token):
    """POST /events/batch with empty list saves nothing."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/events/batch", json={"events": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"saved": 0, "duplicates": 0}


# --- DELETE /events ---

def test_delete_events_requires_token(client):
    """DELETE /events returns 401 without a token."""
    response = client.delete("/events", json={"ids": ["abc-123"]})
    assert response.status_code == 401


def test_delete_events_removes_specified_ids(auth_token):
    """Deleted event IDs are no longer returned by GET /events."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/events/batch", json={"events": [_valid_event(id="e1"), _valid_event(id="e2")]}, headers=headers)

    response = test_client.delete("/events", json={"ids": ["e1"]}, headers=headers)
    assert response.status_code == 200

    remaining = test_client.get("/events", headers=headers).get_json()["events"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == "e2"


def test_delete_events_with_unknown_id_is_a_noop(auth_token):
    """Deleting a non-existent ID returns 200 and causes no error."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    response = test_client.delete("/events", json={"ids": ["does-not-exist"]}, headers=headers)
    assert response.status_code == 200


def test_delete_events_only_affects_requesting_user(auth_token):
    """A user cannot delete another user's events."""
    test_client, _, token1 = auth_token
    headers1 = {"Authorization": f"Bearer {token1}"}

    code2 = test_client.post("/generate-code").get_json()["code"]
    token2 = test_client.post("/generate-token", json={"code": code2}).get_json()["token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    test_client.post("/events", json={"event": _valid_event(id="shared-id")}, headers=headers2)

    test_client.delete("/events", json={"ids": ["shared-id"]}, headers=headers1)

    events = test_client.get("/events", headers=headers2).get_json()["events"]
    assert len(events) == 1


def test_delete_events_missing_ids_key_returns_400(auth_token):
    """DELETE /events without 'ids' key returns 400."""
    test_client, _, token = auth_token
    response = test_client.delete(
        "/events", json={"not_ids": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
