"""Tests for `halmem.llm`: model calls go through `halkit.llm`, and nowhere else (REQ-MEM-11)."""

import ast
import io
import json
import unittest
from pathlib import Path
from unittest import mock

from halkit import llm as kitllm

from halmem import llm

PACKAGE = Path(__file__).resolve().parent.parent / "halmem"
# Setup runs `ollama pull` for a standalone install; it is not a model call.
SETUP_ONLY = {"install.py"}
BANNED_IMPORTS = {"urllib.request", "http.client", "requests", "httpx", "ollama"}
BANNED_TEXT = ("/api/chat", "/api/embed", "ollama_url")


class FakeResponse(io.BytesIO):
    """A 200 response whose body is the JSON of `data`."""

    def __init__(self, data: dict) -> None:
        super().__init__(json.dumps(data).encode())


class FakeGateway:
    """Stands in for the `halkit.llm` transport and records each request."""

    def __init__(self, *replies: object) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, path, body, timeout):
        self.calls.append((path, body))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(reply)


def chat_reply(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def patched(gateway: FakeGateway):
    return mock.patch.object(kitllm, "_post", gateway)


class ModelCallTests(unittest.TestCase):
    def test_memory_uses_halkit_llm(self):
        gw = FakeGateway(chat_reply("hi"), {"data": [{"index": 0, "embedding": [0.5, 1]}]})
        with patched(gw), mock.patch.dict("os.environ", {}, clear=False):
            self.assertEqual(llm.chat("sys", "user"), "hi")
            self.assertEqual(llm.embed(["a"]), [[0.5, 1.0]])
        (chat_path, chat_body), (embed_path, embed_body) = gw.calls
        self.assertEqual(chat_path, "/v1/chat/completions")
        self.assertEqual(chat_body["model"], "hal-chat")
        self.assertEqual(embed_path, "/v1/embeddings")
        self.assertEqual(embed_body["model"], "hal-embed")

    def test_stream_chat_yields_chunks(self):
        lines = [
            b'data: {"choices": [{"delta": {"content": "a"}}]}\n',
            b'data: {"choices": [{"delta": {"content": "b"}}]}\n',
            b"data: [DONE]\n",
        ]
        resp = mock.MagicMock()
        resp.__iter__.return_value = iter(lines)
        with mock.patch.object(kitllm, "_post", return_value=resp):
            self.assertEqual("".join(llm.stream_chat("s", "u")), "ab")

    def test_failed_chat_is_retried_then_succeeds(self):
        gw = FakeGateway(kitllm.ModelUnavailable("down"), chat_reply("ok"))
        with patched(gw), mock.patch.object(llm.time, "sleep") as sleep:
            self.assertEqual(llm.chat("s", "u", retries=1), "ok")
        sleep.assert_called_once_with(llm.RETRY_PAUSE)
        self.assertEqual(len(gw.calls), 2)

    def test_chat_raises_unavailable_after_the_last_retry(self):
        gw = FakeGateway(kitllm.ModelUnavailable("down"), kitllm.ModelUnavailable("down"))
        with patched(gw), mock.patch.object(llm.time, "sleep"):
            with self.assertRaises(llm.Unavailable):
                llm.chat("s", "u", retries=1)

    def test_stopped_gateway_does_not_fall_back_to_another_route(self):
        with mock.patch.object(kitllm, "_endpoint", side_effect=kitllm.ModelUnavailable("off")):
            with self.assertRaises(llm.Unavailable):
                llm.chat("s", "u")

    def test_json_reply_in_a_code_fence_is_parsed(self):
        gw = FakeGateway(chat_reply('```json\n{"a": 1}\n```'))
        with patched(gw):
            self.assertEqual(llm.chat_json("s", "u"), {"a": 1})
        self.assertIn("JSON", gw.calls[0][1]["messages"][0]["content"])
        self.assertEqual(gw.calls[0][1]["temperature"], 0.1)

    def test_non_json_reply_gives_an_empty_dict(self):
        with patched(FakeGateway(chat_reply("sorry"))):
            self.assertEqual(llm.chat_json("s", "u"), {})

    def test_images_travel_as_image_url_parts(self):
        gw = FakeGateway(chat_reply("seen"))
        with patched(gw):
            llm.chat("s", "describe", images=["QUJD"])
        part = gw.calls[0][1]["messages"][1]["content"][1]
        self.assertTrue(part["image_url"]["url"].endswith("QUJD"))

    def test_hal_model_env_overrides_the_alias(self):
        with mock.patch.dict("os.environ", {"HAL_MODEL": "custom"}):
            self.assertEqual(llm.chat_model(), "custom")


class AnswererDefaultTests(unittest.TestCase):
    def test_answerer_defaults_to_local_never_claude(self):
        """Directive I4: Claude Code is never called unless the user sets the key."""
        from halmem import search

        with mock.patch.dict("os.environ", {"HAL_CONFIG": "/nonexistent/c.toml"}):
            os_env = __import__("os").environ
            os_env.pop("HAL_ANSWERER", None)
            self.assertEqual(search.answerer(), "local")


class SourceScanTests(unittest.TestCase):
    def sources(self):
        return [p for p in PACKAGE.rglob("*.py") if p.name not in SETUP_ONLY and p.name != "llm.py"]

    def test_no_direct_ollama_calls(self):
        found = []
        for path in self.sources():
            text = path.read_text()
            for node in ast.walk(ast.parse(text)):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                found += [f"{path.name}: import {n}" for n in names if n in BANNED_IMPORTS]
            found += [f"{path.name}: {t}" for t in BANNED_TEXT if t in text]
        self.assertEqual(found, [])

    def test_llm_module_reaches_models_only_through_halkit(self):
        text = (PACKAGE / "llm.py").read_text()
        for banned in (*BANNED_TEXT, "urllib.request", "http.client"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
