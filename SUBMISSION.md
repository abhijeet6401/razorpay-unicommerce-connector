# Submission note

I chose assignment 3 and built a private Unicommerce connector for merchant operations. It exposes six read-only MCP tools for order list/search/get, known-SKU inventory snapshots, and connection verification. OAuth login and token refresh run inside the connector; credentials never enter the agent's tool arguments or outputs.

The implementation includes explicit facility scope, bounded rate-limit retries, pagination, input validation, a read-endpoint allowlist and customer-data minimization. A one-command local demo exercises the actual connector over HTTP and MCP using fictional merchant records, including token expiry, HTTP 429 recovery, zero versus missing stock, and a rejected order lookup.

Setup and run instructions are in README.md. AGENT_CAPABILITIES.md describes the agent's boundaries, tools.json is the exported MCP specification, and DEMO_GUIDE.md provides a presentation sequence. The tests and captured output are reproducible without external accounts or third-party Python packages.

An authorized Unicommerce tenant and Razorpay Agent Studio environment were unavailable. Accordingly, the submission verifies the local connector path and documents the live configuration, without claiming a live deployment or measured merchant impact.
