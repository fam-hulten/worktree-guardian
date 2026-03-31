#!/usr/bin/env python3
"""
Worktree Guardian v2 - Enhanced CLI scanner
"""

import subprocess
import json
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

ABANDONED_DAYS = 7
WARN_DAYS = 3
PROJECTS_DIR = Path.home() / "projects"


@dataclass
class Worktree:
    name: str
    path: str
    branch: str
    issue_nr: Optional[int]
    commit: str
    status: str
    last_commit: Optional[str]
    days_since_commit: int
    abandoned: bool
    aging: bool
    staleness: str
    repo: str
    

def run_cmd(cmd, cwd=None, timeout=10):
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode
    except Exception:
        return "", -1


def is_main_repo(project_dir: Path) -> bool:
    """Check if this is a main repo (not a worktree)."""
    git_file = project_dir / ".git"
    # Main repos have .git as a directory
    # Worktrees have .git as a file pointing to parent
    return git_file.is_dir()


def parse_issue_from_branch(branch: str) -> Optional[int]:
    patterns = [r'issue[-_]?(\d+)', r'#(\d+)', r'[-_](\d+)$']
    for pattern in patterns:
        match = re.search(pattern, branch, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def get_worktree_info(wt_path: str, repo: str) -> Optional[Worktree]:
    if not Path(wt_path).exists():
        return None
    
    # Git status (dirty check)
    output, rc = run_cmd("git status --porcelain", cwd=wt_path, timeout=5)
    is_dirty = len(output.strip()) > 0 if output else False
    
    # Last commit
    output, _ = run_cmd("git log -1 --format='%ci'", cwd=wt_path, timeout=5)
    last_commit = output.strip("'") if output else None
    
    days_since_commit = 0
    if last_commit:
        try:
            commit_date = datetime.fromisoformat(last_commit.split()[0])
            days_since_commit = (datetime.now() - commit_date).days
        except (ValueError, IndexError):
            pass
    
    # Branch + issue
    output, _ = run_cmd("git rev-parse --abbrev-ref HEAD", cwd=wt_path, timeout=5)
    branch = output.strip() if output else "unknown"
    issue_nr = parse_issue_from_branch(branch)
    
    # Commit hash
    output, _ = run_cmd("git rev-parse --short HEAD", cwd=wt_path, timeout=5)
    commit_hash = output[:8] if output else "??????"
    
    # Status
    status = "dirty" if is_dirty else "clean"
    
    # Staleness
    abandoned = days_since_commit > ABANDONED_DAYS
    aging = days_since_commit > WARN_DAYS and not abandoned
    
    if abandoned:
        staleness = "red"
    elif aging:
        staleness = "yellow"
    elif is_dirty:
        staleness = "yellow"  # Active work
    else:
        staleness = "green"
    
    return Worktree(
        name=Path(wt_path).name,
        path=wt_path,
        branch=branch,
        issue_nr=issue_nr,
        commit=commit_hash,
        status=status,
        last_commit=last_commit[:10] if last_commit else None,
        days_since_commit=days_since_commit,
        abandoned=abandoned,
        aging=aging,
        staleness=staleness,
        repo=repo
    )


def scan_all_projects() -> list[Worktree]:
    worktrees = []
    if not PROJECTS_DIR.exists():
        return worktrees
    
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith('.'):
            continue
        
        # Skip worktrees - only scan main repos
        if not is_main_repo(project_dir):
            continue
        
        output, rc = run_cmd("git worktree list --porcelain", cwd=project_dir, timeout=10)
        if rc == 0 and output:
            wt_paths = []
            for line in output.split('\n'):
                if line.startswith('worktree '):
                    wt_path = line[9:].strip()
                    if wt_path:
                        wt_paths.append(wt_path)
            
            for wt_path in wt_paths:
                info = get_worktree_info(wt_path, project_dir.name)
                if info:
                    worktrees.append(info)
    
    return worktrees


def print_summary(worktrees: list[Worktree]):
    color_order = {"red": 0, "yellow": 1, "green": 2}
    worktrees.sort(key=lambda w: (color_order.get(w.staleness, 3), w.days_since_commit, w.name))
    
    print("\n" + "="*70)
    print("🌳 Worktree Guardian v2 - Status Report")
    print("="*70)
    
    total = len(worktrees)
    clean = sum(1 for w in worktrees if w.status == "clean")
    dirty = sum(1 for w in worktrees if w.status == "dirty")
    abandoned = sum(1 for w in worktrees if w.abandoned)
    aging = sum(1 for w in worktrees if w.aging)
    
    print(f"\n📊 {total} worktrees | 🟢{clean} clean | 🟡{dirty}+{aging} aging | 💀{abandoned} abandoned")
    
    if abandoned > 0:
        print(f"\n⚠️  Abandoned (>7 days):")
        for w in worktrees:
            if w.abandoned:
                issue = f" #{w.issue_nr}" if w.issue_nr else ""
                print(f"   - {w.name}{issue} ({w.branch}) - {w.days_since_commit}d inactive")
    
    print(f"\n{'St':<2} {'Worktree':<42} {'Issue':<8} {'Status':<10} {'Days'}")
    print("-"*70)
    
    for w in worktrees:
        emoji = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(w.staleness, "⚪")
        issue = f"#{w.issue_nr}" if w.issue_nr else "-"
        print(f"{emoji:<2} {w.name:<42} {issue:<8} {w.status:<10} {w.days_since_commit}")
    
    print("-"*70)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--alert", action="store_true")
    args = parser.parse_args()
    
    worktrees = scan_all_projects()
    
    if args.json:
        result = {
            "worktrees": [asdict(w) for w in worktrees],
            "summary": {
                "total": len(worktrees),
                "clean": sum(1 for w in worktrees if w.status == "clean"),
                "dirty": sum(1 for w in worktrees if w.status == "dirty"),
                "abandoned": sum(1 for w in worktrees if w.abandoned),
                "aging": sum(1 for w in worktrees if w.aging),
            },
            "generated_at": datetime.now().isoformat()
        }
        print(json.dumps(result, indent=2))
    elif args.alert:
        abandoned = [w for w in worktrees if w.abandoned]
        if abandoned:
            for w in abandoned:
                issue = f"#{w.issue_nr}" if w.issue_nr else ""
                print(f"ABANDONED: {w.name}{issue} ({w.branch}) - {w.days_since_commit}d")
    else:
        print_summary(worktrees)


if __name__ == "__main__":
    main()
