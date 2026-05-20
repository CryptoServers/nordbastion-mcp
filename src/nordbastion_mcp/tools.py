"""Declarative tool registry.

Each entry mirrors NordBastion's server-side MCP tool catalog 1:1 and binds
it to the REST endpoint that backs it. The MCP layer (``server.py``) reads
this table to advertise tools and to dispatch calls — so the surface stays
single-source-of-truth with the upstream API.

Keys per tool:
    name          MCP tool name (matches NordBastion's own naming).
    method        HTTP verb.
    path          REST path under /v1, with {placeholders} for path params.
    path_params   argument names injected into the path.
    query_params  argument names sent as the query string.
    scope         API-key scope required (None = public, no auth needed).
    description   human/agent-facing description.
    input         JSON Schema for the tool's arguments.

Everything in ``input.properties`` that is neither a path nor a query param
is sent as the JSON request body (for POST/PATCH/PUT).
"""

from __future__ import annotations

from typing import Any

_REGION_ENUM = ["sto", "hel", "osl", "rkv"]
_OS_ENUM = ["ubuntu-24", "ubuntu-22", "debian-13", "debian-12", "alma-9", "rocky-9"]

TOOLS: list[dict[str, Any]] = [
    # ── Auth ──────────────────────────────────────────────────────────────
    {
        "name": "register_account",
        "method": "POST",
        "path": "/auth/register",
        "scope": None,
        "description": "Create a new NordBastion account from an email + password. Returns the user + access/refresh tokens. KYC-free: no name, phone, or document is ever requested.",
        "input": {
            "type": "object",
            "required": ["email", "password"],
            "properties": {
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string", "minLength": 8},
            },
        },
    },
    {
        "name": "login",
        "method": "POST",
        "path": "/auth/login",
        "scope": None,
        "description": "Exchange email + password for access/refresh tokens. If 2FA is enabled, returns 202 and asks for a follow-up `login_totp` call.",
        "input": {
            "type": "object",
            "required": ["email", "password"],
            "properties": {
                "email": {"type": "string"},
                "password": {"type": "string"},
                "totp_code": {
                    "type": "string",
                    "description": "Optional 6-digit code; usually omitted on first call.",
                },
            },
        },
    },
    {
        "name": "login_totp",
        "method": "POST",
        "path": "/auth/login/totp",
        "scope": None,
        "description": "Second factor for a pending login (use after `login` returned `totp_required: true`).",
        "input": {
            "type": "object",
            "required": ["totp_code"],
            "properties": {"totp_code": {"type": "string", "pattern": "^[0-9]{6}$"}},
        },
    },
    {
        "name": "refresh_token",
        "method": "POST",
        "path": "/auth/token/refresh",
        "scope": None,
        "description": "Rotate a refresh token into a fresh access pair.",
        "input": {
            "type": "object",
            "required": ["refresh_token"],
            "properties": {"refresh_token": {"type": "string"}},
        },
    },
    {
        "name": "create_api_key",
        "method": "POST",
        "path": "/auth/api-keys",
        "scope": "full",
        "description": "Mint a long-lived scoped API key. Requires at least one confirmed top-up on the account. Plaintext returned ONCE.",
        "input": {
            "type": "object",
            "required": ["name", "scope"],
            "properties": {
                "name": {"type": "string", "maxLength": 120},
                "scope": {"type": "string", "enum": ["read", "billing", "servers", "full"]},
                "ip_allowlist": {
                    "type": "string",
                    "description": "Comma-separated CIDRs. Empty = any IP.",
                },
            },
        },
    },
    {
        "name": "list_api_keys",
        "method": "GET",
        "path": "/auth/api-keys",
        "scope": "read",
        "description": "List API keys on the account (metadata only — no plaintext recoverable).",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "revoke_api_key",
        "method": "DELETE",
        "path": "/auth/api-keys/{key_id}",
        "path_params": ["key_id"],
        "scope": "full",
        "description": "Revoke an API key by id.",
        "input": {
            "type": "object",
            "required": ["key_id"],
            "properties": {"key_id": {"type": "string", "description": 'e.g. "key_42"'}},
        },
    },
    # ── Account ───────────────────────────────────────────────────────────
    {
        "name": "get_account",
        "method": "GET",
        "path": "/account",
        "scope": "read",
        "description": "Return the current account (no secrets, no password hash).",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "get_balance",
        "method": "GET",
        "path": "/account/balance",
        "scope": "read",
        "description": "Get the current wallet balance in USD.",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "get_audit_log",
        "method": "GET",
        "path": "/account/audit-log",
        "query_params": ["limit"],
        "scope": "read",
        "description": "List the last N authenticated requests for this account.",
        "input": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}
            },
        },
    },
    # ── Billing ───────────────────────────────────────────────────────────
    {
        "name": "list_coins",
        "method": "GET",
        "path": "/billing/coins",
        "scope": None,
        "description": "Cryptocurrencies accepted for top-ups.",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "list_bonus_tiers",
        "method": "GET",
        "path": "/billing/bonus-tiers",
        "scope": None,
        "description": "Top-up bonus ladder (linear interpolation between anchors).",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "create_topup",
        "method": "POST",
        "path": "/billing/topups",
        "scope": "billing",
        "description": "Open a crypto invoice for an account top-up. The minimum is server-enforced (amounts below it return HTTP 422 `amount_too_low`). Returns wallet_address + QR + expiry. Poll `get_topup` until status is `confirmed`.",
        "input": {
            "type": "object",
            "required": ["amount_usd", "crypto"],
            "properties": {
                "amount_usd": {
                    "type": "number",
                    "description": "USD amount to credit (excluding bonus). Subject to a server-enforced floor and ceiling.",
                },
                "crypto": {
                    "type": "string",
                    "description": "Coin code from `list_coins` (BTC, XMR, USDCETH, USDT, …).",
                },
            },
        },
    },
    {
        "name": "get_topup",
        "method": "GET",
        "path": "/billing/topups/{order_number}",
        "path_params": ["order_number"],
        "scope": "read",
        "description": "Read a top-up by order_number.",
        "input": {
            "type": "object",
            "required": ["order_number"],
            "properties": {"order_number": {"type": "string"}},
        },
    },
    {
        "name": "list_topups",
        "method": "GET",
        "path": "/billing/topups",
        "query_params": ["status", "limit"],
        "scope": "read",
        "description": "List recent top-up invoices, optionally filtered by status.",
        "input": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "confirming", "confirmed", "expired", "cancelled"],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
        },
    },
    {
        "name": "cancel_topup",
        "method": "POST",
        "path": "/billing/topups/{order_number}/cancel",
        "path_params": ["order_number"],
        "scope": "billing",
        "description": "Cancel a still-open top-up.",
        "input": {
            "type": "object",
            "required": ["order_number"],
            "properties": {"order_number": {"type": "string"}},
        },
    },
    # ── Catalog ───────────────────────────────────────────────────────────
    {
        "name": "list_catalog",
        "method": "GET",
        "path": "/catalog",
        "scope": None,
        "description": "Full catalog bundle: VPS + dedicated tiers + bastions + OS images.",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "list_vps",
        "method": "GET",
        "path": "/catalog/vps",
        "scope": None,
        "description": "List VPS tiers (5 tiers, Sentinel → Citadel).",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "list_dedicated",
        "method": "GET",
        "path": "/catalog/dedicated",
        "scope": None,
        "description": "List dedicated bare-metal tiers (5 tiers, Bastion-Lite → Hyperion).",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "list_bastions",
        "method": "GET",
        "path": "/catalog/bastions",
        "scope": None,
        "description": "List Nordic bastion locations (Stockholm, Helsinki, Oslo, Reykjavík).",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "list_os_images",
        "method": "GET",
        "path": "/catalog/images",
        "scope": None,
        "description": "List operating-system images offered at checkout.",
        "input": {"type": "object", "properties": {}},
    },
    # ── Servers ───────────────────────────────────────────────────────────
    {
        "name": "order_server",
        "method": "POST",
        "path": "/servers",
        "scope": "servers",
        "description": "Provision a VPS or dedicated server. Debits balance up-front. A root password is generated and returned ONCE if you omit one.",
        "input": {
            "type": "object",
            "required": ["service_code"],
            "properties": {
                "service_code": {
                    "type": "string",
                    "description": "NB-V1..NB-V5 (VPS) or NB-D1..NB-D5 (dedicated). See `list_vps` / `list_dedicated`.",
                },
                "region": {"type": "string", "enum": _REGION_ENUM},
                "os": {"type": "string", "enum": _OS_ENUM},
                "hostname": {"type": "string", "maxLength": 64},
                "root_password": {
                    "type": "string",
                    "description": "Optional — omit and one is generated for you.",
                },
            },
        },
    },
    {
        "name": "list_servers",
        "method": "GET",
        "path": "/servers",
        "query_params": ["limit"],
        "scope": "read",
        "description": "List the account's provisioned servers.",
        "input": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
        },
    },
    {
        "name": "get_server",
        "method": "GET",
        "path": "/servers/{order_number}",
        "path_params": ["order_number"],
        "scope": "read",
        "description": "Get a single server by order_number.",
        "input": {
            "type": "object",
            "required": ["order_number"],
            "properties": {"order_number": {"type": "string"}},
        },
    },
    {
        "name": "cancel_server",
        "method": "DELETE",
        "path": "/servers/{order_number}",
        "path_params": ["order_number"],
        "scope": "servers",
        "description": "Cancel / decommission a server.",
        "input": {
            "type": "object",
            "required": ["order_number"],
            "properties": {"order_number": {"type": "string"}},
        },
    },
    # ── SSH keys ──────────────────────────────────────────────────────────
    {
        "name": "add_ssh_key",
        "method": "POST",
        "path": "/ssh-keys",
        "scope": "servers",
        "description": "Register an SSH public key on the account.",
        "input": {
            "type": "object",
            "required": ["name", "public_key"],
            "properties": {
                "name": {"type": "string", "maxLength": 120},
                "public_key": {
                    "type": "string",
                    "description": "OpenSSH-format public key (ssh-ed25519 / ssh-rsa / ecdsa-…).",
                },
            },
        },
    },
    {
        "name": "list_ssh_keys",
        "method": "GET",
        "path": "/ssh-keys",
        "scope": "read",
        "description": "List the SSH public keys on the account.",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "remove_ssh_key",
        "method": "DELETE",
        "path": "/ssh-keys/{id}",
        "path_params": ["id"],
        "scope": "servers",
        "description": "Remove an SSH public key.",
        "input": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "string", "description": 'e.g. "sshkey_7"'}},
        },
    },
    # ── Webhooks ──────────────────────────────────────────────────────────
    {
        "name": "create_webhook",
        "method": "POST",
        "path": "/webhooks",
        "scope": "full",
        "description": "Register a webhook endpoint. Returns the signing secret ONCE.",
        "input": {
            "type": "object",
            "required": ["url"],
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "event_filter": {
                    "type": "string",
                    "description": 'Comma-separated event names or "*". e.g. "topup.*,server.created"',
                },
                "description": {"type": "string", "maxLength": 255},
            },
        },
    },
    {
        "name": "list_webhooks",
        "method": "GET",
        "path": "/webhooks",
        "scope": "read",
        "description": "List webhook endpoints.",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_webhook",
        "method": "DELETE",
        "path": "/webhooks/{id}",
        "path_params": ["id"],
        "scope": "full",
        "description": "Remove a webhook endpoint.",
        "input": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "string", "description": 'e.g. "whk_3"'}},
        },
    },
    # ── Transparency ──────────────────────────────────────────────────────
    {
        "name": "get_canary",
        "method": "GET",
        "path": "/transparency/canary",
        "scope": None,
        "description": "Latest warrant canary (PGP-signed text excerpt + sha256 + URL).",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "get_status",
        "method": "GET",
        "path": "/transparency/status",
        "scope": None,
        "description": "Operational status per Nordic bastion.",
        "input": {"type": "object", "properties": {}},
    },
    {
        "name": "get_peering",
        "method": "GET",
        "path": "/transparency/peering",
        "scope": None,
        "description": "AS213232 peering policy + IX presence.",
        "input": {"type": "object", "properties": {}},
    },
]

TOOLS_BY_NAME: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOLS}

# MCP resources mirrored from the upstream server.
RESOURCES: list[dict[str, str]] = [
    {"uri": "nordbastion://catalog", "name": "Full catalog", "description": "VPS + dedicated tiers + bastions + OS images.", "mimeType": "application/json"},
    {"uri": "nordbastion://coins", "name": "Accepted coins", "description": "Cryptocurrencies accepted for top-ups.", "mimeType": "application/json"},
    {"uri": "nordbastion://canary", "name": "Warrant canary", "description": "Latest PGP-signed canary excerpt.", "mimeType": "application/json"},
    {"uri": "nordbastion://doctrine", "name": "Doctrine", "description": "The non-negotiable principles.", "mimeType": "text/plain"},
]

# uri -> (method, path) for the JSON-backed resources.
RESOURCE_ENDPOINTS: dict[str, tuple[str, str]] = {
    "nordbastion://catalog": ("GET", "/catalog"),
    "nordbastion://coins": ("GET", "/billing/coins"),
    "nordbastion://canary": ("GET", "/transparency/canary"),
}
