"""One model identity and credential for all three integrated modules."""
import os
from dataclasses import dataclass, field

from . import bootstrap
from yueji_qa.providers import ChatClient


@dataclass(frozen=True)
class ModelConfig:
    provider: str = "aliyun"
    name: str = "deepseek-v4.1-flash"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = field(default="", repr=False)
    # Beijing peak, uncached CNY prices per million tokens, verified 2026-11-14.
    input_price: float = 2.0
    output_price: float = 8.0

    @classmethod
    def from_env(cls):
        provider = os.getenv("MODEL_PROVIDER", "aliyun").lower()
        if provider not in {"aliyun", "deepseek"}:
            raise ValueError("MODEL_PROVIDER 必须是 aliyun 或 deepseek")
        key_name = "DASHSCOPE_API_KEY" if provider == "aliyun" else "DEEPSEEK_API_KEY"
        base = cls.base_url if provider == "aliyun" else "https://api.deepseek.com"
        name = cls.name if provider == "aliyun" else "deepseek-flash"
        return cls(provider=provider, name=os.getenv("MODEL_NAME", name),
                   base_url=os.getenv("MODEL_BASE_URL", base).rstrip("/"),
                   api_key=os.getenv("MODEL_API_KEY", "") or os.getenv(key_name, ""),
                   input_price=float(os.getenv("MODEL_INPUT_CNY_PER_MILLION", "2")),
                   output_price=float(os.getenv("MODEL_OUTPUT_CNY_PER_MILLION", "8")))


class UnifiedChatClient(ChatClient):
    def __init__(self, *args, provider="aliyun", **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = provider

    def _post(self, path, payload, *, limit):
        if self.provider == "aliyun" and path == "/chat/completions":
            payload = dict(payload)
            payload.pop("thinking", None)
            payload["enable_thinking"] = False
        elif self.provider in {'openai','custom'}:
            payload = dict(payload)
            payload.pop('thinking',None)
        return super()._post(path, payload, limit=limit)
