# Three-minute demonstration

1. **Problem (30 seconds):** A merchant operations team needs order status and warehouse stock without manually navigating Uniware. Explain that the agent reads only the fields needed for this question.
2. **Run (60 seconds):** Execute `python demo.py` or `.\run.ps1 demo`. Show discovery of six tools, OAuth login/refresh, recovery from the injected 429, both processing-order pages, order search/get and inventory lookup.
3. **Edge cases (30 seconds):** TOTE-01 is a confirmed zero. UNKNOWN-SKU is missing. An unknown order produces a sanitized tool error. No customer contacts, addresses or tokens appear in output.
4. **Verification (30 seconds):** Run `python -m unittest discover -s tests -v`. Show tests for expired tokens, rejected credentials, limits, redirects, facility scope, invalid arguments and HTTP-200 business failures.
5. **Limits (30 seconds):** State clearly that this demonstration uses a fictional local Uniware simulator and a scripted MCP client. No live tenant, LLM or Agent Studio attachment is claimed. Describe the environment variables and connection check needed for an authorized tenant.

The saved `demo-output.txt` and `verification.txt` are captured from a successful local run. No real customer data or credentials are needed to reproduce them.
