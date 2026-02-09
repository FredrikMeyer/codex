
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

from flask import Flask, jsonify, request
from pydantic import BaseModel, Field, field_validator, ValidationError


class LogEntry(BaseModel):
    """Validated log entry for asthma medicine usage."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    spray: Optional[int] = Field(None, ge=0, description="Spray doses (non-negative)")
    ventoline: Optional[int] = Field(None, ge=0, description="Ventoline doses (non-negative)")

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


def _default_data() -> Dict[str, Any]:
    return {"codes": [], "logs": []}


def _ensure_data_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(_default_data(), indent=2))


def _load_data(path: Path) -> Dict[str, Any]:
    _ensure_data_file(path)
    with path.open() as fp:
        return json.load(fp)


def _save_data(path: Path, data: Dict[str, Any]) -> None:
    _ensure_data_file(path)
    with path.open("w") as fp:
        json.dump(data, fp, indent=2)


def _generate_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))


def create_app(data_file: str | Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATA_FILE"] = Path(
        data_file or os.environ.get("ASTHMA_DATA_FILE") or "backend/data/storage.json"
    )
    data_lock = threading.Lock()

    def read_data() -> Dict[str, Any]:
        with data_lock:
            return _load_data(app.config["DATA_FILE"])

    def write_data(data: Dict[str, Any]) -> None:
        with data_lock:
            _save_data(app.config["DATA_FILE"], data)

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
    def generate_code() -> Any:
        code = _generate_code()
        data = read_data()
        data["codes"].append(
            {"code": code, "created_at": datetime.now(timezone.utc).isoformat()}
        )
        write_data(data)
        return jsonify({"code": code})

    @app.post("/login")
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
            data = read_data()

        # Save the log
        log_entry = {
            "code": code,
            "log": log,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        data["logs"].append(log_entry)
        write_data(data)
        return jsonify({"status": "saved"})

    @app.get("/test-protected")
    @require_auth()
    def test_protected() -> Any:
        """Test endpoint to verify token authentication works."""
        return jsonify({"status": "authorized"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
