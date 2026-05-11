from __future__ import annotations

import os


# 大模型最小回复字数保护。
MIN_REPLY_CHARS = 0

# OpenAI 兼容接口配置（默认使用 DeepSeek）。
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.deepseek.com")
API_MODEL = os.getenv("API_MODEL", "deepseek-chat")
API_KEY_ENV_VAR = "API_KEY"

PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com",
        "default_model": "gpt-4o",
    },
    "dashscope": {
        "name": "阿里通义千问 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode",
        "default_model": "qwen-plus",
    },
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-plus",
    },
    "moonshot": {
        "name": "月之暗面 Moonshot",
        "base_url": "https://api.moonshot.cn",
        "default_model": "moonshot-v1-8k",
    },
    "siliconflow": {
        "name": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn",
        "default_model": "deepseek-ai/DeepSeek-V3",
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "default_model": "",
    },
}


def resolve_api_config(provider: str = "", api_base_url: str = "", api_model: str = "") -> tuple[str, str]:
    if api_base_url and api_model:
        return api_base_url, api_model
    if provider and provider in PROVIDERS:
        p = PROVIDERS[provider]
        resolved_url = api_base_url or p["base_url"] or API_BASE_URL
        resolved_model = api_model or p["default_model"] or API_MODEL
        return resolved_url, resolved_model
    return api_base_url or API_BASE_URL, api_model or API_MODEL
