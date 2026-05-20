# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-20

### Added
- Initial release of the NordBastion MCP server (stdio transport).
- 34 tools mirroring the NordBastion REST API v1 across Auth, Account,
  Billing, Catalog, Servers, SSH keys, Webhooks and Transparency.
- Resources: `nordbastion://catalog`, `nordbastion://coins`,
  `nordbastion://canary`, `nordbastion://doctrine`.
- `onboard_to_nordbastion` prompt for a guided account → top-up → order flow.
- API-key auth via `NORDBASTION_API_KEY`; public tools work with no key.
