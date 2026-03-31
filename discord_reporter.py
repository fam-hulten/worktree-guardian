#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

AUDIT_LOG_PATH = Path(__file__).resolve().parent / "worktrees_cleanup_audit.jsonl"


def load_latest_event_with_candidates(path: Path) -> dict | None:
    if not path.exists():
        return None

    latest: dict | None = None
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if int(event.get("candidates_found", 0) or 0) > 0:
                    latest = event
    except OSError:
        return None

    return latest


def normalize_reason(item: dict) -> str:
    reason = item.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()

    reasons = item.get("reasons")
    if isinstance(reasons, list):
        cleaned = [str(r).strip() for r in reasons if str(r).strip()]
        if cleaned:
            return "/".join(cleaned)

    inferred: list[str] = []
    if item.get("abandoned"):
        inferred.append("abandoned")
    if item.get("merged_into_main"):
        inferred.append("merged")

    return "/".join(inferred) if inferred else "unknown"


def extract_candidates(event: dict) -> list[dict[str, str]]:
    raw_items = event.get("candidates")
    if not isinstance(raw_items, list):
        raw_items = event.get("worktrees")
    if not isinstance(raw_items, list):
        raw_items = []

    candidates: list[dict[str, str]] = []
    for item in raw_items:
        if isinstance(item, str):
            # Parse path to extract worktree name and branch
            path = item
            name = Path(path).name
            # Extract branch from worktree name pattern: studywise-api-<branchname>
            # or use "unknown" if pattern doesn't match
            branch = name.replace("studywise-api-", "") if name.startswith("studywise-api-") else name
            candidates.append({"path": path, "branch": branch, "reason": "merged/abandoned"})
            continue

        if not isinstance(item, dict):
            continue

        path = str(item.get("path") or item.get("worktree") or "unknown")
        branch = str(item.get("branch") or "unknown")
        reason = normalize_reason(item)
        candidates.append({"path": path, "branch": branch, "reason": reason})

    return candidates


def format_message(candidates: list[dict[str, str]]) -> str:
    lines = [
        "🧹 Worktree Cleanup Report",
        "",
        f"Candidates found: {len(candidates)}",
        "",
        "Worktrees:",
    ]

    for candidate in candidates:
        lines.append(
            f"- `{candidate['path']}` (branch: `{candidate['branch']}`, reason: {candidate['reason']})"
        )

    lines.extend(["", "Run with --apply to remove"])
    return "\n".join(lines)


def print_summary(event: dict | None, candidates: list[dict[str, str]]) -> None:
    if not event:
        print("No audit entry with cleanup candidates found.")
        return

    timestamp = event.get("timestamp", "unknown")
    print(f"Latest candidate report: {timestamp}")
    print(f"Candidates found: {len(candidates)}")
    for candidate in candidates:
        print(
            f"- {candidate['path']} (branch={candidate['branch']}, reason={candidate['reason']})"
        )


def post_to_discord(webhook_url: str, content: str) -> bool:
    payload = json.dumps({"content": content})
    result = subprocess.run(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            webhook_url,
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def main() -> int:
    event = load_latest_event_with_candidates(AUDIT_LOG_PATH)
    if not event:
        print_summary(None, [])
        return 0

    candidates = extract_candidates(event)
    if not candidates:
        print_summary(event, candidates)
        return 0

    webhook_url = os.environ.get("DISCORD_WEBHOOK", "").strip()
    if not webhook_url:
        print_summary(event, candidates)
        return 0

    message = format_message(candidates)
    sent = post_to_discord(webhook_url, message)
    print_summary(event, candidates)
    if sent:
        print("Discord webhook sent.")
    else:
        print("Discord webhook request failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
