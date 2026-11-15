#!/usr/bin/env python3
"""Search and download free public-domain audiobooks from LibriVox.

LibriVox recordings are volunteer readings of public-domain books, free for
anyone to use. This tool talks to the public LibriVox API.

Usage:
    python3 librivox_dl.py search "pride and prejudice"
    python3 librivox_dl.py search --author "Mark Twain"
    python3 librivox_dl.py info 253
    python3 librivox_dl.py download 253 --output ~/audiobooks

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional

API_BASE = "https://librivox.org/api/feed/audiobooks/"
USER_AGENT = "librivox-dl/0.1 (+https://github.com/isalivenour-hue/librivox-dl)"
DEFAULT_LIMIT = 10
MAX_LIMIT = 50


class LibriVoxError(Exception):
    pass


def _open(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_json(params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    url = f"{API_BASE}?{query}"
    try:
        with _open(url) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise LibriVoxError(f"could not reach LibriVox: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LibriVoxError(f"unexpected response from LibriVox: {exc}") from exc


def search_books(title: Optional[str] = None, author: Optional[str] = None,
                 limit: int = DEFAULT_LIMIT) -> List[dict]:
    if not title and not author:
        raise LibriVoxError("give a title and/or an author to search for")
    params = {"format": "json", "limit": max(1, min(limit, MAX_LIMIT))}
    if title:
        params["title"] = title
    if author:
        params["author"] = author
    data = fetch_json(params)
    return data.get("books", [])


def get_book(book_id: str) -> dict:
    data = fetch_json({"format": "json", "id": str(book_id)})
    books = data.get("books", [])
    if not books:
        raise LibriVoxError(f"no LibriVox book with id {book_id}")
    return books[0]


def author_names(book: dict) -> str:
    authors = book.get("authors") or []
    names = [
        " ".join(p for p in (a.get("first_name", ""), a.get("last_name", "")) if p).strip()
        for a in authors
    ]
    return ", ".join(n for n in names if n) or "Unknown author"


def format_duration(seconds) -> str:
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return "unknown length"
    hours, rem = divmod(seconds, 3600)
    minutes = int(round(rem / 60))
    if minutes == 60:
        hours += 1
        minutes = 0
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^\w\- ]+", "", text.lower()).strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:max_len].strip("-") or "audiobook"


def describe(book: dict) -> str:
    lines = [
        f"[{book.get('id')}] {book.get('title', 'Untitled')}",
        f"    by {author_names(book)}",
        f"    {format_duration(book.get('totaltimesecs'))}"
        f" | {book.get('language', 'unknown language')}",
        f"    {book.get('url_librivox', '')}",
    ]
    return "\n".join(lines)


def download_book(book_id: str, output_dir: str = ".",
                  progress: bool = True) -> str:
    """Download the zip of MP3 chapters. Returns the saved file path."""
    book = get_book(book_id)
    zip_url = book.get("url_zip_file")
    if not zip_url:
        raise LibriVoxError(
            f"book {book_id} has no downloadable zip; listen at "
            f"{book.get('url_librivox', 'librivox.org')}")
    filename = f"{slugify(book.get('title', 'audiobook'))}-{book_id}.zip"
    import os
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, filename)
    try:
        with _open(zip_url, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress and total:
                        pct = done * 100 // total
                        print(f"\r{pct:3d}% of {_mb(total)} MB", end="",
                              file=sys.stderr, flush=True)
    except urllib.error.URLError as exc:
        raise LibriVoxError(f"download failed: {exc}") from exc
    if progress:
        print("", file=sys.stderr)
    return dest


def _mb(n: int) -> str:
    return f"{n / (1 << 20):.1f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Search and download free public-domain audiobooks from LibriVox.")
    sub = ap.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search by title and/or author")
    p_search.add_argument("title", nargs="?", help="Title (or part of it)")
    p_search.add_argument("--author", help="Author name")
    p_search.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                          help=f"Max results, 1-{MAX_LIMIT} (default {DEFAULT_LIMIT})")
    p_search.add_argument("--json", action="store_true", help="Print raw JSON")

    p_info = sub.add_parser("info", help="Show details for a book id")
    p_info.add_argument("id")
    p_info.add_argument("--json", action="store_true", help="Print raw JSON")

    p_dl = sub.add_parser("download", help="Download a book's MP3 zip by id")
    p_dl.add_argument("id")
    p_dl.add_argument("--output", default=".", help="Directory to save into")

    args = ap.parse_args(argv)

    try:
        if args.command == "search":
            books = search_books(title=args.title, author=args.author,
                                 limit=args.limit)
            if args.json:
                print(json.dumps(books, ensure_ascii=False, indent=2))
            elif not books:
                print("No results. Try a shorter title or just the author's "
                      "last name.")
            else:
                print("\n\n".join(describe(b) for b in books))
                print(f"\n{len(books)} result(s). Download with: "
                      f"python3 librivox_dl.py download <id>")
        elif args.command == "info":
            book = get_book(args.id)
            if args.json:
                print(json.dumps(book, ensure_ascii=False, indent=2))
            else:
                print(describe(book))
                if book.get("url_zip_file"):
                    print(f"    zip: {book['url_zip_file']}")
        elif args.command == "download":
            dest = download_book(args.id, output_dir=args.output)
            print(f"Saved {dest}")
    except LibriVoxError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
