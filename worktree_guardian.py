#!/usr/bin/env python3
"""
Worktree Guardian - MVP v1.2
Lists all git worktrees with their status as JSON for dashboard consumption.
"""

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path.home() / "projects"
ABANDONED_DAYS = 30


def run_cmd(cmd, cwd=None, timeout=10):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", -1


def get_worktree_status(wt_path):
    """Get status for a single worktree."""
    if not Path(wt_path).exists():
        return None
    
    # Get git status (dirty check)
    output, rc = run_cmd("git status --porcelain", cwd=wt_path, timeout=5)
    is_dirty = len(output.strip()) > 0 if output else False
    
    # Get last commit date
    output, _ = run_cmd("git log -1 --format='%ci'", cwd=wt_path, timeout=5)
    last_commit = output.strip("'") if output else None
    
    # Parse date and calculate days since
    days_since_commit = 0
    if last_commit:
        try:
            commit_date = datetime.fromisoformat(last_commit.split()[0])
            days_since_commit = (datetime.now() - commit_date).days
        except (ValueError, IndexError):
            pass
    
    # Get branch name
    output, _ = run_cmd("git rev-parse --abbrev-ref HEAD", cwd=wt_path, timeout=5)
    branch = output.strip() if output else "unknown"
    
    # Get short hash
    output, _ = run_cmd("git rev-parse --short HEAD", cwd=wt_path, timeout=5)
    commit_hash = output[:8] if output else "??????"
    
    # Check if behind origin (outdated)
    output, _ = run_cmd("git fetch origin --quiet 2>/dev/null; git rev-list --left-right --count 'HEAD...origin/main' 2>/dev/null || echo '0 0'", cwd=wt_path, timeout=15)
    ahead, behind = 0, 0
    if output:
        parts = output.split()
        if len(parts) == 2:
            try:
                ahead, behind = int(parts[0]), int(parts[1])
            except ValueError:
                pass
    
    # Determine status
    if is_dirty:
        status = "dirty"
    elif behind > 0:
        status = "outdated"
    else:
        status = "clean"
    
    # Check if abandoned (30+ days since last commit)
    abandoned = days_since_commit > ABANDONED_DAYS
    
    return {
        "name": Path(wt_path).name,
        "path": wt_path,
        "branch": branch,
        "commit": commit_hash,
        "status": status,
        "last_commit": last_commit[:10] if last_commit else None,
        "days_since_commit": days_since_commit,
        "ahead": ahead,
        "behind": behind,
        "abandoned": abandoned
    }


def scan_projects():
    """Scan all directories in projects folder for worktrees."""
    worktrees = []
    
    if not PROJECTS_DIR.exists():
        return worktrees
    
    # Scan studywise-api for its worktrees
    main_repo = "studywise-api"
    main_path = PROJECTS_DIR / main_repo
    
    if main_path.exists():
        output, rc = run_cmd("git worktree list --porcelain", cwd=main_path, timeout=10)
        if rc == 0 and output:
            current_wt = None
            for line in output.split('\n'):
                if line.startswith('worktree '):
                    current_wt = line[9:].strip()
                elif line == '' and current_wt:
                    status = get_worktree_status(current_wt)
                    if status:
                        worktrees.append(status)
                    current_wt = None
            # Handle last entry
            if current_wt:
                status = get_worktree_status(current_wt)
                if status:
                    worktrees.append(status)
    
    return worktrees


def main():
    # Always output JSON (for dashboard)
    worktrees = scan_projects()
    
    # Sort: dirty first, then abandoned, then by name
    worktrees.sort(key=lambda x: (not x['is_dirty'] if 'is_dirty' in x else not x['status'] == 'dirty', x['abandoned'], x['name']))
    
    result = {
        "worktrees": worktrees,
        "summary": {
            "total": len(worktrees),
            "clean": sum(1 for w in worktrees if w['status'] == 'clean'),
            "dirty": sum(1 for w in worktrees if w['status'] == 'dirty'),
            "outdated": sum(1 for w in worktrees if w['status'] == 'outdated'),
            "abandoned": sum(1 for w in worktrees if w['abandoned'])
        },
        "generated_at": datetime.now().isoformat()
    }
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
