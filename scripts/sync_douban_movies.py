#!/usr/bin/env python3
"""Create the portfolio's local Douban movie snapshot.

The script intentionally uses only Python's standard library. It reads the
public "watched" pages, stores only portfolio-safe fields, and asks Douban's
image CDN for WebP variants of poster files.
"""

from __future__ import annotations

import argparse
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
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


@dataclass
class ParsedMovie:
    id: str
    title: str
    cover_url: str
    rating: int | None
    watched_at: str
    comment: str


class CollectPageParser(HTMLParser):
    """Small, dependency-free parser scoped to Douban's collection markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.movies: list[ParsedMovie] = []
        self.total: int | None = None
        self._tags: list[tuple[str, set[str], str | None]] = []
        self._movie: dict[str, object] | None = None
        self._movie_depth = 0
        self._capture: str | None = None
        self._capture_tag: str | None = None
        self._capture_parts: list[str] = []
        self._subject_num_parts: list[str] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key: value or "" for key, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self._attrs(attrs)
        classes = set(values.get("class", "").split())

        if self._movie is None and tag == "div" and {"item", "comment-item"}.issubset(classes):
            self._movie = {
                "id": "",
                "title": "",
                "cover_url": "",
                "rating": None,
                "watched_at": "",
                "comment": "",
            }
            self._movie_depth = 1
        elif self._movie is not None and tag not in VOID_TAGS:
            self._movie_depth += 1

        if self._movie is not None:
            if tag == "a":
                match = re.search(r"/subject/(\d+)/?", values.get("href", ""))
                if match and not self._movie["id"]:
                    self._movie["id"] = match.group(1)
            elif tag == "img" and "pic" in {c for _, cs, _ in self._tags for c in cs}:
                self._movie["cover_url"] = values.get("src", "")

            field: str | None = None
            if tag == "em" and any(t == "li" and "title" in cs for t, cs, _ in self._tags):
                field = "title"
            elif tag == "span" and "date" in classes:
                field = "watched_at"
            elif tag == "span" and "comment" in classes:
                field = "comment"
            if field:
                self._capture = field
                self._capture_tag = tag
                self._capture_parts = []

            for class_name in classes:
                match = re.fullmatch(r"rating([1-5])-t", class_name)
                if match:
                    self._movie["rating"] = int(match.group(1))

        if tag == "span" and "subject-num" in classes:
            self._capture = "subject_num"
            self._capture_tag = tag
            self._capture_parts = []

        if tag not in VOID_TAGS:
            self._tags.append((tag, classes, self._capture))

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag == self._capture_tag:
            value = " ".join("".join(self._capture_parts).split())
            if self._capture == "subject_num":
                self._subject_num_parts.append(value)
                numbers = re.findall(r"\d+", value.replace(",", ""))
                if numbers:
                    self.total = int(numbers[-1])
            elif self._movie is not None:
                self._movie[self._capture] = value
            self._capture = None
            self._capture_tag = None
            self._capture_parts = []

        if self._movie is not None:
            self._movie_depth -= 1
            if self._movie_depth == 0:
                raw = self._movie
                self.movies.append(
                    ParsedMovie(
                        id=str(raw["id"]),
                        title=str(raw["title"]),
                        cover_url=str(raw["cover_url"]),
                        rating=raw["rating"] if isinstance(raw["rating"], int) else None,
                        watched_at=str(raw["watched_at"]),
                        comment=str(raw["comment"]),
                    )
                )
                self._movie = None

        for index in range(len(self._tags) - 1, -1, -1):
            if self._tags[index][0] == tag:
                del self._tags[index:]
                break


def request_bytes(url: str, *, attempts: int = 3) -> tuple[bytes, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://movie.douban.com/",
        "Accept": "text/html,application/xhtml+xml,image/webp,image/*;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
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
    query = urllib.parse.urlencode(
        {"start": start, "sort": "time", "rating": "all", "filter": "all", "mode": "grid"}
    )
    return f"https://movie.douban.com/people/{profile_id}/collect?{query}"


def parse_page(payload: bytes) -> CollectPageParser:
    parser = CollectPageParser()
    parser.feed(payload.decode("utf-8", errors="strict"))
    parser.close()
    return parser


def validate_movies(movies: Iterable[ParsedMovie], expected_total: int) -> list[ParsedMovie]:
    result = list(movies)
    if len(result) != expected_total:
        raise ValueError(f"expected {expected_total} movies, parsed {len(result)}")
    ids = [movie.id for movie in result]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate movie IDs found")
    for movie in result:
        if not movie.id or not movie.title or not movie.cover_url:
            raise ValueError(f"missing required field in movie {movie!r}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", movie.watched_at):
            raise ValueError(f"invalid watched date for {movie.id}: {movie.watched_at!r}")
        if movie.rating is not None and movie.rating not in range(1, 6):
            raise ValueError(f"invalid rating for {movie.id}: {movie.rating!r}")
    return result


def webp_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = re.sub(r"\.(?:jpe?g|png)$", ".webp", parsed.path, flags=re.IGNORECASE)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def is_webp(payload: bytes) -> bool:
    return len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"


def download_cover(movie: ParsedMovie, covers_dir: Path) -> tuple[bool, bool]:
    destination = covers_dir / f"{movie.id}.webp"
    if destination.exists() and is_webp(destination.read_bytes()[:16]):
        return True, True

    payload, content_type = request_bytes(webp_url(movie.cover_url))
    if not is_webp(payload) or "webp" not in content_type.lower():
        raise ValueError(f"CDN did not return WebP for movie {movie.id}")
    temporary = destination.with_suffix(".webp.part")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)
    return True, False


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", default=PROFILE_ID)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="seconds between collection pages")
    parser.add_argument("--expected-total", type=int, help="abort unless the remote total matches")
    parser.add_argument("--skip-covers", action="store_true", help="refresh JSON without downloading posters")
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[1]
    data_dir = repository / "assets" / "douban"
    covers_dir = data_dir / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)

    first_payload, _ = request_bytes(collect_url(args.profile_id, 0))
    first_page = parse_page(first_payload)
    if first_page.total is None:
        raise RuntimeError("could not find the remote collection total; page may require login")
    remote_total = first_page.total
    if args.expected_total is not None and remote_total != args.expected_total:
        raise RuntimeError(f"remote total is {remote_total}, expected {args.expected_total}")

    movies = list(first_page.movies)
    for start in range(PAGE_SIZE, remote_total, PAGE_SIZE):
        time.sleep(max(0.0, args.delay))
        page_payload, _ = request_bytes(collect_url(args.profile_id, start))
        page = parse_page(page_payload)
        if not page.movies:
            raise RuntimeError(f"no movies found on page starting at {start}")
        movies.extend(page.movies)
        print(f"collection: {min(len(movies), remote_total)}/{remote_total}", flush=True)

    movies = validate_movies(movies, remote_total)
    downloaded = cached = failed = 0
    if not args.skip_covers:
        for index, movie in enumerate(movies, 1):
            downloaded_this = False
            try:
                _, was_cached = download_cover(movie, covers_dir)
                if was_cached:
                    cached += 1
                else:
                    downloaded += 1
                    downloaded_this = True
            except Exception as error:
                failed += 1
                print(f"cover warning: {movie.id}: {error}", file=sys.stderr)
            if index % 20 == 0 or index == remote_total:
                print(f"covers: {index}/{remote_total}", flush=True)
            if downloaded_this:
                time.sleep(0.12)

    public_movies = [
        {
            "id": movie.id,
            "title": html.unescape(movie.title),
            "cover": f"assets/douban/covers/{movie.id}.webp",
            "rating": movie.rating,
            "watchedAt": movie.watched_at,
            "comment": html.unescape(movie.comment),
        }
        for movie in movies
    ]
    snapshot = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "total": remote_total,
        "movies": public_movies,
    }
    atomic_write_json(data_dir / "movies.json", snapshot)

    with_comment = sum(bool(movie.comment.strip()) for movie in movies)
    without_comment = remote_total - with_comment
    print(
        "done: "
        f"total={remote_total} comments={with_comment} no_comments={without_comment} "
        f"covers_downloaded={downloaded} covers_cached={cached} covers_failed={failed}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
