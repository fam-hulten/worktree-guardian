# Worktree Guardian

> Git worktree status monitoring for multi-project workflows

## Overview

Worktree Guardian helps you keep track of all your git worktrees across multiple projects. It scans `~/projects` for main repos and lists all their worktrees with staleness indicators.

## Features

- **Smart scanning**: Only scans main repos (skips worktrees to avoid duplicates)
- **Issue parsing**: Extracts issue numbers from branch names
- **Staleness scoring**: Green/Yellow/Red indicators based on days since commit
- **Multiple output modes**: Terminal (human-readable), JSON (dashboard), Alert (cron)
- **Fast**: Scans 70+ worktrees in under 1 second

## Quick Start

```bash
# Human-readable status
python3 worktree_guardian_v2.py

# JSON for dashboard
python3 worktree_guardian_v2.py --json > worktrees.json

# Alert mode for cron (only shows abandoned worktrees)
python3 worktree_guardian_v2.py --alert

# Cron job (daily at 9am)
0 9 * * * cd ~/projects/worktree-guardian && ./check_abandoned.sh
```

## Staleness Rules

| Status | Meaning |
|--------|---------|
| 🟢 Green | Active (<4 days since commit) |
| 🟡 Yellow | Aging (4-7 days) or dirty (active work) |
| 🔴 Red | Abandoned (>7 days inactive) |

## Example Output

```
📊 74 worktrees | 🟢61 clean | 🟡13+31 aging | 💀8 abandoned

⚠️  Abandoned (>7 days):
   - studywise-api-cli-list-grade-schools (feat/85-list-grade-schools-impl) - 8d inactive
   - grocy-shopping-list (main) - 9d inactive
```

## Files

- `worktree_guardian_v2.py` - Main CLI scanner
- `check_abandoned.sh` - Cron script for alerts
- `index.html` - Legacy dashboard (v1)

## Requirements

- Python 3.7+
- Git
- Worktrees in `~/projects/{repo}` structure
