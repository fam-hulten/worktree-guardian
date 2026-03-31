#!/bin/bash
# Cron script to check for abandoned worktrees
# Add to crontab: 0 9 * * * /home/robert/projects/worktree-guardian/check_abandoned.sh

cd ~/projects/worktree-guardian
OUTPUT=$(python3 worktree_guardian_v2.py --alert 2>&1)

if [ -n "$OUTPUT" ]; then
    echo "⚠️ Worktree Guardian Alert:"
    echo "$OUTPUT"
    # Add Discord notification here if needed
fi
