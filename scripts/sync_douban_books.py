#!/usr/bin/env python3
"""Create the portfolio's local Douban reading snapshot.

The default mode reads the public "read" pages with Python's standard
library. Pass --cdp-target when the collection requires the login state of a
browser connected through the local web-access proxy.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


PROFILE_ID = "220748819"
PAGE_SIZE = 15
DEFAULT_DELAY = 1.0
CDP_PROXY = "http://localhost:3456"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


@dataclass
class ParsedBook:
    id: str
    title: str
    cover_url: str
    rating: int | None
    read_at: str
    comment: str
    publication: str


class CollectPageParser(HTMLParser):
    """Dependency-free parser scoped to Douban Book collection markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.books: list[ParsedBook] = []
        self.total: int | None = None
        self._tags: list[tuple[str, set[str]]] = []
        self._book: dict[str, object] | None = None
        self._book_depth = 0
        self._capture: str | None = None
        self._capture_tag: str | None = None
        self._capture_parts: list[str] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self._attrs(attrs)
        classes = set(values.get("class", "").split())

        if self._book is None and tag == "li" and "subject-item" in classes:
            self._book = {"id": "", "title": "", "cover_url": "", "rating": None, "read_at": "", "comment": "", "publication": ""}
            self._book_depth = 1
        elif self._book is not None and tag not in VOID_TAGS:
            self._book_depth += 1

        if self._book is not None:
            if tag == "a":
                match = re.search(r"/subject/(\d+)/?", values.get("href", ""))
                if match and not self._book["id"]:
                    self._book["id"] = match.group(1)
            elif tag == "img" and any("pic" in parent_classes for _, parent_classes in self._tags):
                self._book["cover_url"] = values.get("src", "")

            field: str | None = None
            if tag == "a" and any(parent_tag == "h2" for parent_tag, _ in self._tags):
                field = "title"
            elif tag == "div" and "pub" in classes:
                field = "publication"
            elif tag == "span" and "date" in classes:
                field = "read_at"
            elif tag == "p" and "comment" in classes:
                field = "comment"
            if field:
                self._capture = field
                self._capture_tag = tag
                self._capture_parts = []

            for class_name in classes:
                match = re.fullmatch(r"rating([1-5])-t", class_name)
                if match:
                    self._book["rating"] = int(match.group(1))

        if tag == "h1" and self._book is None:
            self._capture = "total"
            self._capture_tag = tag
            self._capture_parts = []

        if tag not in VOID_TAGS:
            self._tags.append((tag, classes))

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag == self._capture_tag:
            value = " ".join("".join(self._capture_parts).split())
            if self._capture == "total":
                numbers = re.findall(r"\d+", value)
                if numbers:
                    self.total = int(numbers[-1])
            elif self._book is not None:
                if self._capture == "read_at":
                    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
                    value = match.group(0) if match else ""
                self._book[self._capture] = value
            self._capture = None
            self._capture_tag = None
            self._capture_parts = []

        if self._book is not None:
            self._book_depth -= 1
            if self._book_depth == 0:
                raw = self._book
                self.books.append(ParsedBook(
                    id=str(raw["id"]), title=str(raw["title"]), cover_url=str(raw["cover_url"]),
                    rating=raw["rating"] if isinstance(raw["rating"], int) else None,
                    read_at=str(raw["read_at"]), comment=str(raw["comment"]), publication=str(raw["publication"]),
                ))
                self._book = None

        for index in range(len(self._tags) - 1, -1, -1):
            if self._tags[index][0] == tag:
                del self._tags[index:]
                break


def request_bytes(url: str, *, attempts: int = 3) -> tuple[bytes, str]:
    headers = {"User-Agent": USER_AGENT, "Referer": "https://book.douban.com/", "Accept": "text/html,application/xhtml+xml,image/webp,image/*;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"}
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read(), response.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed after {attempts} attempts: {url}") from last_error


def collect_url(profile_id: str, start: int) -> str:
    query = urllib.parse.urlencode({"start": start, "sort": "time", "rating": "all", "filter": "all", "mode": "grid"})
    return f"https://book.douban.com/people/{profile_id}/collect?{query}"


def parse_page(payload: bytes) -> CollectPageParser:
    parser = CollectPageParser()
    parser.feed(payload.decode("utf-8", errors="strict"))
    parser.close()
    return parser


def cdp_call(path: str, body: str | None = None) -> object:
    request = urllib.request.Request(f"{CDP_PROXY}{path}", data=body.encode("utf-8") if body is not None else None, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"CDP proxy error: {payload['error']}")
    return payload.get("value", payload)


BOOK_EXTRACT_JS = r"""JSON.stringify([...document.querySelectorAll('.subject-item')].map(item=>{const a=item.querySelector('.info h2 a');const href=a?.href||'';const m=href.match(/\/subject\/(\d+)/);const rc=[...(item.querySelector('.short-note div')?.querySelector('span')?.classList||[])].find(c=>/^rating[1-5]-t$/.test(c))||'';return{id:m?m[1]:'',title:(a?.textContent||'').replace(/\s+/g,' ').trim(),coverUrl:item.querySelector('.pic img')?.src||'',rating:rc?Number(rc[6]):null,readAt:(item.querySelector('.date')?.textContent||'').match(/\d{4}-\d{2}-\d{2}/)?.[0]||'',comment:(item.querySelector('.comment')?.textContent||'').replace(/\s+/g,' ').trim(),publication:(item.querySelector('.pub')?.textContent||'').replace(/\s+/g,' ').trim()}}))"""


