import unittest
from unittest.mock import PropertyMock, patch

from app.cores.factory import EngineFactory
import app.cores.factory as factory_module


class FactoryRoutingTests(unittest.TestCase):
    def setUp(self):
        self.factory = EngineFactory()

    def test_global_ollama_force_beats_model_engine_override(self):
        with patch.object(factory_module.settings, "find_model", return_value={"engine": "vllm"}):
            with patch.object(type(factory_module.settings), "ENGINE", new_callable=PropertyMock, return_value="ollama"):
                with patch.object(type(factory_module.settings), "HOST_PLATFORM", new_callable=PropertyMock, return_value="dgpu"):
                    self.assertEqual(self.factory.resolve_chat_engine_name("LLM"), "ollama")

    def test_model_engine_override_used_when_not_forced(self):
        with patch.object(factory_module.settings, "find_model", return_value={"engine": "ollama"}):
            with patch.object(type(factory_module.settings), "ENGINE", new_callable=PropertyMock, return_value="vllm"):
                with patch.object(type(factory_module.settings), "HOST_PLATFORM", new_callable=PropertyMock, return_value="dgpu"):
                    self.assertEqual(self.factory.resolve_chat_engine_name("custom-model"), "ollama")

    def test_model_type_vlm_routes_to_ollama_without_name_heuristic(self):
        with patch.object(factory_module.settings, "find_model", return_value={"type": "vlm"}):
            with patch.object(type(factory_module.settings), "ENGINE", new_callable=PropertyMock, return_value="vllm"):
                with patch.object(type(factory_module.settings), "HOST_PLATFORM", new_callable=PropertyMock, return_value="dgpu"):
                    self.assertEqual(self.factory.resolve_chat_engine_name("my-vision-model"), "ollama")


if __name__ == "__main__":
    unittest.main()
