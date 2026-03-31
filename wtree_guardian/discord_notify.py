"""Discord notification for worktree alerts"""
import os
import urllib.request
import json

def send_discord(channel_id: str, message: str, webhook_url: str = None):
    """Send message to Discord channel via webhook."""
    if webhook_url is None:
        # Get from environment
        webhook_url = os.environ.get("DISCORD_WEBHOOK_WORKTREE")
    
    if not webhook_url:
        print("ERROR: DISCORD_WEBHOOK_WORKTREE not set")
        return False
    
    data = {
        "content": message,
        "allowed_mentions": {"roles": []}
    }
    
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 204
    except Exception as e:
        print(f"ERROR sending to Discord: {e}")
        return False