def collect_with_cdp(target: str, profile_id: str, expected_total: int) -> list[ParsedBook]:
    books: list[ParsedBook] = []
    for start in range(0, expected_total, PAGE_SIZE):
        cdp_call(f"/navigate?target={target}", collect_url(profile_id, start))
        rows = json.loads(str(cdp_call(f"/eval?target={target}", BOOK_EXTRACT_JS)))
        books.extend(ParsedBook(id=str(row["id"]), title=str(row["title"]), cover_url=str(row["coverUrl"]), rating=row["rating"] if isinstance(row["rating"], int) else None, read_at=str(row["readAt"]), comment=str(row["comment"]), publication=str(row["publication"])) for row in rows)
        print(f"collection: {min(len(books), expected_total)}/{expected_total}", flush=True)
    return books


def validate_books(books: Iterable[ParsedBook], expected_total: int) -> list[ParsedBook]:
    result = list(books)
    if len(result) != expected_total:
        raise ValueError(f"expected {expected_total} books, parsed {len(result)}")
    ids = [book.id for book in result]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate book IDs found")
    for book in result:
        if not book.id or not book.title or not book.cover_url:
            raise ValueError(f"missing required field in book {book!r}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", book.read_at):
            raise ValueError(f"invalid read date for {book.id}: {book.read_at!r}")
        if book.rating is not None and book.rating not in range(1, 6):
            raise ValueError(f"invalid rating for {book.id}: {book.rating!r}")
    return result


def webp_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = re.sub(r"\.(?:jpe?g|png)$", ".webp", parsed.path, flags=re.IGNORECASE)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def is_webp(payload: bytes) -> bool:
    return len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"


def download_cover(book: ParsedBook, covers_dir: Path, cdp_target: str | None) -> tuple[bool, bool]:
    destination = covers_dir / f"{book.id}.webp"
    if destination.exists() and is_webp(destination.read_bytes()[:16]):
        return True, True
    url = webp_url(book.cover_url)
    if cdp_target:
        expression = "(async()=>{const r=await fetch(" + json.dumps(url) + ",{credentials:'omit'});const b=new Uint8Array(await r.arrayBuffer());let s='';for(let i=0;i<b.length;i+=8192)s+=String.fromCharCode(...b.subarray(i,i+8192));return JSON.stringify({ok:r.ok,type:r.headers.get('content-type'),data:btoa(s)})})()"
        result = json.loads(str(cdp_call(f"/eval?target={cdp_target}", expression)))
        payload = base64.b64decode(result["data"])
        content_type = str(result["type"] or "")
    else:
        payload, content_type = request_bytes(url)
    if not is_webp(payload) or "webp" not in content_type.lower():
        raise ValueError(f"CDN did not return WebP for book {book.id}")
    temporary = destination.with_suffix(".webp.part")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)
    return True, False


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", default=PROFILE_ID)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="seconds between collection pages")
    parser.add_argument("--expected-total", type=int, help="abort unless the remote total matches")
    parser.add_argument("--skip-covers", action="store_true", help="refresh JSON without downloading covers")
    parser.add_argument("--cdp-target", help="read through an existing web-access browser target")
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[1]
    data_dir = repository / "assets" / "douban"
    covers_dir = data_dir / "book-covers"
    covers_dir.mkdir(parents=True, exist_ok=True)

    if args.cdp_target:
        if args.expected_total is None:
            raise RuntimeError("--expected-total is required with --cdp-target")
        remote_total = args.expected_total
        books = collect_with_cdp(args.cdp_target, args.profile_id, remote_total)
    else:
        first_page = parse_page(request_bytes(collect_url(args.profile_id, 0))[0])
        if first_page.total is None:
            raise RuntimeError("could not find the remote collection total; page may require login")
        remote_total = first_page.total
        if args.expected_total is not None and remote_total != args.expected_total:
            raise RuntimeError(f"remote total is {remote_total}, expected {args.expected_total}")
        books = list(first_page.books)
        for start in range(PAGE_SIZE, remote_total, PAGE_SIZE):
            time.sleep(max(0.0, args.delay))
            page = parse_page(request_bytes(collect_url(args.profile_id, start))[0])
            if not page.books:
                raise RuntimeError(f"no books found on page starting at {start}")
            books.extend(page.books)
            print(f"collection: {min(len(books), remote_total)}/{remote_total}", flush=True)

    books = validate_books(books, remote_total)
    downloaded = cached = failed = 0
    if not args.skip_covers:
        for index, book in enumerate(books, 1):
            try:
                _, was_cached = download_cover(book, covers_dir, args.cdp_target)
                cached += int(was_cached)
                downloaded += int(not was_cached)
            except Exception as error:
                failed += 1
                print(f"cover warning: {book.id}: {error}", file=sys.stderr)
            print(f"covers: {index}/{remote_total}", flush=True)
            if not args.cdp_target:
                time.sleep(0.12)

    public_books = [{"id": book.id, "title": html.unescape(book.title), "cover": f"assets/douban/book-covers/{book.id}.webp", "rating": book.rating, "readAt": book.read_at, "comment": html.unescape(book.comment), "publication": html.unescape(book.publication)} for book in books]
    snapshot = {"generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"), "total": remote_total, "books": public_books}
    atomic_write_json(data_dir / "books.json", snapshot)
    with_comment = sum(bool(book.comment.strip()) for book in books)
    print(f"done: total={remote_total} comments={with_comment} no_comments={remote_total-with_comment} covers_downloaded={downloaded} covers_cached={cached} covers_failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
