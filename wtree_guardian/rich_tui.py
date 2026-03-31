"""Simple TUI using Rich (no extra install needed)"""
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
import time
from .git_ops import scan_all_projects

console = Console()


def create_table(worktrees, title="Worktrees"):
    """Create a rich table from worktrees."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("St", style="bold", width=3)
    table.add_column("Name", style="cyan", width=35)
    table.add_column("Issue", width=8)
    table.add_column("Branch", width=35)
    table.add_column("Activity", justify="right", width=10)
    table.add_column("Status", width=10)
    
    # Sort by staleness
    color_order = {"red": 0, "yellow": 1, "green": 2}
    worktrees.sort(key=lambda w: (color_order.get(w.stale, 3), w.activity_days(), w.name))
    
    for wt in worktrees:
        emoji = wt.status_emoji
        issue = f"#{wt.issue_nr}" if wt.issue_nr else "-"
        activity = f"{wt.activity_days()}d"
        
        # Status text with color
        if wt.dirty:
            status = "[blue]DIRTY[/blue]"
        elif wt.stale == "green":
            status = "[green]OK[/green]"
        elif wt.stale == "yellow":
            status = "[yellow]AGING[/yellow]"
        else:
            status = "[red]STALE[/red]"
        
        table.add_row(
            emoji,
            wt.name,
            issue,
            wt.branch[:33],
            activity,
            status
        )
    
    return table


def run_tui(refresh_seconds=0):
    """Run the TUI."""
    if refresh_seconds > 0:
        # Live mode - refresh periodically
        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                worktrees = scan_all_projects()
                
                # Stats
                green = sum(1 for w in worktrees if w.stale == "green")
                yellow = sum(1 for w in worktrees if w.stale == "yellow")
                red = sum(1 for w in worktrees if w.stale == "red")
                dirty = sum(1 for w in worktrees if w.dirty)
                
                stats = f"📊 Total: {len(worktrees)} | 🟢{green} | 🟡{yellow} | 🔴{red} | ⚠️{dirty} dirty"
                
                table = create_table(worktrees, f"Worktree Guardian [{time.strftime('%H:%M:%S')}]")
                panel = Panel(table, title=stats, border_style="blue")
                
                live.update(panel)
                time.sleep(refresh_seconds)
    else:
        # Single run mode
        worktrees = scan_all_projects()
        
        green = sum(1 for w in worktrees if w.stale == "green")
        yellow = sum(1 for w in worktrees if w.stale == "yellow")
        red = sum(1 for w in worktrees if w.stale == "red")
        dirty = sum(1 for w in worktrees if w.dirty)
        
        stats = f"Total: {len(worktrees)} | 🟢{green} | 🟡{yellow} | 🔴{red} | ⚠️{dirty} dirty"
        
        table = create_table(worktrees)
        panel = Panel(table, title=stats, border_style="blue")
        console.print(panel)


if __name__ == "__main__":
    run_tui()
