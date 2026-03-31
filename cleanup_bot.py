#!/usr/bin/env python3
"""
Cleanup Bot for Worktree Guardian.

Finds abandoned, clean worktrees and optionally removes them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / "projects"
AUDIT_LOG_PATH = Path(__file__).resolve().parent / "worktrees_cleanup_audit.jsonl"


def run_cmd(cmd: str, cwd: Path | None = None, timeout: int = 10) -> tuple[str, int]:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", -1


def discover_repos(root: Path) -> list[Path]:
    if not root.exists():
        return []

    repos_by_common_dir: dict[Path, Path] = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        output, rc = run_cmd("git rev-parse --git-common-dir", cwd=child, timeout=4)
        if rc != 0 or not output:
            continue
        common_dir = Path(output)
        if not common_dir.is_absolute():
            common_dir = (child / common_dir).resolve()
        repos_by_common_dir.setdefault(common_dir, child)

    return list(repos_by_common_dir.values())


def parse_worktree_list(output: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line in output.splitlines():
        line = line.strip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        if " " in line:
            key, value = line.split(" ", 1)
            current[key] = value
        else:
            current[line] = "true"

    if current:
        entries.append(current)

    return entries


def parse_merged_branches(output: str) -> set[str]:
    branches: set[str] = set()
    for line in output.splitlines():
        branch = line.strip().lstrip("* ").strip()
        if not branch or "->" in branch:
            continue
        if branch.startswith("remotes/"):
            parts = branch.split("/", 2)
            if len(parts) == 3:
                branch = parts[2]
        branches.add(branch)
    return branches


def get_merged_branches(repo_root: Path) -> set[str]:
    merged_out, rc = run_cmd("git branch -a --merged main", cwd=repo_root, timeout=8)
    if rc != 0:
        merged_out, rc = run_cmd(
            "git branch -a --merged master", cwd=repo_root, timeout=8
        )
    if rc != 0:
        return set()
    return parse_merged_branches(merged_out)


def get_worktree_info(
    repo_root: Path, wt_path: Path, abandoned_days: int, merged_branches: set[str]
) -> dict:
    status_out, _ = run_cmd("git status --porcelain", cwd=wt_path, timeout=5)
    is_dirty = bool(status_out)

    ts_out, _ = run_cmd("git log -1 --format=%ct", cwd=wt_path, timeout=5)
    days_since_commit = 0
    if ts_out:
        try:
            commit_dt = datetime.fromtimestamp(int(ts_out))
            days_since_commit = (datetime.now() - commit_dt).days
        except ValueError:
            pass

    branch_out, _ = run_cmd("git rev-parse --abbrev-ref HEAD", cwd=wt_path, timeout=5)
    branch = branch_out or "unknown"

    ahead_behind_out, _ = run_cmd(
        "git rev-list --left-right --count HEAD...@{upstream} 2>/dev/null || echo '0 0'",
        cwd=wt_path,
        timeout=5,
    )
    ahead, behind = 0, 0
    parts = ahead_behind_out.split()
    if len(parts) == 2:
        try:
            ahead, behind = int(parts[0]), int(parts[1])
        except ValueError:
            pass

    if is_dirty:
        status = "dirty"
    elif behind > 0:
        status = "outdated"
    else:
        status = "clean"

    is_abandoned = days_since_commit >= abandoned_days
    merged_into_main = branch in merged_branches
    is_main = wt_path.resolve() == repo_root.resolve()
    cleanup_candidate = (
        (not is_main) and (not is_dirty) and (is_abandoned or merged_into_main)
    )

    return {
        "repo_root": repo_root,
        "path": wt_path,
        "branch": branch,
        "status": status,
        "ahead": ahead,
        "behind": behind,
        "days_since_commit": days_since_commit,
        "abandoned": is_abandoned,
        "merged_into_main": merged_into_main,
        "is_main": is_main,
        "cleanup_candidate": cleanup_candidate,
    }


def collect_worktrees(projects_dir: Path, abandoned_days: int) -> list[dict]:
    records: list[dict] = []
    for repo_root in discover_repos(projects_dir):
        merged_branches = get_merged_branches(repo_root)
        output, rc = run_cmd("git worktree list --porcelain", cwd=repo_root, timeout=10)
        if rc != 0 or not output:
            continue
        for entry in parse_worktree_list(output):
            wt = entry.get("worktree")
            if not wt:
                continue
            wt_path = Path(wt)
            if not wt_path.exists():
                continue
            records.append(
                get_worktree_info(repo_root, wt_path, abandoned_days, merged_branches)
            )
    return records


def append_audit_log(
    action: str, candidates_found: int, candidates_removed: int, worktrees: list[str]
) -> None:
    event = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "action": action,
        "candidates_found": candidates_found,
        "candidates_removed": candidates_removed,
        "worktrees": worktrees,
    }
    try:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError as exc:
        print(f"failed to append audit log: {exc}", file=sys.stderr)


def remove_candidates(candidates: list[dict], force: bool = False) -> int:
    removed = 0
    for rec in candidates:
        cmd = f'git worktree remove {"--force " if force else ""}"{rec["path"]}"'
        _, rc = run_cmd(cmd, cwd=rec["repo_root"], timeout=20)
        if rc == 0:
            removed += 1
        else:
            print(f"failed: {rec['path']}", file=sys.stderr)
    return removed


def print_report(records: list[dict], candidates: list[dict], dry_run: bool) -> None:
    print(f"Projects dir: {PROJECTS_DIR}")
    print(f"Worktrees scanned: {len(records)}")
    print(f"Cleanup candidates: {len(candidates)}")
    print()

    if not candidates:
        print("No cleanup candidates found.")
        return

    for rec in sorted(candidates, key=lambda r: str(r["path"])):
        reasons: list[str] = []
        if rec["abandoned"]:
            reasons.append("abandoned")
        if rec["merged_into_main"]:
            reasons.append("merged")
        reason_text = "/".join(reasons) if reasons else "unknown"
        print(
            f"- {rec['path']} (branch={rec['branch']}, days={rec['days_since_commit']}, status={rec['status']}, why={reason_text})"
        )

    print()
    if dry_run:
        print("Dry run only. Re-run with --apply to remove these worktrees.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cleanup abandoned, clean git worktrees."
    )
    parser.add_argument(
        "--days", type=int, default=30, help="abandoned threshold in days (default: 30)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="actually remove candidate worktrees"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="force removal (passed to git worktree remove)",
    )
    args = parser.parse_args()

    records = collect_worktrees(PROJECTS_DIR, args.days)
    candidates = [r for r in records if r["cleanup_candidate"]]
    candidate_paths = [str(r["path"]) for r in candidates]

    append_audit_log(
        action="scanned",
        candidates_found=len(candidates),
        candidates_removed=0,
        worktrees=[str(r["path"]) for r in records],
    )

    print_report(records, candidates, dry_run=not args.apply)

    if args.apply and candidates:
        removed = remove_candidates(candidates, force=args.force)
        append_audit_log(
            action="removed",
            candidates_found=len(candidates),
            candidates_removed=removed,
            worktrees=candidate_paths,
        )
        print()
        print(f"Removed {removed}/{len(candidates)} worktrees")
    else:
        append_audit_log(
            action="dry_run",
            candidates_found=len(candidates),
            candidates_removed=0,
            worktrees=candidate_paths,
        )


if __name__ == "__main__":
    main()
