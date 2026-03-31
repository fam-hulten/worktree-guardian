"""Data models for worktree information"""
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Worktree:
    path: str
    name: str
    branch: str
    issue_nr: Optional[int]
    repo: str
    last_commit: Optional[str]
    last_commit_days: int
    last_activity: Optional[str]
    last_activity_days: int
    stale: str  # green, yellow, red
    dirty: bool
    
    def activity_days(self) -> int:
        """Use the more recent of commit or activity"""
        if self.last_activity_days is not None and self.last_activity_days < 999:
            return self.last_activity_days
        return self.last_commit_days
    
    @property
    def status_emoji(self) -> str:
        return {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(self.stale, "⚪")
    
    def to_dict(self):
        return asdict(self)
