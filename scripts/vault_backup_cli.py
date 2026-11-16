"""Interactive CLI for encrypted AutoEarn credential-vault backups.

Passphrases are always read with getpass and are never accepted as command-line
arguments, where they could leak through shell history or process listings.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vault import VAULT_DB  # noqa: E402
from app.vault_backup import create_backup, restore_backup  # noqa: E402


def _passphrase(*, confirm: bool = False) -> str:
    value = getpass.getpass("عبارت اصلی نسخه پشتیبان: ")
    if confirm:
        repeated = getpass.getpass("تکرار عبارت اصلی: ")
        if value != repeated:
            raise ValueError("عبارت‌های واردشده یکسان نیستند.")
    return value


def _confirm_replace(path: Path) -> bool:
    if not path.exists():
        return True
    print(f"هشدار: فایل موجود جایگزین خواهد شد: {path}")
    answer = input("برای تأیید دقیقاً REPLACE را وارد کنید: ")
    return answer == "REPLACE"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="پشتیبان‌گیری رمزگذاری‌شده از خزانه شخصی AutoEarn AI"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="ساخت نسخه پشتیبان رمزگذاری‌شده")
    create.add_argument("destination", type=Path, help="مسیر فایل .aev")
    create.add_argument("--source", type=Path, default=VAULT_DB, help="مسیر دیتابیس خزانه")
    create.add_argument("--overwrite", action="store_true", help="اجازه جایگزینی فایل موجود")

    restore = commands.add_parser("restore", help="بازیابی نسخه پشتیبان")
    restore.add_argument("backup", type=Path, help="فایل پشتیبان .aev")
    restore.add_argument("destination", type=Path, help="مسیر دیتابیس مقصد")
    restore.add_argument("--overwrite", action="store_true", help="اجازه جایگزینی دیتابیس مقصد")

    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            if args.destination.exists() and (
                not args.overwrite or not _confirm_replace(args.destination)
            ):
                print("عملیات لغو شد؛ فایل موجود تغییر نکرد.", file=sys.stderr)
                return 2
            phrase = _passphrase(confirm=True)
            result = create_backup(
                args.source, args.destination, phrase, overwrite=args.overwrite
            )
            print(f"نسخه پشتیبان رمزگذاری‌شده ساخته شد: {result}")
            print("عبارت اصلی را جدا از فایل پشتیبان و در محل امن نگهداری کن.")
            return 0

        if args.destination.exists() and (
            not args.overwrite or not _confirm_replace(args.destination)
        ):
            print("عملیات لغو شد؛ فایل مقصد تغییر نکرد.", file=sys.stderr)
            return 2
        phrase = _passphrase()
        result = restore_backup(
            args.backup, args.destination, phrase, overwrite=args.overwrite
        )
        print(f"بازیابی و بررسی سلامت دیتابیس موفق بود: {result}")
        print("پیش از اجرای برنامه، مطمئن شو مسیر مقصد همان خزانه موردنظر است.")
        return 0
    except (ValueError, OSError) as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nعملیات لغو شد.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
