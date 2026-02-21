
import json
import os
import random
import secrets
import string
import threading
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pydantic import BaseModel, Field, field_validator, ValidationError
from werkzeug.middleware.proxy_fix import ProxyFix

from .repository import LogRepository
from .storage import load_data, save_data


class LogEntry(BaseModel):
    """Validated log entry for asthma medicine usage."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    spray: Optional[int] = Field(None, ge=0, description="Spray doses (non-negative)")
    ventoline: Optional[int] = Field(None, ge=0, description="Ventoline doses (non-negative)")
    preventive: Optional[bool] = Field(None, description="Whether this usage was preventive-related")

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format and is a valid date."""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Date must be in YYYY-MM-DD format and be a valid date: {e}")
        return v

    @field_validator("spray", "ventoline")
    @classmethod
    def validate_non_negative(cls, v: Optional[int]) -> Optional[int]:
        """Validate counts are non-negative."""
        if v is not None and v < 0:
            raise ValueError("Medicine count must be non-negative")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate that at least one medicine type is provided with non-zero count."""
        spray_count = self.spray or 0
        ventoline_count = self.ventoline or 0

        if spray_count == 0 and ventoline_count == 0:
            raise ValueError("At least one medicine type must have a non-zero count")


# Storage functions moved to storage.py module


def _generate_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def create_app(data_file: str | Path | None = None) -> Flask:
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
        methods=["GET", "POST", "OPTIONS"]
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

    # Create repository for data access
    log_repository = LogRepository(app.config["DATA_FILE"])

    data_lock = threading.Lock()

    def read_data() -> Dict[str, Any]:
        with data_lock:
            return load_data(app.config["DATA_FILE"])

    def write_data(data: Dict[str, Any]) -> None:
        with data_lock:
            save_data(app.config["DATA_FILE"], data)

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

                # Validate token against stored tokens
                data = read_data()
                valid_tokens = [
                    entry.get("token")
                    for entry in data.get("codes", [])
                    if "token" in entry
                ]

                if token not in valid_tokens:
                    return jsonify({"error": "Invalid token"}), 401

                # Token is valid, proceed
                return f(*args, **kwargs)

            return decorated_function
        return decorator

    @app.post("/generate-code")
    @limiter.limit("5 per hour")
    def generate_code() -> Any:
        code = _generate_code()
        data = read_data()
        data["codes"].append(
            {"code": code, "created_at": datetime.now(timezone.utc).isoformat()}
        )
        write_data(data)
        return jsonify({"code": code})

    @app.post("/login")
    @limiter.limit("10 per minute")
    def login() -> Any:
        payload = request.get_json(silent=True) or {}
        code = payload.get("code")
        if not code:
            return jsonify({"error": "Code is required"}), 400

        data = read_data()
        for entry in data.get("codes", []):
            if entry["code"] == code:
                entry["last_login_at"] = datetime.now(timezone.utc).isoformat()
                write_data(data)
                return jsonify({"status": "ok"})

        return jsonify({"error": "Invalid code"}), 400

    @app.post("/generate-token")
    @limiter.limit("10 per minute")
    def generate_token() -> Any:
        payload = request.get_json(silent=True) or {}
        code = payload.get("code")

        if not code:
            return jsonify({"error": "Code is required"}), 400

        data = read_data()

        # Find the code entry
        code_entry = None
        for entry in data.get("codes", []):
            if entry["code"] == code:
                code_entry = entry
                break

        if not code_entry:
            return jsonify({"error": "Invalid code"}), 400

        # If token already exists, return it
        if "token" in code_entry:
            return jsonify({"token": code_entry["token"]})

        # Generate new token (32 bytes = 64 hex characters)
        token = secrets.token_hex(32)

        # Store token with code
        code_entry["token"] = token
        code_entry["token_generated_at"] = datetime.now(timezone.utc).isoformat()

        write_data(data)

        return jsonify({"token": token})

    @app.post("/logs")
    @limiter.limit("100 per minute")
    def save_log() -> Any:
        payload = request.get_json(silent=True) or {}
        log = payload.get("log")

        if not isinstance(log, dict):
            return jsonify({"error": "'log' (object) is required"}), 400

        # Validate log entry structure
        try:
            validated_log = LogEntry(**log)
        except ValidationError as e:
            # Extract first error message for simplicity
            first_error = e.errors()[0]
            field = first_error["loc"][0] if first_error["loc"] else "log"
            message = first_error["msg"]
            return jsonify({"error": f"Validation error in '{field}': {message}"}), 400
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Try token authentication first (preferred)
        auth_header = request.headers.get("Authorization", "")
        token_valid = False
        code_from_token = None

        if auth_header.strip():
            parts = auth_header.strip().split()
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
                if token:
                    # Validate token
                    data = read_data()
                    for entry in data.get("codes", []):
                        if entry.get("token") == token:
                            token_valid = True
                            code_from_token = entry["code"]
                            break

                    if not token_valid:
                        return jsonify({"error": "Invalid token"}), 401

        # Fall back to code authentication if no valid token
        if not token_valid:
            code = payload.get("code")

            if not code:
                return (
                    jsonify({"error": "Either 'code' in body or 'Authorization' header is required"}),
                    400,
                )

            data = read_data()
            matching_codes = {entry["code"] for entry in data.get("codes", [])}
            if code not in matching_codes:
                return jsonify({"error": "Unknown code"}), 400
        else:
            # Token auth succeeded, load data
            code = code_from_token
            assert code is not None, "code_from_token must be set when token_valid is True"
            data = read_data()

        # Save the log using repository
        log_repository.save_log(code, log)
        return jsonify({"status": "saved"})

    @app.get("/logs")
    @require_auth()
    @limiter.limit("100 per minute")
    def get_logs() -> Any:
        """
        Retrieve all log entries for authenticated user.

        Requires:
            Authorization: Bearer <token> header

        Returns:
            JSON: {"logs": [{"date", "spray", "ventoline", "received_at"}]}
        """
        # Get token from Authorization header (already validated by @require_auth)
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.split()[1]  # "Bearer <token>"

        # Find code associated with this token
        data = read_data()
        code = None
        for entry in data.get("codes", []):
            if entry.get("token") == token:
                code = entry["code"]
                break

        if not code:
            return jsonify({"error": "Invalid token"}), 401

        # Get logs for this user
        logs = log_repository.get_logs_with_metadata(code)

        return jsonify({"logs": logs})

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

        # Find code associated with this token
        data = read_data()
        code = None
        for entry in data.get("codes", []):
            if entry.get("token") == token:
                code = entry["code"]
                break

        if not code:
            return jsonify({"error": "Code not found for this token"}), 404

        return jsonify({"code": code})

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
