"""AI 推荐服务 - 调用用户配置的 OpenAI 兼容 API

支持 DeepSeek / OpenAI / 各类中转站（OpenAI 兼容 /chat/completions）
URL/Key 存于 UserProfile，由用户在"我的"页面配置
"""
import json
import urllib.request
import urllib.error

DEFAULT_API_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


class AIError(Exception):
    pass


def call_ai(api_url, api_key, system_prompt, user_prompt, model=None, temperature=0.7):
    """调用 OpenAI 兼容 chat/completions，返回文本回复"""
    if not api_key:
        raise AIError("未配置 AI Key，请到「我的」页面填写")

    base = (api_url or DEFAULT_API_URL).rstrip("/")
    url = base + "/chat/completions"
    # 若用户填的 base 已带 /chat/completions，则不重复拼接
    if base.endswith("/chat/completions"):
        url = base

    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": 2000,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise AIError(f"AI 接口返回 {e.code}: {body}")
    except urllib.error.URLError as e:
        raise AIError(f"无法连接 AI 接口: {e.reason}")
    except Exception as e:
        raise AIError(f"AI 调用失败: {e}")

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        raise AIError(f"AI 返回格式异常: {json.dumps(data, ensure_ascii=False)[:200]}")
