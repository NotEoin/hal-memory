"""Local model access, and the GPU guard that keeps it polite.

Chat goes to Ollama, or to an OpenAI-style server (the hal launcher's llama.cpp
router) when HAL_CHAT_API=openai; HAL_CHAT_URL and HAL_MODEL pick the server and
model. Embeddings always come from Ollama. Model work waits while another program
(a training run, a llama.cpp server) holds the GPU. Stdlib only.
"""
import json
import os
import subprocess
import time
import urllib.request

from .config import shared


class Unavailable(Exception):
    pass


# Hal's own GPU users: Ollama, the voice server and speech recognition.
OWN = ("ollama", "GPT-SoVITS", "api_v2.py", "hal-voice", "halvoice", "faster_whisper")


def gpu_busy() -> str | None:
    """Returns the name of a program other than Hal's own that is using the GPU, or None."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    ignore = OWN + tuple(shared().get("gpu_ignore", []))
    others = []
    for line in out.splitlines():
        pid, _, name = line.partition(",")
        try:
            cmd = open(f"/proc/{pid.strip()}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="ignore")
        except OSError:
            cmd = name
        if not any(i in cmd or i in name for i in ignore):
            others.append(name.strip().rsplit("/", 1)[-1])
    return ", ".join(others) or None


def _post(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (OSError, ValueError) as e:
        raise Unavailable(f"{url}: {e}") from e


def _ollama(path: str) -> str:
    return shared()["ollama_url"].rstrip("/") + path


def chat_api() -> str:
    """Returns the chat protocol: "ollama", or "openai" for an OpenAI-style server."""
    return os.environ.get("HAL_CHAT_API", "ollama")


def chat_model() -> str:
    """Returns the chat model: HAL_MODEL when the hal launcher sets one, else [hal].chat_model."""
    return os.environ.get("HAL_MODEL") or shared()["chat_model"]


def chat_messages(messages: list[dict], *, model: str | None = None, temperature: float | None = None,
                  json_out: bool = False, timeout: float = 300, retries: int = 0) -> str:
    """Returns the model's reply to a conversation, retrying failed calls with a growing pause."""
    base = (os.environ.get("HAL_CHAT_URL") or shared()["ollama_url"]).rstrip("/")
    payload = {"model": model or chat_model(), "messages": messages, "stream": False}
    if json_out and temperature is None:
        temperature = 0.1
    if chat_api() == "openai":
        url = base + "/v1/chat/completions"
        # Thinking costs minutes per call on the CPU modes and adds nothing here.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        if temperature is not None:
            payload["temperature"] = temperature
        if json_out:
            payload["response_format"] = {"type": "json_object"}
    else:
        url = base + "/api/chat"
        payload["think"] = False
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        if json_out:
            payload["format"] = "json"
    for attempt in range(retries + 1):
        try:
            data = _post(url, payload, timeout)
            if chat_api() == "openai":
                return data["choices"][0]["message"].get("content") or ""
            return data["message"]["content"] or ""
        except (Unavailable, KeyError, IndexError, TypeError) as e:
            if attempt == retries:
                raise Unavailable(f"chat failed after {retries + 1} tries: {e}") from e
            time.sleep(3 * (attempt + 1))
    raise AssertionError("unreachable")


def chat(system: str, user: str, *, model: str | None = None, json_out: bool = False,
         images: list[str] | None = None, timeout: float = 300, **kw) -> str:
    """Returns the model's reply to one prompt; images are base64 strings."""
    msg: dict = {"role": "user", "content": user}
    if images and chat_api() == "openai":
        msg["content"] = [{"type": "text", "text": user}] + [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in images]
    elif images:
        msg["images"] = images
    return chat_messages([{"role": "system", "content": system}, msg], model=model, json_out=json_out,
                         timeout=timeout, **kw)


def chat_json(system: str, user: str, **kw) -> dict:
    out = chat(system, user, json_out=True, **kw)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def embed(texts: list[str], timeout: float = 120) -> list[list[float]]:
    """Returns one embedding per text."""
    payload = {"model": shared()["embed_model"], "input": texts}
    if shared().get("embed_on_cpu"):
        # A small embedding model runs well on the CPU and leaves the GPU's memory alone.
        payload["options"] = {"num_gpu": 0}
    return _post(_ollama("/api/embed"), payload, timeout)["embeddings"]
