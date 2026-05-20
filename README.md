# NordBastion MCP server

> Provision **KYC-free, crypto-paid Nordic VPS and dedicated servers** from any AI agent — Claude, Cursor, Zed, Continue, or your own [MCP](https://modelcontextprotocol.io) client.

[![License: MIT](https://img.shields.io/badge/License-MIT-success.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/Model_Context_Protocol-server-7c3aed.svg)](https://modelcontextprotocol.io)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

`nordbastion-mcp` exposes the [NordBastion API](https://nordbastion.com/api/) as Model Context Protocol tools, so an AI assistant can do the whole hosting workflow in natural language: **compare VPS tiers, pick a Nordic region, top up with Monero or Bitcoin, and spin up an anonymous server** — without you ever touching a dashboard.

[NordBastion](https://nordbastion.com) is a privacy-first hosting provider running four bastions in **Stockholm, Helsinki, Oslo and Reykjavík**. Accounts need only an email and a password — no name, phone number, or ID document, ever — and billing is crypto-native. The API was built for agents from day one (scoped API keys, OAuth 2.1 with Dynamic Client Registration, a public agent directory), which makes it a natural fit for MCP.

---

## Why this exists

Agentic workflows increasingly need infrastructure on demand: a throwaway box to run a scraper, a [WireGuard VPN](https://nordbastion.com/guides/wireguard-vpn-on-a-vps/), a [Tor hidden service](https://nordbastion.com/guides/tor-hidden-service-on-a-vps/), or a [self-hosted Lightning node](https://nordbastion.com/guides/self-host-bitcoin-lightning-node/). This server lets the agent do that end-to-end against a host that doesn't demand identity documents and accepts [Monero](https://nordbastion.com/monero-vps/) and [Bitcoin](https://nordbastion.com/bitcoin-vps/).

## Install & run

The server speaks MCP over **stdio**, so any MCP client launches it as a subprocess. The simplest path uses [`uv`](https://docs.astral.sh/uv/) (no manual virtualenv):

```bash
# Run straight from this repository
uvx --from git+https://github.com/CryptoServers/nordbastion-mcp nordbastion-mcp
```

Or install it into your environment with pip / pipx:

```bash
pip install git+https://github.com/CryptoServers/nordbastion-mcp
# then the console script is on your PATH:
nordbastion-mcp
```

### Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `NORDBASTION_API_KEY` | for authenticated tools | — | An `nb_live_*` API key (mint it in the [panel](https://nordbastion.com/panel/) or via `create_api_key`) or an `nb_at_*` OAuth token. |
| `NORDBASTION_BASE_URL` | no | `https://nordbastion.com/v1` | Override the API base URL (testing/self-host). |

Public tools — `list_vps`, `list_dedicated`, `list_bastions`, `list_os_images`, `list_coins`, `get_status`, `get_canary`, `get_peering` — work with **no key at all**.

### Claude Desktop

Add to `claude_desktop_config.json` (see [`examples/`](examples/)):

```json
{
  "mcpServers": {
    "nordbastion": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/CryptoServers/nordbastion-mcp", "nordbastion-mcp"],
      "env": { "NORDBASTION_API_KEY": "nb_live_xxxxxxxxxxxxxxxx" }
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "nordbastion": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/CryptoServers/nordbastion-mcp", "nordbastion-mcp"],
      "env": { "NORDBASTION_API_KEY": "nb_live_xxxxxxxxxxxxxxxx" }
    }
  }
}
```

## Try it

Once connected, ask your assistant things like:

- *"List NordBastion's VPS tiers and tell me the cheapest one with 4 GB RAM."*
- *"Top up my balance with $30 of Monero and wait for it to confirm."*
- *"Provision an `NB-V2` in Helsinki running Debian 13, hostname `wg-gw`, and show me the root password."*
- *"What's the current status of the Reykjavík bastion?"*

There's also a built-in **`onboard_to_nordbastion`** prompt that drives the full account → top-up → order flow.

## Tools

34 tools, mapped 1:1 onto the REST API. Tools marked _public_ need no API key.

| Group | Tools |
| --- | --- |
| **Catalog** _(public)_ | `list_catalog`, `list_vps`, `list_dedicated`, `list_bastions`, `list_os_images` |
| **Transparency** _(public)_ | `get_status`, `get_canary`, `get_peering` |
| **Billing** | `list_coins` _(public)_, `list_bonus_tiers` _(public)_, `create_topup`, `get_topup`, `list_topups`, `cancel_topup` |
| **Servers** | `order_server`, `list_servers`, `get_server`, `cancel_server` |
| **Account** | `get_account`, `get_balance`, `get_audit_log` |
| **SSH keys** | `add_ssh_key`, `list_ssh_keys`, `remove_ssh_key` |
| **Auth** | `register_account`, `login`, `login_totp`, `refresh_token`, `create_api_key`, `list_api_keys`, `revoke_api_key` |
| **Webhooks** | `create_webhook`, `list_webhooks`, `delete_webhook` |

### Resources

- `nordbastion://catalog` — full catalog bundle (JSON)
- `nordbastion://coins` — accepted cryptocurrencies (JSON)
- `nordbastion://canary` — latest warrant canary excerpt (JSON)
- `nordbastion://doctrine` — the operating principles (text)

## How it works

```
AI agent ──MCP/stdio──▶ nordbastion-mcp ──HTTPS──▶ https://nordbastion.com/v1
```

The registry in [`tools.py`](src/nordbastion_mcp/tools.py) mirrors NordBastion's own server-side MCP catalog and binds each tool to its REST endpoint, so the surface stays in lock-step with the upstream API. Authentication is a single bearer credential; nothing is cached to disk.

## Security

- Your API key lives only in the client's environment — never written to disk by this server.
- Scope your key: `read`, `billing`, `servers`, or `full`. Use the narrowest scope an agent needs and an IP allow-list where possible.
- `order_server` and `create_topup` move real money/balance. Review your agent's confirmations before granting `servers`/`billing`/`full` scope.

## Development

```bash
git clone https://github.com/CryptoServers/nordbastion-mcp
cd nordbastion-mcp
uv venv && uv pip install -e ".[dev]" mcp httpx ruff
python -m nordbastion_mcp   # starts the stdio server
ruff check .
```

## Links

- 🌐 Website — <https://nordbastion.com>
- 📚 API reference — <https://nordbastion.com/api/>
- 🧭 Guides (anonymous VPS, Monero, Tor, WireGuard…) — <https://nordbastion.com/guides/>
- 🔒 Warrant canary — <https://nordbastion.com/warrant-canary/>
- 📡 Status — <https://nordbastion.com/status/>

## License

[MIT](LICENSE) © NordBastion OÜ. This is an open-source client for the NordBastion API; "NordBastion" is a trademark of NordBastion OÜ.
