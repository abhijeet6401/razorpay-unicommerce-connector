# Unicommerce private connector for Agent Studio

**Razorpay Forward-Deployed Engineer assignment · Option 3**

A merchant operations agent can look up a sale order, find processing orders, and check warehouse inventory without opening Uniware or exposing customer contact details to the model. This connector wraps Unicommerce's client REST APIs in six read-only MCP tools.

**What has been verified:** a local HTTP simulator with fictional records, the actual connector subprocess, and an MCP client exercise OAuth login, refresh, order search/get, inventory snapshots, pagination, and failure handling. Automated integration tests use the same HTTP boundary. No real tenant or Razorpay Agent Studio account was available; live tenant access and Agent Studio attachment remain unverified. This is a working connector and reproducible local demonstration, not a claim of deployment in Agent Studio.

## Quick start (no accounts or dependencies)

Requires Python 3.10+; everything uses the standard library. No package installation is needed.

```sh
python demo.py
python -m unittest discover -s tests -v
python connector.py --spec
```

On Windows, use the included launcher. It finds Python on PATH or the bundled Codex Python runtime:

```powershell
.\run.ps1 demo
.\run.ps1 test
```

The demo starts a loopback merchant simulator on a random port, launches the real MCP server, checks responses, prints sanitized results and exits. It uses four fictional orders and three inventory records. Test credentials are clearly fictional constants that authenticate only to the simulator. The demo does not call anyone or send data to an external service.

Expected final line:

```text
PASS: OAuth, refresh, facility scope, pagination, search, inventory, privacy and errors
```

## Configure an authorized tenant

1. Obtain a dedicated authorized Uniware account and its facility code. Unicommerce's published OAuth docs require an admin account with appropriate facility access. The connector's endpoint allowlist limits its operations; it does **not** reduce the account's actual upstream permissions. Confirm API access for your tenant with Unicommerce.
2. Set the following variables in the process that will launch the connector. Use a secret manager or a hidden local prompt for credentials; never commit them or place them in the agent prompt. `.env.example` lists variable names but is not automatically loaded.
3. Run the connection check. It logs in and performs a one-record order search. Success verifies order reads, not inventory permissions; check inventory separately with a known authorized SKU.

PowerShell (password entered through a hidden prompt):

```powershell
$env:UC_BASE_URL = 'https://YOUR_TENANT.unicommerce.com'
$env:UC_USERNAME = Read-Host 'Uniware username'
$env:UC_FACILITY = Read-Host 'Facility code'
$taskCredential = Get-Credential -UserName $env:UC_USERNAME -Message 'Uniware credentials'
$env:UC_PASSWORD = $taskCredential.GetNetworkCredential().Password
$env:UC_DEMO = '0'
.\run.ps1 check
# Clear after you finish the session:
Remove-Item Env:UC_PASSWORD
```

For macOS/Linux, export the same variables securely, then `python connector.py --check`. Avoid passwords in command arguments or shell history. To perform an individual read:

```sh
python connector.py --call get_order '{"code":"SO-1001"}'
python connector.py --call get_inventory '{"sku":"MUG-01"}'
```

Examples use fictional identifiers; substitute tenant records you are authorized to read. PowerShell can pass a JSON string variable to the bundled interpreter if its native argument quoting differs.

## Agent integration

The server implements the MCP **2025-06-18** stdio lifecycle, `ping`, `tools/list`, and `tools/call`. It is deliberately pinned to this protocol revision; it is not an implementation of the newer stateless MCP revision. stdout contains JSON-RPC only. Start it with `python connector.py`; the host must send `initialize`, then `notifications/initialized`, and discover tools.

`tools.json` contains the exported tool descriptions, input schemas and annotations. `mcp-config.example.json` is a generic MCP host configuration: replace absolute executable/script paths and supply credentials to the host process through its secure environment. Do not put secrets into the shared JSON file.

For Agent Studio, attach this as a private stdio MCP connector **if that transport is supported**. Otherwise the equivalent integration is a trusted backend calling `Connector.call(name, arguments)` with the schemas in `tools.json`. That backend must authenticate Agent Studio, bind each merchant to its own configured connector, and keep secrets server-side. No undocumented Razorpay connector registration format is assumed here. A hosted HTTP adapter, tenant routing and Agent Studio-specific registration are outside this submission.

