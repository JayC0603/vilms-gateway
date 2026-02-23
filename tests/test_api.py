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


class _FakeEmbeddingEngine:
    def embed(self, inputs):
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
        self.assertEqual(res.status_code, 405)

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


if __name__ == "__main__":
    unittest.main()
