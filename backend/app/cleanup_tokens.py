"""Remove legacy plaintext tokens while the application is stopped.

Back up both files first. This command must not run alongside app workers:
JSON writes are atomic but are not coordinated across processes.
"""

import argparse
import json
from pathlib import Path

from .sqlite_storage import SqliteStorage
from .storage import save_data


def cleanup_plaintext_tokens(json_path: Path, storage: SqliteStorage) -> None:
    """Verify both stores, then clear JSON and SQLite plaintext tokens.

    The caller must stop all writers before invoking this function. If the
    process stops between writes, rerunning is safe: digests remain intact.
    """
    with json_path.open() as fp:
        data = json.load(fp)

    for entry in [*data.get("codes", []), *storage.get_codes()]:
        token = entry.get("token")
        if token and storage.get_code_for_hashed_token(token) != entry["code"]:
            raise ValueError("Legacy token has no matching account digest")

    for entry in data.get("codes", []):
        entry.pop("token", None)
    save_data(json_path, data)
    storage.remove_legacy_plaintext_tokens()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--app-stopped", action="store_true", required=True,
                        help="Confirm all application workers are stopped")
    args = parser.parse_args()
    if not args.json.is_file() or not args.db.is_file():
        parser.error("Both existing storage files are required")
    storage = SqliteStorage(args.db)
    try:
        cleanup_plaintext_tokens(args.json, storage)
    finally:
        storage.close()
    print("Legacy plaintext token fields cleared from active storage.")


if __name__ == "__main__":
    main()
