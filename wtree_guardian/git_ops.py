"""Git operations for worktree scanning"""
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from .models import Worktree

PROJECTS_DIR = Path.home() / "projects"
STALE_THRESHOLD_DAYS = 3
WARN_THRESHOLD_DAYS = 1


def is_main_repo(project_dir: Path) -> bool:
    """Check if this is a main repo (not a worktree)."""
    git_file = project_dir / ".git"
    return git_file.is_dir()


def run_cmd(cmd: str, cwd=None, timeout=10) -> tuple:
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.returncode
    except Exception:
        return "", -1


def parse_issue_from_branch(branch: str) -> Optional[int]:
    patterns = [r'issue[-_]?(\d+)', r'#(\d+)', r'[-_](\d+)$']
    for pattern in patterns:
        match = re.search(pattern, branch, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def get_last_activity(wt_path: str) -> tuple:
    """Get most recent file modification in worktree using stat."""
    try:
        output, rc = run_cmd(
            f"find . -type f -not -path './.git/*' -not -path './node_modules/*' -not -path './bin/*' -not -path './obj/*' -printf '%T@\\n' 2>/dev/null | sort -rn | head -1",
            cwd=wt_path, timeout=15
        )
        if output:
            try:
                timestamp = float(output.strip())
                activity_dt = datetime.fromtimestamp(timestamp)
                days = (datetime.now() - activity_dt).days
                return activity_dt.strftime("%Y-%m-%d %H:%M"), days
            except ValueError:
                pass
    except Exception:
        pass
    return None, 999


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
    
    # Last file activity
    last_activity, days_since_activity = get_last_activity(wt_path)
    
    # Staleness
    activity_days = days_since_activity if days_since_activity < 999 else days_since_commit
    
    if activity_days > STALE_THRESHOLD_DAYS:
        stale = "red"
    elif activity_days > WARN_THRESHOLD_DAYS:
        stale = "yellow"
    else:
        stale = "green"
    
    return Worktree(
        path=wt_path,
        name=Path(wt_path).name,
        branch=branch,
        issue_nr=issue_nr,
        repo=repo,
        last_commit=last_commit[:10] if last_commit else None,
        last_commit_days=days_since_commit,
        last_activity=last_activity,
        last_activity_days=days_since_activity,
        stale=stale,
        dirty=is_dirty
    )


def scan_all_projects() -> List[Worktree]:
    """Scan all worktrees across all projects."""
    worktrees = []
    if not PROJECTS_DIR.exists():
        return worktrees
    
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith('.'):
            continue
        if not is_main_repo(project_dir):
            continue
        
        output, rc = run_cmd("git worktree list --porcelain", cwd=project_dir, timeout=10)
        if rc == 0 and output:
            for line in output.split('\n'):
                if line.startswith('worktree '):
                    wt_path = line[9:].strip()
                    if wt_path:
                        info = get_worktree_info(wt_path, project_dir.name)
                        if info:
                            worktrees.append(info)
    
    return worktrees
