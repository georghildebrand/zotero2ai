# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024-12-30

### Added
- Zotero Bridge Plugin (`zotero-mcp-bridge`) for secure communication.
- Full CRUD support for notes (Create, Read, Update).
- Human-readable friendly names for notes.
- Bearer token authentication (256-bit).
- New `PluginClient` for Python communication with Zotero.
- Contract tests for API validation.

### Changed
- Migrated MCP server from direct SQLite access to Plugin-based API.
- Updated `doctor` command to include basic plugin checks (placeholder).
- Improved error handling for connection issues.

### Security
- Binds HTTP server to `127.0.0.1` only.
- Enforces Bearer token on all endpoints.

## [0.1.0] - 2024-12-29
- Initial release with read-only SQLite access.
- Basic search and list tools.
