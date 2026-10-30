"""Model access for hal-memory: a thin layer over `halkit.llm`, and the GPU guard.

Every model call (chat, embeddings) goes through `halkit.llm`, which reaches the Hal gateway with
role aliases (`hal-chat`, `hal-embed`). Nothing here names Ollama or a model URL, and a missing
gateway raises `Unavailable` rather than falling back to another route. Two things stay local
because `halkit.llm` leaves them to the caller: retries with a growing pause, and the GPU guard
that makes model work wait while another program holds the GPU. Stdlib only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from collections.abc import Iterator, Mapping, Sequence

from halkit import llm as kitllm

from .config import shared

log = logging.getLogger(__name__)

# Any gateway failure, including a stopped gateway (`ModelUnavailable` is a subclass).
Unavailable = kitllm.GatewayError

CHAT_ALIAS = "hal-chat"
EMBED_ALIAS = "hal-embed"
RETRY_PAUSE = 3.0  # seconds, times the attempt number
JSON_HINT = "\n\nReply with one JSON object and nothing else."
FENCE = re.compile(r"^```[a-zA-Z]*\n(.*?)\n?```$", re.S)

# Hal's own GPU users: Ollama, the voice server and speech recognition.
OWN = ("ollama", "GPT-SoVITS", "api_v2.py", "hal-voice", "halvoice", "faster_whisper")


def gpu_busy() -> str | None:
    """Returns the name of a program other than Hal's own that is using the GPU, or None."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    ignore = OWN + tuple(shared().get("gpu_ignore", []))
    others = []
    for line in out.splitlines():
        pid, _, name = line.partition(",")
        try:
            cmd = (
                open(f"/proc/{pid.strip()}/cmdline", "rb")
                .read()
                .replace(b"\0", b" ")
                .decode(errors="ignore")
            )
        except OSError:
            cmd = name
        if not any(i in cmd or i in name for i in ignore):
            others.append(name.strip().rsplit("/", 1)[-1])
    return ", ".join(others) or None


def chat_model() -> str:
    """Returns the chat model: HAL_MODEL when the launcher sets one, else the `hal-chat` alias."""
    return os.environ.get("HAL_MODEL") or CHAT_ALIAS


def chat_messages(
    messages: Sequence[Mapping[str, object]],
    *,
    model: str | None = None,
    temperature: float | None = None,
    json_out: bool = False,
    timeout: float = 300,
    retries: int = 0,
) -> str:
    """Returns the model's reply to a conversation, retrying failed calls with a growing pause."""
    msgs = [dict(m) for m in messages]
    if json_out:
        if temperature is None:
            temperature = 0.1
        # `halkit.llm.chat` has no JSON mode, so the prompt asks for it.
        if msgs and msgs[0].get("role") == "system":
            msgs[0]["content"] = f"{msgs[0]['content']}{JSON_HINT}"
        else:
            msgs.insert(0, {"role": "system", "content": JSON_HINT.strip()})
    for attempt in range(retries + 1):
        try:
            return kitllm.chat(
                msgs, model=model or chat_model(), timeout=timeout, temperature=temperature
            )
        except kitllm.GatewayError as e:
            if attempt == retries:
                raise Unavailable(f"chat failed after {retries + 1} tries: {e}") from e
            log.warning("chat try %d failed: %s", attempt + 1, e)
            time.sleep(RETRY_PAUSE * (attempt + 1))
    raise AssertionError("unreachable")


def chat(
    system: str,
    user: str,
    *,
    model: str | None = None,
    json_out: bool = False,
    images: list[str] | None = None,
    timeout: float = 300,
    **kw,
) -> str:
    """Returns the model's reply to one prompt; images are base64 JPEG strings."""
    content: object = user
    if images:
        content = [{"type": "text", "text": user}] + [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}}
            for b in images
        ]
    return chat_messages(
        [{"role": "system", "content": system}, {"role": "user", "content": content}],
        model=model,
        json_out=json_out,
        timeout=timeout,
        **kw,
    )


def stream_chat(
    system: str, user: str, *, model: str | None = None, timeout: float = 300
) -> Iterator[str]:
    """Yields the model's reply to one prompt in chunks as it streams."""
    return kitllm.stream_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model or chat_model(),
        timeout=timeout,
    )


def chat_json(system: str, user: str, **kw) -> dict:
    """Returns the model's JSON reply as a dict, or {} when it is not a JSON object."""
    out = chat(system, user, json_out=True, **kw).strip()
    fenced = FENCE.match(out)
    try:
        data = json.loads(fenced.group(1) if fenced else out)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def embed(texts: list[str], timeout: float = 120) -> list[list[float]]:
    """Returns one embedding per text; the gateway decides where the embedding model runs."""
    return kitllm.embed(texts, model=EMBED_ALIAS, timeout=timeout)
