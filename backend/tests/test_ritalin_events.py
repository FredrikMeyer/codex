"""
Tests for POST /ritalin-events, POST /ritalin-events/batch, DELETE /ritalin-events, and GET /ritalin-events endpoints.

Ritalin doses are stored as events identified by a client-generated
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
        "id": "ritalin-abc-123",
        "date": "2026-03-04",
        "timestamp": "2026-03-04T08:00:00.000Z",
        "count": 1,
    }
    return {**base, **overrides}


# --- POST /ritalin-events ---

def test_save_ritalin_event_returns_200(auth_token):
    """POST /ritalin-events returns 200 for a valid event."""
    test_client, _, token = auth_token
    response = test_client.post(
        "/ritalin-events",
        json={"event": _valid_event()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "saved"


def test_duplicate_ritalin_event_is_idempotent(auth_token):
    """Posting a Ritalin event with a duplicate id stores only one event."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/ritalin-events", json={"event": _valid_event()}, headers=headers)
    test_client.post("/ritalin-events", json={"event": _valid_event()}, headers=headers)

    events = test_client.get("/ritalin-events", headers=headers).get_json()["events"]
    assert len(events) == 1


def test_invalid_ritalin_event_returns_400(auth_token):
    """POST /ritalin-events without required field returns 400."""
    test_client, _, token = auth_token
    incomplete = {"date": "2026-03-04", "timestamp": "2026-03-04T08:00:00.000Z", "count": 1}
    response = test_client.post(
        "/ritalin-events",
        json={"event": incomplete},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


# --- GET /ritalin-events authentication ---

def test_get_ritalin_events_requires_token(client):
    """GET /ritalin-events returns 401 without a token."""
    response = client.get("/ritalin-events")
    assert response.status_code == 401


# --- GET /ritalin-events happy path ---

def test_ritalin_event_round_trips(auth_token):
    """A saved Ritalin event is returned with all fields intact by GET /ritalin-events."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/ritalin-events/batch", json={"events": [_valid_event(count=2)]}, headers=headers)

    response = test_client.get("/ritalin-events", headers=headers)
    assert response.status_code == 200
    events = response.get_json()["events"]
    assert len(events) == 1
    ev = events[0]
    assert ev["id"] == "ritalin-abc-123"
    assert ev["date"] == "2026-03-04"
    assert ev["timestamp"] == "2026-03-04T08:00:00.000Z"
    assert ev["count"] == 2
    assert "received_at" in ev


def test_ritalin_events_are_user_isolated(auth_token):
    """Ritalin events from other users are not returned."""
    test_client, _, token1 = auth_token
    headers1 = {"Authorization": f"Bearer {token1}"}

    code2 = test_client.post("/generate-code").get_json()["code"]
    token2 = test_client.post("/generate-token", json={"code": code2}).get_json()["token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    test_client.post("/ritalin-events/batch", json={"events": [_valid_event(id="user1-ritalin")]}, headers=headers1)
    test_client.post("/ritalin-events/batch", json={"events": [_valid_event(id="user2-ritalin")]}, headers=headers2)

    events = test_client.get("/ritalin-events", headers=headers1).get_json()["events"]
    assert len(events) == 1
    assert events[0]["id"] == "user1-ritalin"


# --- Batch endpoint ---

def test_ritalin_batch_requires_token(client):
    """POST /ritalin-events/batch returns 401 without a token."""
    response = client.post("/ritalin-events/batch", json={"events": [_valid_event()]})
    assert response.status_code == 401


def test_ritalin_batch_saves_multiple_events(auth_token):
    """POST /ritalin-events/batch saves all events and GET returns them."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}
    events = [_valid_event(id="r-1"), _valid_event(id="r-2"), _valid_event(id="r-3")]

    response = test_client.post("/ritalin-events/batch", json={"events": events}, headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {"saved": 3, "duplicates": 0}
    stored = test_client.get("/ritalin-events", headers=headers).get_json()["events"]
    assert len(stored) == 3


def test_ritalin_batch_skips_duplicates(auth_token):
    """POST /ritalin-events/batch reports duplicates without storing them twice."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}
    events = [_valid_event(id="r-dup-1"), _valid_event(id="r-dup-2")]

    test_client.post("/ritalin-events/batch", json={"events": events}, headers=headers)
    response = test_client.post("/ritalin-events/batch", json={"events": events}, headers=headers)

    assert response.get_json() == {"saved": 0, "duplicates": 2}
    stored = test_client.get("/ritalin-events", headers=headers).get_json()["events"]
    assert len(stored) == 2


def test_ritalin_batch_invalid_event_returns_400(auth_token):
    """POST /ritalin-events/batch returns 400 if any event fails validation."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}
    events = [_valid_event(id="ok"), {"id": "bad", "date": "2026-03-04"}]

    response = test_client.post("/ritalin-events/batch", json={"events": events}, headers=headers)

    assert response.status_code == 400


# --- DELETE /ritalin-events ---

def test_delete_ritalin_events_requires_token(client):
    """DELETE /ritalin-events returns 401 without a token."""
    response = client.delete("/ritalin-events", json={"ids": ["ritalin-abc-123"]})
    assert response.status_code == 401


def test_delete_ritalin_events_removes_specified_ids(auth_token):
    """Deleted ritalin event IDs are no longer returned by GET /ritalin-events."""
    test_client, _, token = auth_token
    headers = {"Authorization": f"Bearer {token}"}

    test_client.post("/ritalin-events/batch", json={"events": [_valid_event(id="r1"), _valid_event(id="r2")]}, headers=headers)

    response = test_client.delete("/ritalin-events", json={"ids": ["r1"]}, headers=headers)
    assert response.status_code == 200

    remaining = test_client.get("/ritalin-events", headers=headers).get_json()["events"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == "r2"


def test_delete_ritalin_events_with_unknown_id_is_a_noop(auth_token):
    """Deleting a non-existent ritalin ID returns 200 and causes no error."""
    test_client, _, token = auth_token
    response = test_client.delete(
        "/ritalin-events", json={"ids": ["does-not-exist"]}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_delete_ritalin_events_only_affects_requesting_user(auth_token):
    """A user cannot delete another user's ritalin events."""
    test_client, _, token1 = auth_token
    headers1 = {"Authorization": f"Bearer {token1}"}

    code2 = test_client.post("/generate-code").get_json()["code"]
    token2 = test_client.post("/generate-token", json={"code": code2}).get_json()["token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    test_client.post("/ritalin-events", json={"event": _valid_event(id="shared-id")}, headers=headers2)

    test_client.delete("/ritalin-events", json={"ids": ["shared-id"]}, headers=headers1)

    events = test_client.get("/ritalin-events", headers=headers2).get_json()["events"]
    assert len(events) == 1


def test_delete_ritalin_events_missing_ids_key_returns_400(auth_token):
    """DELETE /ritalin-events without 'ids' key returns 400."""
    test_client, _, token = auth_token
    response = test_client.delete(
        "/ritalin-events", json={"not_ids": []}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
