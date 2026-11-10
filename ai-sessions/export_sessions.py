"""Snapshot complete native Codex JSONL records for one working conversation."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TOKEN = re.compile(r"(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{20,}")


def redact(value, account_values, counts):
    if isinstance(value, dict):
        return {key: redact(item, account_values, counts) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, account_values, counts) for item in value]
    if not isinstance(value, str):
        return value
    for account in sorted(account_values):
        counts["account_identifier"] += value.count(account)
        value = value.replace(account, "[REDACTED:account_identifier]")
    if "@" in value:
        counts["email"] += len(EMAIL.findall(value))
        value = EMAIL.sub("[REDACTED:email]", value)
    counts["github_token"] += len(TOKEN.findall(value))
    return TOKEN.sub("[REDACTED:github_token]", value)


def read_snapshot(path):
    for attempt in range(3):
        data = path.read_bytes()
        try:
            records = [json.loads(line) for line in data.decode("utf-8").split("\n") if line]
            if not records or records[0].get("type") != "session_meta":
                raise ValueError(f"missing session metadata in {path}")
            return data, records
        except (UnicodeDecodeError, json.JSONDecodeError):
            if attempt == 2:
                raise
            time.sleep(0.2)


def export_sessions(sessions_directory, root_session, output):
    catalog = {}
    for path in sorted(sessions_directory.rglob("*.jsonl")):
        with path.open(encoding="utf-8") as source:
            first_line = source.readline()
        if not first_line.strip():
            continue
        first = json.loads(first_line)
        if first.get("type") != "session_meta":
            continue
        metadata = first["payload"]
        session_id = metadata.get("id", metadata.get("session_id"))
        if session_id:
            catalog[session_id] = (path, metadata)
    if root_session not in catalog:
        raise ValueError("root session was not found in the native session directory")

    selected = {root_session}
    while True:
        children = {
            session_id for session_id, (_, metadata) in catalog.items()
            if metadata.get("parent_thread_id") in selected and metadata.get("agent_path")
        }
        expanded = selected | children
        if expanded == selected:
            break
        selected = expanded

    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous["root_session_id"] != root_session:
            raise ValueError("output directory belongs to a different root session")

    snapshots = []
    account_values = set()
    for session_id in sorted(selected):
        path, _ = catalog[session_id]
        data, records = read_snapshot(path)
        metadata = records[0]["payload"]
        for key in ("creator_user_id", "creator_account_id"):
            if metadata.get(key):
                account_values.add(metadata[key])
        snapshots.append((path, data, records))

    files = []
    for path, original, records in snapshots:
        counts = {"account_identifier": 0, "email": 0, "github_token": 0}
        redacted_records = [redact(record, account_values, counts) for record in records]
        text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in redacted_records)
        exported = text.encode("utf-8")
        copied_records = [json.loads(line) for line in text.split("\n") if line]
        if len(copied_records) != len(records):
            raise ValueError("redaction changed the number of native records")
        destination = output / path.name
        temporary = destination.with_suffix(".jsonl.tmp")
        temporary.write_bytes(exported)
        temporary.replace(destination)
        metadata = records[0]["payload"]
        files.append({
            "file": path.name,
            "session_id": metadata.get("id", metadata.get("session_id")),
            "parent_thread_id": metadata.get("parent_thread_id"),
            "agent_path": metadata.get("agent_path", "/root"),
            "source": str(path),
            "records": len(records),
            "first_timestamp": records[0].get("timestamp"),
            "last_timestamp": records[-1].get("timestamp"),
            "last_ordinal": records[-1].get("ordinal"),
            "source_sha256": hashlib.sha256(original).hexdigest(),
            "export_sha256": hashlib.sha256(exported).hexdigest(),
            "redactions": counts,
        })

    manifest = {
        "root_session_id": root_session,
        "snapshot_time_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Full native root records and all working subagent descendants, with declared redactions.",
        "redaction_policy": "String values containing account identifiers, email addresses and recognizable GitHub tokens are redacted. Native JSON objects are re-encoded in their original order, retaining all fields and records without summaries.",
        "files": sorted(files, key=lambda item: item["first_timestamp"] or ""),
    }
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-session", required=True)
    parser.add_argument("--sessions-dir", type=Path, default=Path.home() / ".codex/sessions")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "raw")
    args = parser.parse_args()
    manifest = export_sessions(args.sessions_dir, args.root_session, args.out)
    print(json.dumps({
        "files": len(manifest["files"]),
        "records": sum(item["records"] for item in manifest["files"]),
        "snapshot_time_utc": manifest["snapshot_time_utc"],
        "manifest": str(args.out / "manifest.json"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