## Tools

| Tool | Inputs | Result |
| --- | --- | --- |
| `connection_check` | none | OAuth + order read access; inventory marked not checked |
| `list_orders` | optional `status`, `channel`, `offset`, `limit` | One page, total, `next_offset` |
| `search_orders` | `display_order_code`, optional list filters | Search by merchant display order code |
| `get_order` | internal sale order `code` | Sanitized order and item status/prices |
| `get_inventory` | exact `sku` | Snapshot in configured facility; missing SKU explicit |
| `list_inventory` | 1–100 unique `skus` | Batched snapshots and missing SKUs |

All order operations are restricted to the configured facility. Inventory supplies the documented `Facility` header. The agent cannot select arbitrary URLs, facilities, raw request bodies, or additional endpoints. Order pages default to 20 and cap at 100; follow `next_offset` until null. Inventory listing is a known-SKU batch, not complete catalog enumeration. The selected snapshot API has no documented pagination, so this connector limits each batch to 100.

## Authentication and resilience

Login uses Unicommerce Authentication2: `GET /oauth/token`, password grant parameters, and username/password **headers**. Tokens stay in memory. The client refreshes before expiry with a clock margin, rotates returned tokens, and renews once after an HTTP 401. An invalid refresh token triggers one fresh login; a repeated read 401 stops. Restarting the process requires login again.

Reads are POST requests to three explicitly allowed read endpoints. HTTP 429/502/503/504 and transport failures receive at most two retries per HTTP operation. Numeric and HTTP-date `Retry-After` are respected. Missing/invalid values use exponential backoff plus jitter. Cooldowns over 10 seconds are returned to the agent as `rate_limited` with `retry_after_seconds`, avoiding an early retry. Socket timeout is 8 seconds and response size is capped at 2 MB. These are per-operation bounds, not a global tool deadline.

Redirects are blocked, TLS verification stays enabled, and live origins must be under `.unicommerce.com`. HTTP is accepted only for loopback with explicit demo mode. Provider error bodies are never echoed. HTTP-200 `successful:false`, warnings, malformed envelopes and incomplete order fetches return sanitized tool errors. Missing orders can produce `merchant_rejected` rather than `not_found`, because Uniware business errors are not guessed from undocumented numeric codes.

Rate-limit policy is tenant/provider dependent; no universal request quota is assumed. This single-process version handles reactive limits, not fleet-wide scheduling. A production deployment should add shared tenant cooldowns, connection pooling, an overall deadline, redacted operational metrics, and an SDK-backed MCP transport.

## Merchant problem and impact

Initial merchant request: “Let an agent read our orders.” The operational question is narrower: “Which processing orders need attention, and is the SKU available in this warehouse?” The connector gives the agent order search/get plus inventory snapshots, while withholding addresses and contact details that are unnecessary for that workflow.

Before rollout, confirm what “needs attention” means, which facilities and channels are in scope, and how often stock changes. Pilot with a synthetic evaluation set, then measure correct answers against Uniware, unresolved lookups, time per investigation, tool failure rate and 429 frequency. No time-saving or accuracy percentage is claimed without merchant measurements.

See [AGENT_CAPABILITIES.md](AGENT_CAPABILITIES.md) for the agent's operating contract and [DEMO_GUIDE.md](DEMO_GUIDE.md) for a short presentation sequence.

## Official API references

Endpoint spelling and payloads follow Unicommerce's **Client Documentation**, not its marketplace APIs (which run in the opposite direction):

- [Authentication2](https://documentation.unicommerce.com/docs/oauth2.html)
- [Token refresh](https://documentation.unicommerce.com/docs/oauth-refreshtoken.html)
- [Order search](https://documentation.unicommerce.com/docs/saleorder-search.html)
- [Order get](https://documentation.unicommerce.com/docs/saleorder-get.html)
- [Inventory snapshot](https://documentation.unicommerce.com/docs/inventory-snapshot.html)
- [MCP stdio 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [MCP tools 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

Official examples contain some inconsistent type descriptions. This implementation uses the documented JSON arrays for `facilityCodes`, the response's `elements`/`totalRecords`, and distinct endpoint casing for order search and get. Verify these against an authorized tenant before deployment.
