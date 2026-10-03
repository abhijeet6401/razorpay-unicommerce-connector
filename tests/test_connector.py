import email.utils
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from connector import Connector, ConnectorError, Server, UniClient, SEARCH, GET_ORDER, INVENTORY
from mock_store import DEMO_USER, DEMO_PASSWORD, FACILITY, merchant


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.context = merchant()
        self.url, self.state = self.context.__enter__()
        self.waits = []
        self.client = UniClient(self.url, DEMO_USER, DEMO_PASSWORD, FACILITY, demo=True, sleep=self.waits.append)
        self.connector = Connector(self.client)

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def error(self, code, callback):
        with self.assertRaises(ConnectorError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_authenticated_reads_and_projection(self):
        self.assertTrue(self.connector.call("connection_check", {})["authenticated"])
        order = self.connector.call("get_order", {"code": "SO-1001"})["record"]
        for private in ("notificationEmail", "notificationMobile", "addresses", "additionalInfo"):
            self.assertNotIn(private, order)
        self.assertEqual(order["items"][0]["itemSku"], "MUG-01")
        self.assertEqual(self.state["grants"], ["password"])
        self.assertTrue(all(r["facility"] == FACILITY for r in self.state["requests"]))

    def test_rejected_credentials(self):
        client = UniClient(self.url, DEMO_USER, "wrong", FACILITY, demo=True)
        self.error("authentication", lambda: client.read(SEARCH, {}))
        self.assertEqual(self.state["requests"], [])

    def test_pagination_and_filters(self):
        first = self.connector.call("list_orders", {"status": "PROCESSING", "limit": 1})
        second = self.connector.call("list_orders", {"status": "PROCESSING", "limit": 1, "offset": first["next_offset"]})
        self.assertEqual(first["total"], 2)
        self.assertNotEqual(first["records"][0]["code"], second["records"][0]["code"])
        self.assertIsNone(second["next_offset"])

    def test_search_and_empty_results(self):
        self.assertEqual(self.connector.call("search_orders", {"display_order_code": "WEB-1002"})["total"], 1)
        self.assertEqual(self.connector.call("search_orders", {"display_order_code": "WEB & MISSING"})["records"], [])
        self.assertEqual(self.state["requests"][-1]["body"]["displayOrderCode"], "WEB & MISSING")

    def test_inventory_missing_is_not_zero(self):
        result = self.connector.call("list_inventory", {"skus": ["TOTE-01", "UNKNOWN"]})
        self.assertEqual(result["records"][0]["inventory"], 0)
        self.assertEqual(result["missing_skus"], ["UNKNOWN"])

    def test_list_summary_does_not_claim_empty_order_items(self):
        result = self.connector.call("list_orders", {})
        self.assertNotIn("items", result["records"][0])

    def test_wrong_order_identity_is_rejected(self):
        self.state["raw"] = '{"successful":true,"saleOrderDTO":{"code":"OTHER"}}'
        self.error("invalid_response", lambda: self.connector.call("get_order", {"code": "SO-1001"}))

    def test_inventory_quantities_must_be_numbers(self):
        self.state["raw"] = '{"successful":true,"inventorySnapshots":[{"itemTypeSKU":"MUG-01","inventory":"zero"}]}'
        self.error("invalid_response", lambda: self.connector.call("get_inventory", {"sku": "MUG-01"}))

    def test_validation_prevents_network_requests(self):
        for args in ({"code": True}, {"code": ""}, {"code": "SO-1", "url": "x"}, {}):
            self.error("invalid_arguments", lambda: self.connector.call("get_order", args))
        for args in ({"limit": 101}, {"offset": -1}, {"offset": True}, {"status": "invalid"}):
            self.error("invalid_arguments", lambda: self.connector.call("list_orders", args))
        for skus in ([], ["x", "x"], [None], ["x"]*101):
            self.error("invalid_arguments", lambda: self.connector.call("list_inventory", {"skus": skus}))
        self.error("unknown_tool", lambda: self.connector.call("cancel_order", {"code": "SO-1001"}))
        self.error("forbidden", lambda: self.client.read("/services/rest/v1/oms/saleOrder/create", {}))
        self.assertEqual(self.state["requests"], [])
        self.assertEqual(self.state["grants"], [])

    def test_token_refresh_on_401(self):
        self.state["expire_once"] = True
        self.connector.call("list_orders", {})
        self.assertEqual(self.state["grants"], ["password", "refresh_token"])
        self.assertEqual(len(self.state["requests"]), 2)

    def test_proactive_token_refresh(self):
        self.connector.call("list_orders", {})
        self.client.expires_at = time.monotonic() - 1
        self.connector.call("list_orders", {})
        self.assertEqual(self.state["grants"], ["password", "refresh_token"])

    def test_invalid_refresh_falls_back_to_login(self):
        self.connector.call("list_orders", {})
        self.client.expires_at = 0
        self.state["reject_refresh"] = True
        self.connector.call("list_orders", {})
        self.assertEqual(self.state["grants"], ["password", "refresh_token", "password"])

    def test_repeated_401_is_bounded(self):
        self.state["failures"] = [(401, {})]*2
        self.error("authentication", lambda: self.connector.call("list_orders", {}))
        self.assertEqual(len(self.state["requests"]), 2)

    def test_rate_limit_recovery(self):
        self.state["failures"] = [(429, {"Retry-After": "2"})]
        self.connector.call("list_orders", {})
        self.assertEqual(self.waits, [2])
        self.assertEqual(len(self.state["requests"]), 2)

    def test_retry_budget(self):
        self.state["failures"] = [(429, {"Retry-After": "0"})]*3
        self.error("rate_limited", lambda: self.connector.call("list_orders", {}))
        self.assertEqual(len(self.state["requests"]), 3)
        self.assertEqual(len(self.waits), 2)

    def test_long_cooldown_is_not_retried_early(self):
        self.state["failures"] = [(429, {"Retry-After": "120"})]
        error = self.error("rate_limited", lambda: self.connector.call("list_orders", {}))
        self.assertEqual(error.retry_after, 120)
        self.assertEqual(self.waits, [])

    def test_http_date_and_fallback(self):
        date = email.utils.format_datetime(datetime.now(timezone.utc)+timedelta(seconds=5), usegmt=True)
        self.assertTrue(0 < self.client.retry_delay(date, 0) <= 5)
        for value in ("invalid", "NaN", "Infinity"):
            self.assertTrue(1 <= self.client.retry_delay(value, 1) <= 1.2)

    def test_transient_server_failure(self):
        self.state["failures"] = [(503, {})]
        self.connector.call("list_orders", {})
        self.assertEqual(len(self.waits), 1)

    def test_permanent_errors_not_retried(self):
        for status, code in ((403, "forbidden"), (404, "not_found"), (400, "upstream_error")):
            self.state["failures"] = [(status, {})]
            self.error(code, lambda: self.connector.call("list_orders", {}))
        self.assertEqual(len(self.state["requests"]), 3)

    def test_redirects_are_blocked(self):
        self.state["redirect"] = "http://127.0.0.1:1/secrets"
        self.error("upstream_error", lambda: self.connector.call("list_orders", {}))
        self.assertEqual(len(self.state["requests"]), 1)

    def test_business_failure_and_warning_are_sanitized(self):
        self.state["business_failure"] = True
        error = self.error("merchant_rejected", lambda: self.connector.call("list_orders", {}))
        self.assertNotIn("PRIVATE", str(error))
        self.state["business_failure"] = False
        self.state["warning"] = True
        self.error("merchant_warning", lambda: self.connector.call("list_orders", {}))

    def test_invalid_upstream_response(self):
        for raw in ("not json", "{}", '{"successful":true,"elements":[{}],"totalRecords":1}',
                    '{"successful":true,"elements":[],"totalRecords":1}'):
            self.state["raw"] = raw
            self.error("invalid_response", lambda: self.connector.call("list_orders", {}))

    def test_transport_failure(self):
        client = UniClient("http://127.0.0.1:1", DEMO_USER, DEMO_PASSWORD, FACILITY, demo=True, sleep=self.waits.append)
        self.error("unavailable", lambda: client.authenticate())
        self.assertEqual(len(self.waits), 2)

    def test_mcp_lifecycle_and_tool_error(self):
        server = Server(self.connector)
        def request(method, params=None):
            return server.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})
        self.assertIn("error", request("tools/list"))
        self.assertEqual(request("initialize", {"protocolVersion": "2025-06-18"})["result"]["protocolVersion"], "2025-06-18")
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(len(request("tools/list")["result"]["tools"]), 6)
        error = request("tools/call", {"name": "get_order", "arguments": {"code": "MISSING"}})["result"]
        self.assertTrue(error["isError"])
        self.assertEqual(json.loads(error["content"][0]["text"])["code"], "merchant_rejected")
        self.assertEqual(request("unsupported")["error"]["code"], -32601)
        self.assertEqual(server.handle({"jsonrpc": "2.0", "method": "ping", "id": {}})["error"]["code"], -32600)


class ConfigurationTests(unittest.TestCase):
    def test_secure_url_requirements(self):
        for url in ("http://example.com", "http://127.0.0.1", "https://user:pass@x.unicommerce.com",
                    "https://x.unicommerce.com/?key=x", "https://evil.example", "https://x.unicommerce.com/path", ""):
            with self.assertRaises(ConnectorError):
                UniClient(url, "user", "password", "facility")
        UniClient("https://example.unicommerce.com", "user", "password", "facility")


if __name__ == "__main__":
    unittest.main()
