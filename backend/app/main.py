
import logging
import os
import random
import string
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError
from werkzeug.middleware.proxy_fix import ProxyFix

from .repository import CodeRepository, LogRepository
from .sqlite_storage import SqliteStorage

logger = logging.getLogger(__name__)



class BaseEvent(BaseModel):
    """Common fields for all events."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Client-generated UUID for deduplication")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    timestamp: str = Field(..., description="ISO 8601 datetime of the usage")

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Date must be in YYYY-MM-DD format: {e}")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_format(cls, v: str) -> str:
        """Validate timestamp is a valid ISO 8601 datetime."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Timestamp must be a valid ISO 8601 datetime: {e}")
        return v


class AsthmaMedicineEvent(BaseEvent):
    """An asthma medicine usage event (spray or ventoline)."""

    type: str = Field(..., description="Medicine type: 'spray' or 'ventoline'")
    count: int = Field(..., ge=1, description="Number of doses (at least 1)")
    preventive: bool = Field(False, description="Whether this usage was preventive")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate type is a known medicine type."""
        if v not in ("spray", "ventoline"):
            raise ValueError("Type must be 'spray' or 'ventoline'")
        return v


class RitalinEvent(BaseEvent):
    """A Ritalin dose event."""

    count: int = Field(..., ge=1, description="Number of doses (at least 1)")


# Storage functions moved to storage.py module


def _generate_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_app(data_file: str | Path | None = None, db_file: str | Path | None = None) -> Flask:
    # Load environment variables from .env file if present
    load_dotenv()

    app = Flask(__name__)

    # Configure data file path
    # Priority: parameter > DATA_FILE env > ASTHMA_DATA_FILE env > default
    app.config["DATA_FILE"] = Path(
        data_file or os.environ.get("DATA_FILE") or os.environ.get("ASTHMA_DATA_FILE") or "backend/data/storage.json"
    )

    # Configure production mode
    production_value = os.environ.get("PRODUCTION", "false").lower()
    app.config["PRODUCTION"] = production_value in ("true", "1")

    # Configure CORS
    allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
    # Split comma-separated origins or use single origin/wildcard
    origins = [origin.strip() for origin in allowed_origins.split(",")] if "," in allowed_origins else allowed_origins

    # Store in config for testing
    app.config["ALLOWED_ORIGINS"] = allowed_origins

    CORS(
        app,
        origins=origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "DELETE", "OPTIONS"]
    )

    # Configure proxy support for production (behind nginx)
    if app.config["PRODUCTION"]:
        app.wsgi_app = ProxyFix(  # type: ignore[assignment]
            app.wsgi_app,
            x_for=1,    # Trust X-Forwarded-For (real client IP)
            x_proto=1,  # Trust X-Forwarded-Proto (original protocol)
            x_host=1,   # Trust X-Forwarded-Host (original host)
            x_prefix=1  # Trust X-Forwarded-Prefix (URL prefix)
        )

    # Configure rate limiting
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],  # No default limits, set per-endpoint
        storage_uri="memory://",  # In-memory storage for simplicity
    )

    # Custom error handler for rate limit exceeded
    @app.errorhandler(429)
    def ratelimit_handler(e: Any) -> tuple[Any, int]:
        response = jsonify({
            "error": "Rate limit exceeded",
            "message": str(e.description)
        })
        # Add Retry-After header (in seconds)
        # Extract the window from the description if possible, default to 60 seconds
        retry_after = 60  # Default: retry after 1 minute
        if hasattr(e, 'limit'):
            limit = e.limit
            # Parse limit like "5 per 1 hour" to get window in seconds
            if hasattr(limit, 'per'):
                retry_after = int(limit.per)
        response.headers['Retry-After'] = str(retry_after)
        return response, 429

    # Create SQLite storage if configured (dual-write alongside JSON)
    resolved_db_file = db_file or os.environ.get("DB_FILE")
    sqlite = SqliteStorage(resolved_db_file) if resolved_db_file else None

    # Create repositories for data access
    code_repository = CodeRepository(app.config["DATA_FILE"], sqlite=sqlite)
    log_repository = LogRepository(app.config["DATA_FILE"], sqlite=sqlite)

    # Migrate old log entries to the event format on startup (idempotent)
    log_repository.migrate_logs_to_events()

    def require_auth() -> Callable:
        """Decorator to require token authentication."""
        def decorator(f: Callable) -> Callable:
            @wraps(f)
            def decorated_function(*args: Any, **kwargs: Any) -> Any:
                # Get Authorization header
                auth_header = request.headers.get("Authorization", "")

                # Check format: "Bearer <token>"
                if not auth_header.strip():
                    return jsonify({"error": "Authorization header required"}), 401

                parts = auth_header.strip().split()
                if len(parts) != 2 or parts[0] != "Bearer":
                    return jsonify({"error": "Invalid authorization format. Use: Bearer <token>"}), 401

                token = parts[1]

                if not token:
                    return jsonify({"error": "Token required"}), 401

                if not code_repository.validate_token(token):
                    return jsonify({"error": "Invalid token"}), 401

                # Token is valid, proceed
                return f(*args, **kwargs)

            return decorated_function
        return decorator

    @app.post("/generate-code")
    @limiter.limit("5 per hour")
    def generate_code() -> Any:
        code = _generate_code()
        code_repository.create_code(code)
        return jsonify({"code": code})

    @app.post("/login")
    @limiter.limit("10 per minute")
    def login() -> Any:
        payload = request.get_json(silent=True) or {}
        code = payload.get("code")
        if not code:
            return jsonify({"error": "Code is required"}), 400

        if not code_repository.record_login(code):
            return jsonify({"error": "Invalid code"}), 400

        return jsonify({"status": "ok"})

    @app.post("/generate-token")
    @limiter.limit("10 per minute")
    def generate_token() -> Any:
        payload = request.get_json(silent=True) or {}
        code = payload.get("code")

        if not code:
            return jsonify({"error": "Code is required"}), 400

        token = code_repository.generate_token(code)

        if token is None:
            return jsonify({"error": "Invalid code"}), 400

        return jsonify({"token": token})

    @app.get("/code")
    @require_auth()
    @limiter.limit("10 per minute")
    def get_code() -> Any:
        """
        Retrieve the 6-character code for authenticated user.

        This allows logged-in users to retrieve their code for setting up
        sync on additional devices.

        Requires:
            Authorization: Bearer <token> header

        Returns:
            JSON: {"code": "ABC123"}
        """
        # Get token from Authorization header (already validated by @require_auth)
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]  # "Bearer <token>"

        code = code_repository.get_code_for_token(token)

        if not code:
            return jsonify({"error": "Code not found for this token"}), 404

        return jsonify({"code": code})

    @app.post("/events")
    @require_auth()
    @limiter.limit("100 per minute")
    def save_event() -> Any:
        """
        Save a single usage event for the authenticated user.

        Requires:
            Authorization: Bearer <token> header

        Body:
            JSON: {"event": {"id", "date", "timestamp", "type", "count", "preventive"}}

        Returns:
            JSON: {"status": "saved"}
        """
        payload = request.get_json(silent=True) or {}
        event = payload.get("event")

        if not isinstance(event, dict):
            return jsonify({"error": "'event' (object) is required"}), 400

        try:
            AsthmaMedicineEvent(**event)
        except ValidationError as e:
            first_error = e.errors()[0]
            field = first_error["loc"][0] if first_error["loc"] else "event"
            message = first_error["msg"]
            logger.warning("Invalid asthma event rejected: %s (field=%s, payload=%r)", message, field, event)
            return jsonify({"error": f"Validation error in '{field}': {message}"}), 400

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        log_repository.save_event(code, event)
        return jsonify({"status": "saved"})

    @app.post("/events/batch")
    @require_auth()
    @limiter.limit("20 per minute")
    def save_events_batch() -> Any:
        """
        Save multiple asthma usage events in one request.

        Requires:
            Authorization: Bearer <token> header

        Body:
            JSON: {"events": [{"id", "date", "timestamp", "type", "count", "preventive"}, ...]}

        Returns:
            JSON: {"saved": N, "duplicates": M}
        """
        payload = request.get_json(silent=True) or {}
        events = payload.get("events")

        if not isinstance(events, list):
            return jsonify({"error": "'events' (array) is required"}), 400

        for event in events:
            if not isinstance(event, dict):
                return jsonify({"error": "Each event must be an object"}), 400
            try:
                AsthmaMedicineEvent(**event)
            except ValidationError as e:
                first_error = e.errors()[0]
                field = first_error["loc"][0] if first_error["loc"] else "event"
                message = first_error["msg"]
                logger.warning("Invalid asthma event rejected: %s (field=%s, payload=%r)", message, field, event)
                return jsonify({"error": f"Validation error in '{field}': {message}"}), 400

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        saved = log_repository.save_events_batch(code, events)
        return jsonify({"saved": saved, "duplicates": len(events) - saved})

    @app.get("/events")
    @require_auth()
    @limiter.limit("100 per minute")
    def get_events() -> Any:
        """
        Retrieve all usage events for the authenticated user.

        Requires:
            Authorization: Bearer <token> header

        Returns:
            JSON: {"events": [{"id", "date", "timestamp", "type", "count", "preventive", "received_at"}]}
        """
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        return jsonify({"events": log_repository.get_events(code)})

    @app.delete("/events")
    @require_auth()
    @limiter.limit("100 per minute")
    def delete_events() -> Any:
        """
        Delete asthma events by ID for the authenticated user.

        Body:
            JSON: {"ids": ["id1", "id2", ...]}

        Returns:
            JSON: {"deleted": N}
        """
        payload = request.get_json(silent=True) or {}
        ids = payload.get("ids")
        if not isinstance(ids, list):
            return jsonify({"error": "'ids' (array) is required"}), 400

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        log_repository.delete_events(code, ids)
        return jsonify({"deleted": len(ids)})

    @app.post("/ritalin-events")
    @require_auth()
    @limiter.limit("100 per minute")
    def save_ritalin_event() -> Any:
        """
        Save a single Ritalin dose event for the authenticated user.

        Requires:
            Authorization: Bearer <token> header

        Body:
            JSON: {"event": {"id", "date", "timestamp", "count"}}

        Returns:
            JSON: {"status": "saved"}
        """
        payload = request.get_json(silent=True) or {}
        event = payload.get("event")

        if not isinstance(event, dict):
            return jsonify({"error": "'event' (object) is required"}), 400

        try:
            RitalinEvent(**event)
        except ValidationError as e:
            first_error = e.errors()[0]
            field = first_error["loc"][0] if first_error["loc"] else "event"
            message = first_error["msg"]
            logger.warning("Invalid ritalin event rejected: %s (field=%s, payload=%r)", message, field, event)
            return jsonify({"error": f"Validation error in '{field}': {message}"}), 400

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        log_repository.save_ritalin_event(code, event)
        return jsonify({"status": "saved"})

    @app.post("/ritalin-events/batch")
    @require_auth()
    @limiter.limit("20 per minute")
    def save_ritalin_events_batch() -> Any:
        """
        Save multiple Ritalin dose events in one request.

        Requires:
            Authorization: Bearer <token> header

        Body:
            JSON: {"events": [{"id", "date", "timestamp", "count"}, ...]}

        Returns:
            JSON: {"saved": N, "duplicates": M}
        """
        payload = request.get_json(silent=True) or {}
        events = payload.get("events")

        if not isinstance(events, list):
            return jsonify({"error": "'events' (array) is required"}), 400

        for event in events:
            if not isinstance(event, dict):
                return jsonify({"error": "Each event must be an object"}), 400
            try:
                RitalinEvent(**event)
            except ValidationError as e:
                first_error = e.errors()[0]
                field = first_error["loc"][0] if first_error["loc"] else "event"
                message = first_error["msg"]
                logger.warning("Invalid ritalin event rejected: %s (field=%s, payload=%r)", message, field, event)
                return jsonify({"error": f"Validation error in '{field}': {message}"}), 400

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        saved = log_repository.save_ritalin_events_batch(code, events)
        return jsonify({"saved": saved, "duplicates": len(events) - saved})

    @app.get("/ritalin-events")
    @require_auth()
    @limiter.limit("100 per minute")
    def get_ritalin_events() -> Any:
        """
        Retrieve all Ritalin dose events for the authenticated user.

        Requires:
            Authorization: Bearer <token> header

        Returns:
            JSON: {"events": [{"id", "date", "timestamp", "count", "received_at"}]}
        """
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        return jsonify({"events": log_repository.get_ritalin_events(code)})

    @app.delete("/ritalin-events")
    @require_auth()
    @limiter.limit("100 per minute")
    def delete_ritalin_events() -> Any:
        """
        Delete ritalin events by ID for the authenticated user.

        Body:
            JSON: {"ids": ["id1", "id2", ...]}

        Returns:
            JSON: {"deleted": N}
        """
        payload = request.get_json(silent=True) or {}
        ids = payload.get("ids")
        if not isinstance(ids, list):
            return jsonify({"error": "'ids' (array) is required"}), 400

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]
        code = code_repository.get_code_for_token(token)
        if not code:
            return jsonify({"error": "Invalid token"}), 401

        log_repository.delete_ritalin_events(code, ids)
        return jsonify({"deleted": len(ids)})

    @app.get("/health")
    def health() -> Any:
        """Health check endpoint for monitoring and container health checks."""
        return jsonify({"status": "ok", "version": "0.1.0"})

    @app.get("/test-protected")
    @require_auth()
    def test_protected() -> Any:
        """Test endpoint to verify token authentication works."""
        return jsonify({"status": "authorized"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
