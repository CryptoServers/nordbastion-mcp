"""MCP server for NordBastion (stdio transport).

Advertises NordBastion's tool catalog, resources and onboarding prompt to any
MCP client, and dispatches tool calls to the public REST API via
``NordBastionClient``. Configure with the ``NORDBASTION_API_KEY`` environment
variable (public tools work without one).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .client import NordBastionClient, NordBastionError
from .tools import RESOURCE_ENDPOINTS, RESOURCES, TOOLS, TOOLS_BY_NAME

server: Server = Server("nordbastion-mcp")

_client: NordBastionClient | None = None


def client() -> NordBastionClient:
    global _client
    if _client is None:
        _client = NordBastionClient()
    return _client


def _text(payload: Any) -> list[types.TextContent]:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    return [types.TextContent(type="text", text=text)]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=t["name"], description=t["description"], inputSchema=t["input"])
        for t in TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return _text({"error": "unknown_tool", "tool": name})

    args = arguments or {}
    path_params = spec.get("path_params", [])
    query_params = spec.get("query_params", [])

    api = client()
    if spec.get("scope") is not None and not api.authenticated:
        return _text(
            {
                "error": "missing_api_key",
                "detail": (
                    f"Tool '{name}' needs an authenticated account "
                    f"(scope: {spec['scope']}). Set the NORDBASTION_API_KEY "
                    "environment variable to an nb_live_* API key."
                ),
            }
        )

    try:
        path = spec["path"].format(**{k: args[k] for k in path_params})
    except KeyError as exc:
        return _text({"error": "missing_path_param", "param": str(exc).strip("'")})

    query = {k: args[k] for k in query_params if args.get(k) is not None}

    body: dict[str, Any] | None = None
    if spec["method"] in ("POST", "PATCH", "PUT"):
        skip = set(path_params) | set(query_params)
        body = {k: v for k, v in args.items() if k not in skip and v is not None}

    try:
        data = await api.request(spec["method"], path, query=query, body=body)
    except NordBastionError as exc:
        return _text({"error": "api_error", "status": exc.status, "detail": exc.payload})
    except Exception as exc:  # noqa: BLE001 — surface transport errors to the agent
        return _text({"error": "request_failed", "detail": str(exc)})

    return _text(data)


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri=r["uri"],
            name=r["name"],
            description=r["description"],
            mimeType=r["mimeType"],
        )
        for r in RESOURCES
    ]


@server.read_resource()
async def read_resource(uri: types.AnyUrl) -> str:
    key = str(uri)
    if key == "nordbastion://doctrine":
        return "NordBastion doctrine: minimal data collection, jurisdiction by design, crypto-native billing, change announced rather than made in silence. Full text: https://nordbastion.com/doctrine/"
    endpoint = RESOURCE_ENDPOINTS.get(key)
    if endpoint is None:
        return json.dumps({"error": "unknown_resource", "uri": key})
    method, path = endpoint
    try:
        data = await client().request(method, path)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "request_failed", "detail": str(exc)})
    return json.dumps(data, indent=2, ensure_ascii=False)


_ONBOARD_TEMPLATE = (
    "I need to spin up a KYC-free Nordic VPS for {use}. Please:\n\n"
    "1. Use `list_vps` and `list_bastions` to recommend a tier + region.\n"
    "2. Either `register_account` (new email + password) or `login` (existing creds).\n"
    "3. `get_balance`. If 0, walk me through `create_topup` (BTC by default; ask "
    "before any other coin), then poll `get_topup` until status=confirmed.\n"
    "4. `order_server` with the recommended tier/region. Read the generated root "
    "password back to me ONCE.\n"
    "5. Optionally `add_ssh_key` if I have one.\n"
    "6. Print a summary: server id, status, region, root password.\n\n"
    "At every step, prefer asking me a short multiple-choice question over making "
    "assumptions on my behalf."
)


@server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    return [
        types.Prompt(
            name="onboard_to_nordbastion",
            description="Step-by-step prompt to create an account, do a first crypto top-up, and order a VPS.",
            arguments=[
                types.PromptArgument(
                    name="target_use",
                    description='Why you want a VPS (e.g. "WireGuard VPN").',
                    required=False,
                )
            ],
        )
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
    if name != "onboard_to_nordbastion":
        raise ValueError(f"Unknown prompt: {name}")
    use = (arguments or {}).get("target_use") or "a general-purpose workload"
    return types.GetPromptResult(
        description="NordBastion onboarding walkthrough",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(type="text", text=_ONBOARD_TEMPLATE.format(use=use)),
            )
        ],
    )


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run() -> None:
    """Console-script entry point (``nordbastion-mcp``)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
