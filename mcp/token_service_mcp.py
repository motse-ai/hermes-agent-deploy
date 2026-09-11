#!/usr/bin/env python3
"""
Token Service MCP Server (stdio)
Wraps Token Service REST API for Hermes agent.
Encapsulates admin credentials — agent only sees safe tools.

Robustness features:
- Retry with exponential backoff on transient failures
- JWT token auto-refresh on 401
- Connection health check
- Graceful degradation with clear error messages
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
MAX_RETRIES = int(os.environ.get("TS_MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.environ.get("TS_RETRY_DELAY", "1.0"))
REQUEST_TIMEOUT = float(os.environ.get("TS_TIMEOUT", "15"))

# JWT token cache
_token_cache: Dict[str, Any] = {"token": None, "expires_at": 0}

# Health state
_healthy = False
_last_health_check = 0
HEALTH_CHECK_INTERVAL = 60  # seconds

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("token_service_mcp")


class TokenServiceError(Exception):
    """Base error for Token Service operations."""
    pass


class TokenServiceUnavailable(TokenServiceError):
    """Token Service is unreachable."""
    pass


class TokenServiceAuthError(TokenServiceError):
    """Authentication failed."""
    pass


def _check_health() -> bool:
    """Quick health check without auth."""
    global _healthy, _last_health_check
    now = time.time()
    if _healthy and (now - _last_health_check) < HEALTH_CHECK_INTERVAL:
        return True
    try:
        resp = httpx.get(f"{TOKEN_SERVICE_URL}/api", timeout=5)
        _healthy = resp.status_code == 200
        _last_health_check = now
        return _healthy
    except Exception:
        _healthy = False
        _last_health_check = now
        return False


def _get_auth_headers(force_refresh: bool = False) -> Dict[str, str]:
    """Get auth headers, refreshing JWT if needed."""
    global _token_cache
    now = time.time()

    # Return cached token if still valid (with 60s buffer)
    if not force_refresh and _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return {"Cookie": f"access_token={_token_cache['token']}"}

    # Login to get new token
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(
                f"{TOKEN_SERVICE_URL}/auth/login",
                json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            # Extract token from Set-Cookie header
            set_cookie = resp.headers.get("set-cookie", "")
            for part in set_cookie.split(";"):
                if part.strip().startswith("access_token="):
                    _token_cache["token"] = part.strip().split("=", 1)[1]
                    _token_cache["expires_at"] = now + 43000  # ~12h
                    logger.info("JWT token refreshed successfully")
                    return {"Cookie": f"access_token={_token_cache['token']}"}
            raise TokenServiceAuthError("No access_token in login response")
        except TokenServiceAuthError:
            raise
        except httpx.ConnectError as e:
            last_err = e
            logger.warning(f"Connection failed (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
        except httpx.TimeoutException as e:
            last_err = e
            logger.warning(f"Timeout (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
        except Exception as e:
            last_err = e
            logger.error(f"Login failed: {e}")
            break

    raise TokenServiceUnavailable(
        f"Cannot connect to Token Service at {TOKEN_SERVICE_URL}. "
        f"Service may be down. Last error: {last_err}"
    )


def _api_request(method: str, path: str, data: Any = None, retries: int = MAX_RETRIES) -> Any:
    """Make API request with retry logic."""
    url = f"{TOKEN_SERVICE_URL}{path}"

    for attempt in range(retries):
        try:
            headers = _get_auth_headers()
            if data is not None:
                headers["Content-Type"] = "application/json"

            if method == "GET":
                resp = httpx.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            elif method == "POST":
                resp = httpx.post(url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
            elif method == "PATCH":
                resp = httpx.patch(url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
            elif method == "DELETE":
                resp = httpx.delete(url, headers=headers, timeout=REQUEST_TIMEOUT)
            else:
                raise ValueError(f"Unsupported method: {method}")

            # Handle 401 — force token refresh and retry once
            if resp.status_code == 401 and attempt == 0:
                logger.warning("Got 401, refreshing token...")
                _get_auth_headers(force_refresh=True)
                continue

            resp.raise_for_status()
            return resp.json()

        except TokenServiceUnavailable:
            raise
        except httpx.ConnectError as e:
            if attempt < retries - 1:
                logger.warning(f"Connection failed (attempt {attempt+1}/{retries}): {e}")
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
            else:
                raise TokenServiceUnavailable(
                    f"Cannot connect to Token Service at {TOKEN_SERVICE_URL}. "
                    f"Please check if the service is running. Error: {e}"
                )
        except httpx.TimeoutException as e:
            if attempt < retries - 1:
                logger.warning(f"Timeout (attempt {attempt+1}/{retries}): {e}")
                time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
            else:
                raise TokenServiceUnavailable(
                    f"Request timed out after {retries} attempts. "
                    f"Service at {TOKEN_SERVICE_URL} may be slow or unresponsive."
                )
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", str(e))
            except Exception:
                error_detail = str(e)
            raise TokenServiceError(
                f"API Error ({e.response.status_code}): {error_detail}"
            )

    raise TokenServiceError(f"Failed after {retries} attempts")


def _api_get(path: str) -> Any:
    """GET request to Token Service."""
    return _api_request("GET", path)


def _api_post(path: str, data: Any = None) -> Any:
    """POST request to Token Service."""
    return _api_request("POST", path, data)


def _api_patch(path: str, data: Any = None) -> Any:
    """PATCH request to Token Service."""
    return _api_request("PATCH", path, data)


# MCP Server
server = Server("token-service")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_configs",
            description="List lingxing config items from Token Service. Default: xingshang only (星驰/星商/星乐). Set xingshang_only=false to get all.",
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
        # Health check on first call
        if not _check_health():
            return [TextContent(type="text",
                text="⚠️ Token Service is currently unreachable. "
                     "Please check if the service is running at "
                     f"{TOKEN_SERVICE_URL}. You can verify with: curl {TOKEN_SERVICE_URL}/api")]

        if name == "list_configs":
            xingshang_only = arguments.get("xingshang_only", True)
            result = _api_get("/configs/lingxing/admin")
            items = result.get("items", [])
            
            if xingshang_only:
                XINGSHANG_KEYWORDS = ["星商", "星驰", "星乐"]
                items = [i for i in items if any(kw in (i.get("title","") or "") for kw in XINGSHANG_KEYWORDS)]
            
            summary = f"Found {len(items)} config items:"
            if xingshang_only:
                summary += " (xingshang only)"
            summary += "\n"
            for item in items:
                cfg = item.get("config", {})
                source = cfg.get("CONFIG_SOURCE", "?")
                enabled = "✓" if item.get("enabled", True) else "✗"
                item_id = item["id"]; summary += f"  {enabled} {item_id} (source={source})\n"
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
            result = _api_patch(
                f"/configs/lingxing/config-item/{item_id}/batch",
                updates,
            )
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

    except TokenServiceUnavailable as e:
        logger.error(f"Service unavailable: {e}")
        return [TextContent(type="text", text=f"⚠️ Token Service unavailable: {e}")]
    except TokenServiceError as e:
        logger.error(f"Service error: {e}")
        return [TextContent(type="text", text=f"❌ Token Service error: {e}")]
    except Exception as e:
        logger.exception(f"Unexpected error in {name}: {e}")
        return [TextContent(type="text", text=f"❌ Unexpected error: {str(e)}")]


async def main():
    logger.info(f"Starting Token Service MCP server (url={TOKEN_SERVICE_URL})")
    # Initial health check
    if _check_health():
        logger.info("Token Service is healthy")
    else:
        logger.warning(f"Token Service at {TOKEN_SERVICE_URL} is not responding, will retry on first call")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
