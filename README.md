# 🌳 Worktree Guardian

Git worktree monitoring med **TUI** (Textual) och **CLI** (Click).

## Installation

```bash
pip install -e .
```

## Usage

### CLI

```bash
wtree list                    # Lista alla worktrees
wtree list --json            # JSON output
wtree list --filter red      # Filtrera på färg

wtree alert --days=3         # Visa stalna worktrees
wtree watch --interval=300   # Cron-läge (poll var 5e min)
```

### TUI

```bash
wtree tui                    # Starta interaktiv TUI
```

### Navigation
- `j/k` - Navigate up/down
- `r` - Refresh
- `q` - Quit

## Features

- **Issue parsing**: Extraherar issue-nummer från branch-namn
- **Activity tracking**: Använder fil-ändringar, inte bara commits
- **Staleness scoring**: 🟢grön / 🟡gul / 🔴röd baserat på aktivitet
- **Multiple output modes**: CLI, TUI, JSON
