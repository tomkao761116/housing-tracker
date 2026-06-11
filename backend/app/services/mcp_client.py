"""MCP Client - Twinkle Hub 連線 (使用 subprocess + curl)"""
import json
import subprocess
from typing import Optional


class MCPClient:
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint.rstrip("/") + "/"
        self.api_key = api_key
        self._initialized = False

    def _call(self, method: str, params: dict | None = None) -> dict:
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        cmd = [
            "curl", "-s", "--max-time", "120",
            self.endpoint,
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json, text/event-stream",
            "-H", f"Authorization: Bearer {self.api_key}",
            "-d", json.dumps(req, ensure_ascii=False)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=130)
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr[:500]}")
        
        # Parse SSE response
        for line in result.stdout.split("\n"):
            if line.startswith("data: "):
                return json.loads(line[6:])
        raise RuntimeError(f"No SSE data response. Output: {result.stdout[:500]}")

    def init(self):
        if not self._initialized:
            self._call("initialize", {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "housing-tracker", "version": "1.0"}
            })
            self._call("notifications/initialized")
            self._initialized = True

    def tool_call(self, name: str, arguments: dict) -> dict:
        result = self._call("tools/call", {"name": name, "arguments": arguments})
        content = result.get("result", {}).get("content", [{}])[0]
        return json.loads(content.get("text", "{}"))

    def query_rows(self, dataset_id: str, where: str = None, columns: list = None,
                   group_by: list = None, order_by: str = None, limit: int = 100) -> dict:
        """查詢資料列"""
        args = {"dataset_id": dataset_id, "limit": limit}
        if where:
            args["where"] = where
        if columns:
            args["columns"] = columns
        if group_by:
            args["group_by"] = group_by
        if order_by:
            args["order_by"] = order_by
        return self.tool_call("opendata-query_rows", args)

    def get_dataset(self, dataset_id: str, sample_rows: int = 5) -> dict:
        """取得資料集 metadata"""
        return self.tool_call("opendata-get_dataset", {"dataset_id": dataset_id, "sample_rows": sample_rows})
