from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path


AGENTVERSE_ROOT = Path(__file__).resolve().parents[1]
if str(AGENTVERSE_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTVERSE_ROOT))

import frontend_proxy_lambda  # noqa: E402


class EnvPatch:
    def __init__(self, **updates: str):
        self.updates = updates
        self.previous: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in self.updates.items():
            self.previous[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, exc_type, exc, tb):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def event(method: str, path: str, body: dict | None = None) -> dict:
    return {
        "requestContext": {"http": {"method": method}},
        "rawPath": path,
        "body": json.dumps(body or {}),
    }


class FrontendProxyLambdaBoundaryTests(unittest.TestCase):
    def test_health_endpoint_is_transport_health_only(self):
        response = frontend_proxy_lambda.handler(event("GET", "/health"), None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["service"], "3d-rams-agentcore-proxy")

    def test_legacy_fastapi_product_routes_are_not_exposed(self):
        calls: list[dict] = []
        original_invoke = frontend_proxy_lambda.invoke_runtime_json
        frontend_proxy_lambda.invoke_runtime_json = lambda **kwargs: calls.append(kwargs) or {"output": {}}
        try:
            for path in ("/api/chat", "/api/run", "/api/session/start", "/api/upload-url"):
                response = frontend_proxy_lambda.handler(event("POST", path, {"message": "hello"}), None)
                self.assertEqual(response["statusCode"], 404, path)
        finally:
            frontend_proxy_lambda.invoke_runtime_json = original_invoke

        self.assertEqual(calls, [])

    def test_invoke_forwards_entry_payload_without_product_orchestration(self):
        calls: list[dict] = []
        original_invoke = frontend_proxy_lambda.invoke_runtime_json

        def fake_invoke_runtime(**kwargs):
            calls.append(kwargs)
            return {"output": {"entryAgent": {"status": "confirmation_required"}}}

        frontend_proxy_lambda.invoke_runtime_json = fake_invoke_runtime
        try:
            with EnvPatch(
                AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:eu-west-2:123456789012:runtime/entry-test",
                AGENTCORE_PROXY_USER_ID="3d-rams-test-frontend",
            ):
                response = frontend_proxy_lambda.handler(
                    event(
                        "POST",
                        "/invoke",
                        {
                            "entryTurn": True,
                            "caller": "frontend",
                            "conversationId": "frontend-demo-session",
                            "message": "8 Albert Embankment tomorrow survey",
                        },
                    ),
                    None,
                )
        finally:
            frontend_proxy_lambda.invoke_runtime_json = original_invoke

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(len(calls), 1)
        forwarded = calls[0]["payload"]
        self.assertTrue(forwarded["entryTurn"])
        self.assertEqual(forwarded["caller"], "frontend")
        self.assertEqual(forwarded["frontendConversationId"], "frontend-demo-session")
        self.assertEqual(forwarded["message"], "8 Albert Embankment tomorrow survey")
        self.assertNotIn("input", forwarded)
        self.assertEqual(calls[0]["runtime_arn"], "arn:aws:bedrock-agentcore:eu-west-2:123456789012:runtime/entry-test")
        self.assertEqual(calls[0]["user_id"], "3d-rams-test-frontend")


if __name__ == "__main__":
    unittest.main()
