"""CLI interface for Worktree Guardian"""
import click
import json
from datetime import datetime
from pathlib import Path
from .git_ops import scan_all_projects, STALE_THRESHOLD_DAYS
from .models import Worktree

STATE_FILE = Path.home() / ".wtreeguardian" / "state.json"

@click.group()
@click.version_option(version="2.0.0")
def cli():
    """🌳 Worktree Guardian - Git worktree monitoring"""
    pass


@cli.command()
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--filter", "filter_color", type=click.Choice(["all", "green", "yellow", "red"]), default="all")
def list(output_json, filter_color):
    """List all worktrees with status"""
    worktrees = scan_all_projects()
    
    if output_json:
        result = {
            "worktrees": [w.to_dict() for w in worktrees],
            "scanned_at": datetime.now().isoformat(),
            "total": len(worktrees),
            "green": sum(1 for w in worktrees if w.stale == "green"),
            "yellow": sum(1 for w in worktrees if w.stale == "yellow"),
            "red": sum(1 for w in worktrees if w.stale == "red"),
            "dirty": sum(1 for w in worktrees if w.dirty),
        }
        click.echo(json.dumps(result, indent=2))
        return
    
    # Human readable
    color_order = {"red": 0, "yellow": 1, "green": 2}
    worktrees.sort(key=lambda w: (color_order.get(w.stale, 3), w.activity_days(), w.name))
    
    # Filter
    if filter_color != "all":
        worktrees = [w for w in worktrees if w.stale == filter_color]
    
    green = sum(1 for w in worktrees if w.stale == "green")
    yellow = sum(1 for w in worktrees if w.stale == "yellow")
    red = sum(1 for w in worktrees if w.stale == "red")
    dirty = sum(1 for w in worktrees if w.dirty)
    
    click.echo(f"\n🌳 Worktree Guardian")
    click.echo("=" * 60)
    click.echo(f"📊 Total: {len(worktrees)} | 🟢{green} | 🟡{yellow} | 🔴{red} | ⚠️{dirty} dirty")
    click.echo("-" * 60)
    
    for wt in worktrees:
        emoji = wt.status_emoji
        issue = f"#{wt.issue_nr}" if wt.issue_nr else ""
        status = "DIRTY" if wt.dirty else wt.stale.upper()
        
        click.echo(f"{emoji} {wt.name} {issue}")
        click.echo(f"   Branch: {wt.branch}")
        click.echo(f"   Commit: {wt.last_commit or '?'} ({wt.last_commit_days}d)")
        click.echo(f"   Activity: {wt.last_activity or '?'} ({wt.activity_days()}d)")
        click.echo(f"   Status: {status}")
        click.echo()


@cli.command()
@click.option("--days", default=STALE_THRESHOLD_DAYS, help="Alert threshold in days")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def alert(days, output_json):
    """Show stale worktrees (for cron)"""
    worktrees = scan_all_projects()
    
    # Filter to stale (red)
    stale = [w for w in worktrees if w.stale == "red" or w.activity_days() > days]
    
    if not stale:
        if not output_json:
            click.echo("✅ No stale worktrees found")
        return
    
    if output_json:
        result = {
            "alerts": [w.to_dict() for w in stale],
            "count": len(stale),
            "threshold_days": days,
        }
        click.echo(json.dumps(result, indent=2))
        return
    
    click.echo(f"\n🚨 Worktree Guardian — {len(stale)} stale worktrees\n")
    for wt in stale:
        issue = f"#{wt.issue_nr}" if wt.issue_nr else ""
        click.echo(f"  • {wt.name} {issue}")
        click.echo(f"    {wt.activity_days()} days inactive")
        click.echo()


@cli.command()
@click.option("--interval", default=300, help="Poll interval in seconds")
def watch(interval):
    """Watch mode - poll periodically (for cron)"""
    import time
    click.echo(f"🌳 Watching worktrees every {interval}s (Ctrl+C to stop)")
    
    while True:
        worktrees = scan_all_projects()
        stale = [w for w in worktrees if w.stale == "red"]
        
        if stale:
            click.echo(f"\n🚨 [{datetime.now().strftime('%H:%M:%S')}] {len(stale)} stale:")
            for wt in stale:
                issue = f"#{wt.issue_nr}" if wt.issue_nr else ""
                click.echo(f"  • {wt.name} {issue} ({wt.activity_days()}d)")
        
        time.sleep(interval)


if __name__ == "__main__":
    cli()


@cli.command()
@click.option("--refresh", default=0, help="Auto-refresh interval in seconds (0=disabled)")
def tui(refresh):
    """Launch the interactive TUI"""
    from .rich_tui import run_tui
    run_tui(refresh_seconds=refresh)


@cli.command()
@click.option("--days", default=3, help="Alert threshold in days")
@click.option("--channel", default=None, help="Discord channel ID")
def discord_alert(days, channel):
    """Send stale worktrees to Discord"""
    from .git_ops import scan_all_projects
    
    worktrees = scan_all_projects()
    stale = [w for w in worktrees if w.stale == "red" or w.activity_days() > days]
    
    if not stale:
        click.echo("✅ No stale worktrees - all good!")
        return
    
    # Format message
    lines = [f"🚨 **{len(stale)} stale worktrees**\n"]
    for wt in stale:
        issue = f"#{wt.issue_nr}" if wt.issue_nr else ""
        lines.append(f"• `{wt.name}` {issue}")
        lines.append(f"  {wt.activity_days()} days inactive")
    
    message = "\n".join(lines)
    
    if channel:
        # Send to Discord via message tool
        import subprocess
        cmd = ['python3', '-c', f'''
import sys
sys.path.insert(0, ".")
from wtree_guardian.discord_notify import send_discord
send_discord({channel}, """{message}""")
''']
        subprocess.run(cmd, cwd="~/projects/worktree-guardian-tui")
    else:
        click.echo(message)


@cli.command()
@click.option("--days", default=3, help="Days threshold")
def cleanup(days):
    """Show commands to cleanup stale worktrees"""
    from .git_ops import scan_all_projects
    
    worktrees = scan_all_projects()
    stale = [w for w in worktrees if w.activity_days() > days]
    
    if not stale:
        click.echo("✅ No stale worktrees to clean up")
        return
    
    click.echo(f"\n🧹 Cleanup commands for {len(stale)} stale worktrees:\n")
    for wt in stale:
        click.echo(f"# {wt.name} ({wt.activity_days()}d)")
        click.echo(f"cd ~/projects && rm -rf {wt.path}")
        click.echo(f"cd ~/projects/{wt.repo} && git worktree remove {wt.path}")
        click.echo()
