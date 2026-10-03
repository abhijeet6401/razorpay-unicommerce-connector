"""Fictional merchant HTTP -> connector subprocess -> MCP client, in one command."""
import json
import os
from pathlib import Path
import subprocess
import sys
from mock_store import DEMO_USER, DEMO_PASSWORD, FACILITY, merchant


def run_demo():
    with merchant() as (url, state):
        env = {**os.environ, "UC_BASE_URL": url, "UC_USERNAME": DEMO_USER,
               "UC_PASSWORD": DEMO_PASSWORD, "UC_FACILITY": FACILITY, "UC_DEMO": "1"}
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18",
             "capabilities": {}, "clientInfo": {"name": "assignment-demo", "version": "1.0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
        calls = [("connection_check", {}), ("list_orders", {"status": "PROCESSING", "limit": 1}),
                 ("list_orders", {"status": "PROCESSING", "limit": 1, "offset": 1}),
                 ("get_order", {"code": "SO-1002"}), ("search_orders", {"display_order_code": "WEB-1001"}),
                 ("get_inventory", {"sku": "MUG-01"}),
                 ("list_inventory", {"skus": ["TOTE-01", "UNKNOWN-SKU"]}),
                 ("get_order", {"code": "MISSING-ORDER"})]
        for ident, (name, args) in enumerate(calls, 3):
            messages.append({"jsonrpc": "2.0", "id": ident, "method": "tools/call",
                             "params": {"name": name, "arguments": args}})
        state["failures"] = [(429, {"Retry-After": "0"})]
        state["expire_once"] = True
        process = subprocess.run([sys.executable, str(Path(__file__).with_name("connector.py"))],
                                 input="\n".join(json.dumps(m) for m in messages) + "\n",
                                 text=True, encoding="utf-8", capture_output=True, env=env, timeout=30)
        assert process.returncode == 0, process.stderr
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        assert len(replies) == 10
        assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
        assert len(replies[1]["result"]["tools"]) == 6
        outputs = [r["result"] for r in replies[2:]]
        assert all(not r["isError"] for r in outputs[:-1])
        assert outputs[-1]["isError"]
        assert outputs[1]["structuredContent"]["next_offset"] == 1
        assert outputs[2]["structuredContent"]["next_offset"] is None
        assert outputs[3]["structuredContent"]["record"]["status"] == "CANCELLED"
        assert outputs[4]["structuredContent"]["records"][0]["code"] == "SO-1001"
        assert outputs[5]["structuredContent"]["records"][0]["inventory"] == 8
        assert outputs[6]["structuredContent"]["records"][0]["inventory"] == 0
        assert outputs[6]["structuredContent"]["missing_skus"] == ["UNKNOWN-SKU"]
        assert state["grants"] == ["password", "refresh_token"]
        assert len(state["requests"]) == 10
        for private in ("notificationEmail", "notificationMobile", "addresses", "additionalInfo",
                        DEMO_PASSWORD, "fictional-access", "fictional-refresh"):
            assert private not in process.stdout
        print("UNICOMMERCE FICTIONAL DEMO - no live tenant, Agent Studio or language model used")
        print("MCP initialized; discovered 6 read-only tools")
        print("OAuth header login -> injected 401 -> token refresh -> injected 429 -> successful retry")
        for (name, args), response in zip(calls, outputs):
            print("\n" + name + " " + json.dumps(args))
            print(json.dumps(json.loads(response["content"][0]["text"]), indent=2))
        print("\nPASS: OAuth, refresh, facility scope, pagination, search, inventory, privacy and errors")


if __name__ == "__main__":
    run_demo()
