"""Textual TUI for Worktree Guardian"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Tree
from textual.containers import Container, ScrollableContainer
from textual.binding import Binding
from textual import events
from typing import List
from .models import Worktree
from .git_ops import scan_all_projects


class WorktreeItem(Static):
    """A single worktree display item."""
    
    def __init__(self, wt: Worktree):
        super().__init__()
        self.wt = wt
    
    def compose(self) -> ComposeResult:
        emoji = self.wt.status_emoji
        issue = f"#{self.wt.issue_nr}" if self.wt.issue_nr else ""
        
        with self.border鋼材:
            yield Static(f"{emoji} {self.wt.name} {issue}", classes="wt-name")
            yield Static(f"   Branch: {self.wt.branch}", classes="wt-detail")
            
            commit_str = self.wt.last_commit or "?"
            yield Static(f"   Commit: {commit_str} ({self.wt.last_commit_days}d)", classes="wt-detail")
            
            activity_str = self.wt.last_activity or "?"
            activity_days = self.wt.activity_days()
            yield Static(f"   Activity: {activity_str} ({activity_days}d)", classes="wt-detail")
            
            if self.wt.dirty:
                yield Static("   Status: 🟡 DIRTY", classes="wt-dirty")
            else:
                yield Static(f"   Status: {self.wt.stale.upper()}", classes=f"wt-{self.wt.stale}")


class WorktreeGuardianTUI(App):
    """Main TUI application."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #header {
        height: 3;
        background: $primary;
        color: $text;
        dock: top;
    }
    
    #stats {
        height: 3;
        background: $surface;
        border-bottom: solid $primary;
        padding: 1;
    }
    
    #worktrees {
        height: 1fr;
        scrollbar-size: 1;
    }
    
    .wt-item {
        height: auto;
        border: solid $primary;
        margin: 1;
        padding: 1;
        background: $surface;
    }
    
    .wt-name {
        text-style: bold;
        color: $text;
    }
    
    .wt-detail {
        color: $text-muted;
    }
    
    .wt-green {
        color: #4CAF50;
        text-style: bold;
    }
    
    .wt-yellow {
        color: #FFC107;
        text-style: bold;
    }
    
    .wt-red {
        color: #F44336;
        text-style: bold;
    }
    
    .wt-dirty {
        color: #2196F3;
        text-style: bold;
    }
    
    #footer {
        dock: bottom;
        background: $primary;
        color: $text;
    }
    
    .stat-green {
        color: #4CAF50;
    }
    
    .stat-yellow {
        color: #FFC107;
    }
    
    .stat-red {
        color: #F44336;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j", "cursor_down", "Down"),
        Binding("k", "cursor_up", "Up"),
        Binding("r", "refresh", "Refresh"),
    ]
    
    def __init__(self):
        super().__init__()
        self.worktrees: List[Worktree] = []
        self.filter = "all"  # all, green, yellow, red
    
    def compose(self) -> ComposeResult:
        yield Header(id="header")
        yield Static("", id="stats")
        yield ScrollableContainer(id="worktrees")
        yield Footer()
    
    def on_mount(self) -> None:
        self.title = "🌳 Worktree Guardian"
        self.sub_title = "Git worktree monitoring"
        self.refresh_worktrees()
    
    def refresh_worktrees(self) -> None:
        """Scan and display worktrees."""
        self.worktrees = scan_all_projects()
        self.update_display()
    
    def update_display(self) -> None:
        """Update the stats and worktree list."""
        # Calculate stats
        green = sum(1 for w in self.worktrees if w.stale == "green")
        yellow = sum(1 for w in self.worktrees if w.stale == "yellow")
        red = sum(1 for w in self.worktrees if w.stale == "red")
        dirty = sum(1 for w in self.worktrees if w.dirty)
        
        stats = self.query_one("#stats", Static)
        stats.update(
            f"📊 Total: {len(self.worktrees)} | "
            f"🟢{green} | 🟡{yellow} | 🔴{red} | "
            f"⚠️ {dirty} dirty"
        )
        
        # Filter worktrees
        filtered = self.worktrees
        if self.filter == "green":
            filtered = [w for w in self.worktrees if w.stale == "green"]
        elif self.filter == "yellow":
            filtered = [w for w in self.worktrees if w.stale == "yellow"]
        elif self.filter == "red":
            filtered = [w for w in self.worktrees if w.stale == "red"]
        
        # Sort: red first, then yellow, then green
        color_order = {"red": 0, "yellow": 1, "green": 2}
        filtered.sort(key=lambda w: (color_order.get(w.stale, 3), w.activity_days(), w.name))
        
        # Display worktrees
        container = self.query_one("#worktrees", ScrollableContainer)
        container.remove_children()
        
        for wt in filtered:
            item = WorktreeItem(wt)
            container.mount(item)
    
    def action_refresh(self) -> None:
        self.refresh_worktrees()
    
    def action_cursor_down(self) -> None:
        """Move cursor down in the list."""
        # Simple scroll for now
        container = self.query_one("#worktrees", ScrollableContainer)
        container.scroll_down(animate=True)
    
    def action_cursor_up(self) -> None:
        """Move cursor up in the list."""
        container = self.query_one("#worktrees", ScrollableContainer)
        container.scroll_up(animate=True)
