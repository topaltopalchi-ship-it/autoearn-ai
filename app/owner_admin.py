from __future__ import annotations

import getpass
import sys

from app.main import init_db, initialize_owner_password


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "set-password":
        print("Usage: python -m app.owner_admin set-password")
        return 2
    init_db()
    password = getpass.getpass("New owner password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm owner password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 1
    try:
        initialize_owner_password(password)
    except ValueError as exc:
        print(str(exc))
        return 1
    print("Owner password updated. All previous browser sessions were revoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
