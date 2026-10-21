"""Cached VLM clients (OpenAI REST, Google Gemini).

Every call is keyed by (model, prompt, image hashes, parameters, sample tag) and stored on
disk, so re-running an experiment re-reads results instead of re-buying them, and the
raw responses stay available for re-scoring. Errors are stored too: an API fault must
surface in the validity battery (protocol compliance), never vanish into a retry loop.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import threading
import time

import requests

CACHE = pathlib.Path(__file__).resolve().parents[2] / "cache" / "vlm"

# USD per 1M tokens (input, output), list prices; used only for cost estimates.
PRICES = {
    "gpt-4o-2024-11-20": (2.50, 10.00),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4.1-2025-04-14": (2.00, 8.00),
    "gpt-4.1-mini-2025-04-14": (0.40, 1.60),
    "gemini-3.5-flash": (0.30, 2.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "global.anthropic.claude-sonnet-5": (3.00, 15.00),
    "global.anthropic.claude-haiku-4-5-20251001-v1:0": (1.00, 5.00),
    "us.amazon.nova-pro-v1:0": (0.80, 3.20),
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class VLM:
    """ask(prompt, images, sample) -> {"text", "usage", "latency", "error", "cached"}."""

    provider = "base"

    def __init__(self, model: str, temperature: float | None = 0.7, max_tokens: int = 8192,
                 cache_dir: pathlib.Path = CACHE, thinking_budget: int | None = None):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.thinking_budget = thinking_budget
        self.cache_dir = cache_dir / model
        self._lock = threading.Lock()
        self.calls = 0
        self.cache_hits = 0

    # ---- cache
    def _key(self, prompt: str, images: list[bytes], sample: str) -> str:
        payload = {"model": self.model, "prompt": prompt, "images": [sha(i) for i in images],
                   "temperature": self.temperature, "max_tokens": self.max_tokens, "sample": sample}
        if self.thinking_budget is not None:
            payload["thinking_budget"] = self.thinking_budget
        return sha(json.dumps(payload, sort_keys=True).encode())

    def ask(self, prompt: str, images: list[bytes], sample: str = "0", allow_network: bool = True) -> dict:
        key = self._key(prompt, images, sample)
        path = self.cache_dir / key[:2] / f"{key}.json"
        if path.exists():
            out = json.loads(path.read_text())
            with self._lock:
                self.cache_hits += 1
            return dict(out, cached=True)
        if not allow_network:
            return {"text": None, "usage": {}, "latency": 0.0, "error": "not cached", "cached": False}
        t0 = time.time()
        text, usage, error = None, {}, None
        for attempt in range(6):
            try:
                text, usage = self._call(prompt, images)
                error = None
                break
            except RetryableError as e:
                error = str(e)
                time.sleep(min(60, 2 ** attempt * 2))
            except Exception as e:  # noqa: BLE001  (non-retryable: record and surface)
                error = f"{type(e).__name__}: {e}"
                if "client has been closed" in error and attempt < 5:   # local client fault, not the model
                    GeminiVLM._local.client = None
                    continue
                break
        out = {"text": text, "usage": usage, "latency": time.time() - t0, "error": error,
               "model": self.model, "sample": sample, "time": time.time()}
        if error is None or not error.startswith("transient"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(out))
        with self._lock:
            self.calls += 1
        return dict(out, cached=False)

    def _call(self, prompt: str, images: list[bytes]) -> tuple[str, dict]:
        raise NotImplementedError


class RetryableError(Exception):
    pass


class OpenAIVLM(VLM):
    provider = "openai"
    URL = "https://api.openai.com/v1/chat/completions"

    def _call(self, prompt, images):
        content = [{"type": "text", "text": prompt}]
        for img in images:
            content.append({"type": "image_url", "image_url": {
                "url": "data:image/png;base64," + base64.b64encode(img).decode(), "detail": "high"}})
        body = {"model": self.model, "messages": [{"role": "user", "content": content}],
                "response_format": {"type": "json_object"}}
        if self.model.startswith(("gpt-5", "o3", "o4")):
            body["max_completion_tokens"] = self.max_tokens
        else:
            body["max_tokens"] = self.max_tokens
            if self.temperature is not None:
                body["temperature"] = self.temperature
        r = requests.post(self.URL, json=body, timeout=120,
                          headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
        if r.status_code == 429 and any(k in r.text for k in ("billing_not_active", "insufficient_quota")):
            raise RuntimeError(f"HTTP 429 (account): {r.text[:200]}")   # not a rate limit: fail fast
        if r.status_code in (429, 500, 502, 503, 504):
            raise RetryableError(f"transient HTTP {r.status_code}")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        d = r.json()
        u = d.get("usage", {})
        return d["choices"][0]["message"]["content"], {"input": u.get("prompt_tokens", 0),
                                                        "output": u.get("completion_tokens", 0)}


class GeminiVLM(VLM):
    provider = "gemini"
    _local = threading.local()     # one client per thread: a shared client can be closed under us

    def _call(self, prompt, images):
        from google import genai
        from google.genai import errors, types
        client = getattr(GeminiVLM._local, "client", None)
        if client is None:
            client = GeminiVLM._local.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        parts = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images] + [prompt]
        cfg = types.GenerateContentConfig(
            response_mime_type="application/json", max_output_tokens=self.max_tokens, temperature=self.temperature,
            thinking_config=None if self.thinking_budget is None else types.ThinkingConfig(thinking_budget=self.thinking_budget))
        try:
            resp = client.models.generate_content(model=self.model, contents=parts, config=cfg)
        except errors.APIError as e:
            if getattr(e, "code", None) in (429, 500, 502, 503, 504):
                raise RetryableError(f"transient {e.code}") from e
            raise
        u = resp.usage_metadata
        usage = {"input": getattr(u, "prompt_token_count", 0) or 0,
                 "output": (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0),
                 "thoughts": getattr(u, "thoughts_token_count", 0) or 0}
        return resp.text, usage


class BedrockVLM(VLM):
    """Anthropic / Amazon / Meta models through the Bedrock Converse API."""
    provider = "bedrock"
    _client = None

    def _call(self, prompt, images):
        import boto3
        from botocore.config import Config as BotoConfig
        from botocore.exceptions import ClientError
        if BedrockVLM._client is None:
            session = boto3.Session(profile_name=os.environ.get("EAV_AWS_PROFILE", "gamania-aws-profile"))
            BedrockVLM._client = session.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"),
                                                config=BotoConfig(read_timeout=180, retries={"max_attempts": 2}))
        content = [{"image": {"format": "png", "source": {"bytes": img}}} for img in images]
        content.append({"text": prompt + "\nAnswer with the JSON object only."})
        inf = {"maxTokens": self.max_tokens}
        # Claude 5 models reject `temperature` ("deprecated for this model"): sampling stays
        # at the provider default, which is stochastic, so repeated readings still differ.
        if self.temperature is not None and "claude" not in self.model:
            inf["temperature"] = self.temperature
        try:
            resp = BedrockVLM._client.converse(modelId=self.model, messages=[{"role": "user", "content": content}],
                                               inferenceConfig=inf)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException",
                        "InternalServerException"):
                raise RetryableError(f"transient {code}") from e
            raise
        parts = resp["output"]["message"]["content"]
        text = "".join(p.get("text", "") for p in parts)
        u = resp.get("usage", {})
        return text, {"input": u.get("inputTokens", 0), "output": u.get("outputTokens", 0)}


def make(name: str, **kw) -> VLM:
    if name.startswith("gemini"):
        return GeminiVLM(name, **kw)
    if name.startswith(("global.", "us.", "eu.", "apac.")):
        return BedrockVLM(name, **kw)
    return OpenAIVLM(name, **kw)


def cost(model: str, usage: dict) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return (usage.get("input", 0) * pin + usage.get("output", 0) * pout) / 1e6
