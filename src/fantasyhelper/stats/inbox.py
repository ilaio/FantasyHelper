"""Import prepared CSV files from data/inbox. One file is one transaction."""

import csv
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from fantasyhelper.db import connect
from fantasyhelper.stats.names import canonical_name_key
from fantasyhelper.stats.store import (
    PROJECTION_HEADER,
    PROJECTION_OPTIONAL,
    STATS_HEADER,
    STATS_OPTIONAL,
    ensure_schema,
    file_imported,
    inbox_directory,
    stats_season_imported,
    write_projection,
    write_stats,
)

_STATS_NAME = re.compile(r"^stats-(\d{4}-\d{2})\.csv$")
_PROJECTION_NAME = re.compile(r"^projection-(\d{4}-\d{2})-([a-z0-9]+)\.csv$")
_TEXT_COLUMNS = frozenset({"team", "positions"})


class InboxFileError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ImportReport:
    imported: tuple[str, ...]
    refused: tuple[str, ...]


@dataclass(frozen=True)
class _InboxFile:
    path: Path
    kind: str
    season: str
    source: str


def import_inbox() -> ImportReport:
    """Import inbox CSVs that are not already in import_log.

    Stats files are imported before projection files, and each group is
    imported by file name. The display name comes from the file that
    creates the player. A later file does not rename them.
    """
    inbox = inbox_directory()
    if not inbox.is_dir():
        return ImportReport(
            imported=(),
            refused=("There is no data/inbox/ folder. Add prepared CSV files there.",),
        )

    imported: list[str] = []
    refused: list[str] = []
    conn = connect()
    try:
        ensure_schema(conn)
        for path in _csv_files(inbox):
            _import_one(conn, path, imported, refused)
    finally:
        conn.close()
    return ImportReport(tuple(imported), tuple(refused))


def _csv_files(inbox: Path) -> list[Path]:
    files = [path for path in inbox.iterdir() if path.is_file() and path.suffix.lower() == ".csv"]
    return sorted(files, key=lambda path: (_sort_group(path), path.name))


def _sort_group(path: Path) -> int:
    identified = _identify(path)
    if identified is None:
        return 2
    if identified.kind == "stats":
        return 0
    return 1


def _identify(path: Path) -> _InboxFile | None:
    stats = _STATS_NAME.fullmatch(path.name)
    if stats is not None:
        return _InboxFile(path, "stats", stats.group(1), "")
    projection = _PROJECTION_NAME.fullmatch(path.name)
    if projection is not None:
        return _InboxFile(path, "projection", projection.group(1), projection.group(2))
    return None


def _import_one(
    conn: sqlite3.Connection,
    path: Path,
    imported: list[str],
    refused: list[str],
) -> None:
    identified = _identify(path)
    if identified is None:
        refused.append(_refused(path.name, _bad_name_reason()))
        return
    if file_imported(conn, path.name):
        return
    if identified.kind == "stats" and stats_season_imported(conn, identified.season):
        refused.append(
            _refused(
                path.name,
                f"A stats file for {identified.season} is already imported.",
            )
        )
        return

    header = STATS_HEADER if identified.kind == "stats" else PROJECTION_HEADER
    optional = STATS_OPTIONAL if identified.kind == "stats" else PROJECTION_OPTIONAL
    kind_label = "stats" if identified.kind == "stats" else "projection"
    try:
        rows = _parse_file(path, header, optional, kind_label)
        if identified.kind == "stats":
            write_stats(conn, path.name, identified.season, rows)
        else:
            write_projection(conn, path.name, identified.season, identified.source, rows)
    except InboxFileError as exc:
        refused.append(_refused(path.name, exc.reason))
        return
    except (OSError, UnicodeError, csv.Error) as exc:
        refused.append(_refused(path.name, f"The file could not be read ({exc})."))
        return
    except sqlite3.Error as exc:
        refused.append(_refused(path.name, f"The file could not be saved ({exc})."))
        return
    imported.append(f"Imported {path.name} ({len(rows)} players).")


def _parse_file(
    path: Path,
    header: tuple[str, ...],
    optional: frozenset[str],
    kind_label: str,
) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        found = tuple(reader.fieldnames or ())
        if found != header:
            raise InboxFileError(f"The header does not match the {kind_label} columns.")
        rows: list[dict[str, object]] = []
        seen: dict[str, str] = {}
        for number, raw in enumerate(reader, start=2):
            if _blank_row(raw, header):
                continue
            row = _parse_row(number, raw, header, optional)
            key = str(row["name_key"])
            if key in seen:
                raise InboxFileError(
                    f"Two players share the key {key} ({seen[key]} and {row['name']})."
                )
            seen[key] = str(row["name"])
            rows.append(row)
        return rows


def _blank_row(raw: dict[str, str | None], header: tuple[str, ...]) -> bool:
    return all(_text(raw, column) == "" for column in header)


def _parse_row(
    number: int,
    raw: dict[str, str | None],
    header: tuple[str, ...],
    optional: frozenset[str],
) -> dict[str, object]:
    if raw.get(None):
        raise InboxFileError(f"Row {number} has extra columns.")
    name = _text(raw, "name")
    if name == "":
        raise InboxFileError(f"Row {number}: the name is blank.")
    key = canonical_name_key(name)
    if key == "":
        raise InboxFileError(f"Row {number} ({name}): the name does not produce a match key.")

    row: dict[str, object] = {"name": name, "name_key": key}
    for column in header:
        if column == "name":
            continue
        text = _text(raw, column)
        if column in _TEXT_COLUMNS:
            row[column] = text
            continue
        if text == "":
            if column in optional:
                row[column] = None
                continue
            raise InboxFileError(f"Row {number} ({name}): {column} is missing.")
        try:
            value = float(text)
        except ValueError:
            raise InboxFileError(
                f"Row {number} ({name}): {column} is not a number."
            ) from None
        if not math.isfinite(value):
            raise InboxFileError(f"Row {number} ({name}): {column} is not a number.")
        row[column] = value
    return row


def _text(raw: dict[str, str | None], column: str) -> str:
    value = raw.get(column)
    if value is None:
        return ""
    return value.strip()


def _bad_name_reason() -> str:
    return (
        "The file name has to be stats-<season>.csv "
        "or projection-<season>-<source>.csv."
    )


def _refused(file_name: str, reason: str) -> str:
    return f"{file_name} was not imported. {reason}"
