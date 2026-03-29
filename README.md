# Worktree Guardian

> Git worktree status monitoring for multi-project workflows

## Overview

Worktree Guardian helps you keep track of all your git worktrees across multiple projects.

## Features

- Scan all worktrees in `~/projects`
- Status: clean, dirty, outdated, abandoned
- JSON export for dashboard integration
- Dark theme dashboard

## Quick Start

```bash
# Generate status report
python3 worktree_guardian.py

# Generate JSON for dashboard
python3 worktree_guardian.py > worktrees.json

# Serve dashboard
python3 -m http.server 3080
```

## Files

- `worktree_guardian.py` - CLI tool
- `index.html` - Dashboard
- `worktrees.json` - Latest scan data
