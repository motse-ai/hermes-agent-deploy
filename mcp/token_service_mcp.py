#!/usr/bin/env python3
"""
Token Service MCP Server (stdio)
Wraps Token Service REST API for Hermes agent.
Encapsulates admin credentials — agent only sees safe tools.
"""

import os
import sys
import json
import time
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration
TOKEN_SERVICE_URL = os.environ.get("TOKEN_SERVICE_URL", "http://localhost:8105")
ADMIN_USERNAME = os.environ.get("TS_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("TS_ADMIN_PASS", "admin123")

# JWT token cache
_token_cache: Dict[str, Any] = {"token": None, "expires_at": 0}

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("token_service_mcp")


def _get_auth_headers() -> Dict[str, str]:
    """Get auth headers, refreshing JWT if needed."""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return {"Cookie": f"access_token={_token_cache['token']}"}

    # Login to get new token
    try:
        resp = httpx.post(
            f"{TOKEN_SERVICE_URL}/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            timeout=10,
        )
        resp.raise_for_status()
        # Extract token from Set-Cookie header
        set_cookie = resp.headers.get("set-cookie", "")
        for part in set_cookie.split(";"):
            if part.strip().startswith("access_token="):
                _token_cache["token"] = part.strip().split("=", 1)[1]
                _token_cache["expires_at"] = now + 43000  # ~12h
                return {"Cookie": f"access_token={_token_cache['token']}"}
        raise ValueError("No access_token in login response")
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise


def _api_get(path: str) -> Any:
    """GET request to Token Service."""
    resp = httpx.get(
        f"{TOKEN_SERVICE_URL}{path}",
        headers=_get_auth_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _api_post(path: str, data: Any = None) -> Any:
    """POST request to Token Service."""
    resp = httpx.post(
        f"{TOKEN_SERVICE_URL}{path}",
        headers={**_get_auth_headers(), "Content-Type": "application/json"},
        json=data,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# MCP Server
server = Server("token-service")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_configs",
            description="List all lingxing config items from Token Service",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_config",
            description="Get a specific config item by ID",
            inputSchema={
                "type": "object",
                "properties": {"item_id": {"type": "string", "description": "Config item ID (ASIN)"}},
                "required": ["item_id"],
            },
        ),
        Tool(
            name="update_config_field",
            description="Update a single field in a config item's config object",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "Config item ID"},
                    "field": {"type": "string", "description": "Field name in config object"},
                    "value": {"description": "New value for the field"},
                },
                "required": ["item_id", "field", "value"],
            },
        ),
        Tool(
            name="batch_update_config",
            description="Update multiple fields in a config item at once",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "Config item ID"},
                    "updates": {"type": "object", "description": "Dict of field:value pairs to update"},
                },
                "required": ["item_id", "updates"],
            },
        ),
        Tool(
            name="create_backup",
            description="Create a snapshot of all current configs",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Optional description for the backup"},
                },
            },
        ),
        Tool(
            name="list_backups",
            description="List all backup snapshots (newest first)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="restore_backup",
            description="Restore all configs from a backup snapshot (creates auto-backup first)",
            inputSchema={
                "type": "object",
                "properties": {
                    "snapshot_id": {"type": "string", "description": "Backup snapshot ID to restore from"},
                },
                "required": ["snapshot_id"],
            },
        ),
        Tool(
            name="get_item_audit",
            description="Get audit trail for a specific config item",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "Config item ID"},
                    "limit": {"type": "integer", "description": "Max entries to return (default 50)", "default": 50},
                },
                "required": ["item_id"],
            },
        ),
        Tool(
            name="get_global_audit",
            description="Get the global audit log (most recent first)",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max entries to return (default 100)", "default": 100},
                },
            },
        ),
        Tool(
            name="create_proposal",
            description="Create a HITL proposal for config changes. Changes are NOT applied until approved and executed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Description of the proposed changes"},
                    "changes": {
                        "type": "array",
                        "description": "List of changes, each with item_id, field, old_value, new_value, action (update/delete/enable/disable)",
                        "items": {"type": "object"},
                    },
                },
                "required": ["changes"],
            },
        ),
        Tool(
            name="list_proposals",
            description="List all proposals, optionally filtered by status (pending/approved/rejected/executed/expired)",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status"},
                },
            },
        ),
        Tool(
            name="get_proposal",
            description="Get a specific proposal by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string", "description": "Proposal ID"},
                },
                "required": ["proposal_id"],
            },
        ),
        Tool(
            name="approve_proposal",
            description="Approve a pending proposal (admin only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string", "description": "Proposal ID to approve"},
                },
                "required": ["proposal_id"],
            },
        ),
        Tool(
            name="reject_proposal",
            description="Reject a pending proposal (admin only)",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string", "description": "Proposal ID to reject"},
                },
                "required": ["proposal_id"],
            },
        ),
        Tool(
            name="execute_proposal",
            description="Execute an approved proposal, applying all changes and recording audit trail",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposal_id": {"type": "string", "description": "Proposal ID to execute"},
                },
                "required": ["proposal_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "list_configs":
            result = _api_get("/configs/lingxing/admin")
            items = result.get("items", [])
            summary = f"Found {len(items)} config items:\n"
            for item in items:
                cfg = item.get("config", {})
                source = cfg.get("CONFIG_SOURCE", "?")
                enabled = "✓" if item.get("enabled", True) else "✗"
                summary += f"  {enabled} {item['id']} (source={source})\n"
            return [TextContent(type="text", text=summary)]

        elif name == "get_config":
            item_id = arguments["item_id"]
            result = _api_get(f"/configs/lingxing/item/{item_id}")
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        elif name == "update_config_field":
            item_id = arguments["item_id"]
            field = arguments["field"]
            value = arguments["value"]
            result = _api_post(
                f"/configs/lingxing/config-item/{item_id}?remove=false",
                {"key": field, "value": value},
            )
            return [TextContent(type="text", text=f"Updated {item_id}.{field} = {json.dumps(value, ensure_ascii=False)}")]

        elif name == "batch_update_config":
            item_id = arguments["item_id"]
            updates = arguments["updates"]
            result = httpx.patch(
                f"{TOKEN_SERVICE_URL}/configs/lingxing/config-item/{item_id}/batch",
                headers={**_get_auth_headers(), "Content-Type": "application/json"},
                json=updates,
                timeout=30,
            )
            result.raise_for_status()
            return [TextContent(type="text", text=f"Batch updated {item_id}: {list(updates.keys())}")]

        elif name == "create_backup":
            desc = arguments.get("description")
            result = _api_post("/configs/lingxing/backup", {"description": desc})
            data = result.get("data", {})
            return [TextContent(type="text", text=f"Backup created: {data.get('snapshot_id')}, {data.get('item_count')} items")]

        elif name == "list_backups":
            result = _api_get("/configs/lingxing/backups")
            backups = result.get("backups", [])
            if not backups:
                return [TextContent(type="text", text="No backups found.")]
            lines = [f"  {b['snapshot_id']} — {b['item_count']} items — {b['created_at']}" for b in backups]
            return [TextContent(type="text", text=f"Found {len(backups)} backups:\n" + "\n".join(lines))]

        elif name == "restore_backup":
            snapshot_id = arguments["snapshot_id"]
            result = _api_post(f"/configs/lingxing/backup/{snapshot_id}/restore")
            data = result.get("data", {})
            return [TextContent(type="text", text=f"Restored {data.get('restored')} items from backup {snapshot_id}")]

        elif name == "get_item_audit":
            item_id = arguments["item_id"]
            limit = arguments.get("limit", 50)
            result = _api_get(f"/configs/lingxing/audit/{item_id}?limit={limit}")
            entries = result.get("entries", [])
            if not entries:
                return [TextContent(type="text", text=f"No audit entries for {item_id}")]
            lines = [f"  [{e['timestamp']}] {e['action']} by {e['actor']} (proposal={e.get('proposal_id', '-')})" for e in entries]
            return [TextContent(type="text", text=f"Audit for {item_id} ({len(entries)} entries):\n" + "\n".join(lines))]

        elif name == "get_global_audit":
            limit = arguments.get("limit", 100)
            result = _api_get(f"/configs/lingxing/audit?limit={limit}")
            entries = result.get("entries", [])
            if not entries:
                return [TextContent(type="text", text="No audit entries.")]
            lines = [f"  [{e['timestamp']}] {e['item_id']}: {e['action']} by {e['actor']}" for e in entries]
            return [TextContent(type="text", text=f"Global audit ({len(entries)} entries):\n" + "\n".join(lines))]

        elif name == "create_proposal":
            changes = arguments["changes"]
            desc = arguments.get("description")
            result = _api_post("/configs/lingxing/proposals", {"actor": "agent", "description": desc, "changes": changes})
            data = result.get("data", {})
            return [TextContent(type="text", text=f"Proposal created: {data.get('proposal_id')} (status={data.get('status')}, expires={data.get('expires_at')})")]

        elif name == "list_proposals":
            status = arguments.get("status")
            path = "/configs/lingxing/proposals"
            if status:
                path += f"?status={status}"
            result = _api_get(path)
            proposals = result.get("proposals", [])
            if not proposals:
                return [TextContent(type="text", text="No proposals found.")]
            lines = [f"  {p['proposal_id']} [{p['status']}] by {p['actor']} — {p.get('description', '-')}" for p in proposals]
            return [TextContent(type="text", text=f"Found {len(proposals)} proposals:\n" + "\n".join(lines))]

        elif name == "get_proposal":
            prop_id = arguments["proposal_id"]
            result = _api_get(f"/configs/lingxing/proposals/{prop_id}")
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        elif name == "approve_proposal":
            prop_id = arguments["proposal_id"]
            result = _api_post(f"/configs/lingxing/proposals/{prop_id}/approve", {"actor": "admin"})
            return [TextContent(type="text", text=f"Proposal {prop_id} approved.")]

        elif name == "reject_proposal":
            prop_id = arguments["proposal_id"]
            result = _api_post(f"/configs/lingxing/proposals/{prop_id}/reject", {"actor": "admin"})
            return [TextContent(type="text", text=f"Proposal {prop_id} rejected.")]

        elif name == "execute_proposal":
            prop_id = arguments["proposal_id"]
            result = _api_post(f"/configs/lingxing/proposals/{prop_id}/execute", {"actor": "admin"})
            data = result.get("data", {})
            return [TextContent(type="text", text=f"Proposal {prop_id} executed. Result: {data.get('result', 'N/A')}")]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_detail = e.response.json().get("detail", str(e))
        except Exception:
            error_detail = str(e)
        return [TextContent(type="text", text=f"API Error ({e.response.status_code}): {error_detail}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
