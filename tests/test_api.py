import unittest

from fastapi.testclient import TestClient

from app.main import app
from app import routes


class _FakeChatEngine:
    async def chat_completion(self, payload: dict):
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": payload.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


class _RecordingFakeChatEngine:
    def __init__(self, content: str = "ok"):
        self.last_payload = None
        self.content = content

    async def chat_completion(self, payload: dict):
        self.last_payload = payload
        return {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": payload.get("model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": self.content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }


class _FakeEmbeddingEngine:
    def embed(self, inputs, model_name=None):
        return [[0.1, 0.2, 0.3] for _ in inputs]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._orig_map_model_alias = routes.factory.map_model_alias
        self._orig_resolve_chat_engine = routes.factory.resolve_chat_engine
        self._orig_embedding = routes.factory.embedding

    def tearDown(self):
        routes.factory.map_model_alias = self._orig_map_model_alias
        routes.factory.resolve_chat_engine = self._orig_resolve_chat_engine
        routes.factory.embedding = self._orig_embedding

    def test_health_check(self):
        res = self.client.get("/health_check")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

    def test_chat_completion_method_not_allowed(self):
        res = self.client.get("/v1/chat/completions")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["detail"], "Method Not Allowed")
        self.assertIn("Use POST /v1/chat/completions", body["hint"])

    def test_chat_completion_success(self):
        routes.factory.map_model_alias = lambda m: m
        routes.factory.resolve_chat_engine = lambda _m: _FakeChatEngine()

        payload = {
            "model": "qwen3:4b-instruct",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
        }
        res = self.client.post("/v1/chat/completions", json=payload)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["model"], "qwen3:4b-instruct")
        self.assertEqual(data["choices"][0]["message"]["content"], "ok")

    def test_chat_completion_llm_alias_maps_internal_model_and_preserves_requested_model(self):
        fake_engine = _RecordingFakeChatEngine(content="llm-ok")
        routes.factory.map_model_alias = lambda m: "qwen3:4b-instruct" if m == "LLM_SMALL" else m
        routes.factory.resolve_chat_engine = lambda _m: fake_engine

        payload = {
            "model": "LLM_SMALL",
            "messages": [{"role": "user", "content": "ping llm"}],
            "stream": False,
        }
        res = self.client.post("/v1/chat/completions", json=payload)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["model"], "LLM_SMALL")  # external API keeps requested model label
        self.assertEqual(data["choices"][0]["message"]["content"], "llm-ok")
        self.assertIsNotNone(fake_engine.last_payload)
        self.assertEqual(fake_engine.last_payload["model"], "qwen3:4b-instruct")

    def test_chat_completion_vlm_alias_maps_internal_model_and_preserves_requested_model(self):
        fake_engine = _RecordingFakeChatEngine(content="vlm-ok")
        routes.factory.map_model_alias = lambda m: "qwen3-vl:4b-instruct" if m == "VLM_SMALL" else m
        routes.factory.resolve_chat_engine = lambda _m: fake_engine

        payload = {
            "model": "VLM_SMALL",
            "messages": [{"role": "user", "content": "ping vlm"}],
            "stream": False,
        }
        res = self.client.post("/v1/chat/completions", json=payload)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["model"], "VLM_SMALL")
        self.assertEqual(data["choices"][0]["message"]["content"], "vlm-ok")
        self.assertIsNotNone(fake_engine.last_payload)
        self.assertEqual(fake_engine.last_payload["model"], "qwen3-vl:4b-instruct")

    def test_embeddings_disabled(self):
        routes.factory.embedding = None

        payload = {"model": "Qwen/Qwen3-Embedding-4B", "input": "hello"}
        res = self.client.post("/v1/embeddings", json=payload)

        self.assertEqual(res.status_code, 400)
        self.assertIn("Embedding is disabled", res.json()["detail"])

    def test_embeddings_success(self):
        routes.factory.map_model_alias = lambda m: m
        routes.factory.embedding = _FakeEmbeddingEngine()

        payload = {"model": "Qwen/Qwen3-Embedding-4B", "input": ["hello", "world"]}
        res = self.client.post("/v1/embeddings", json=payload)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["model"], "Qwen/Qwen3-Embedding-4B")
        self.assertEqual(len(data["data"]), 2)
        self.assertEqual(len(data["data"][0]["embedding"]), 3)

    def test_embeddings_alias_model_maps_and_preserves_requested_model(self):
        class _RecordingFakeEmbeddingEngine:
            def __init__(self):
                self.last_model_name = None
                self.last_inputs = None

            def embed(self, inputs, model_name=None):
                self.last_inputs = inputs
                self.last_model_name = model_name
                return [[0.1, 0.2, 0.3] for _ in inputs]

        fake_engine = _RecordingFakeEmbeddingEngine()
        routes.factory.map_model_alias = lambda m: "Qwen/Qwen3-Embedding-4B" if m == "Embedding" else m
        routes.factory.embedding = fake_engine

        payload = {"model": "Embedding", "input": "hello embedding"}
        res = self.client.post("/v1/embeddings", json=payload)

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["model"], "Qwen/Qwen3-Embedding-4B")
        self.assertEqual(fake_engine.last_model_name, "Qwen/Qwen3-Embedding-4B")
        self.assertEqual(fake_engine.last_inputs, ["hello embedding"])


if __name__ == "__main__":
    unittest.main()
