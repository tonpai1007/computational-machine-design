"""
MDIE Multi-Provider LLM Router & Smart Switching Engine
Supports Groq, OpenRouter, Google Gemini, and Local Ollama with automatic cascading failover
and deterministic offline heuristic fallback.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("ai.llm_router")


def load_dotenv(env_path: Optional[Path] = None) -> None:
    """Lightweight zero-dependency .env loader that populates os.environ."""
    if env_path is None:
        candidates = [
            Path(".env"),
            Path(__file__).resolve().parent.parent.parent / ".env"
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                env_path = c
                break

    if not env_path or not env_path.exists() or not env_path.is_file():
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ and val:
                    os.environ[key] = val
    except Exception:
        pass


# Auto-load .env on import
load_dotenv()


class LLMRouter:
    """
    Intelligent LLM Model Router with Cascading Multi-Provider Failover.
    Attempts fastest / lowest-cost providers first (Groq -> OpenRouter -> Gemini -> Local/Offline).
    """

    # Default model selections for each provider
    DEFAULT_MODELS = {
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "meta-llama/llama-3.3-70b-instruct",
        "gemini": "gemini-1.5-flash",
        "ollama": "llama3.2"
    }

    @classmethod
    def get_configured_providers(cls) -> List[str]:
        """
        Detects which LLM providers have available API keys or active endpoints in priority order.
        User can override priority via MDIE_LLM_PROVIDER environment variable (e.g. 'groq,openrouter,gemini').
        """
        env_pref = os.environ.get("MDIE_LLM_PROVIDER")
        if env_pref:
            providers = [p.strip().lower() for p in env_pref.split(",") if p.strip()]
            return providers

        available = []
        if os.environ.get("GROQ_API_KEY"):
            available.append("groq")
        if os.environ.get("OPENROUTER_API_KEY"):
            available.append("openrouter")
        if os.environ.get("GEMINI_API_KEY"):
            available.append("gemini")
        if os.environ.get("OLLAMA_HOST") or os.environ.get("MDIE_USE_OLLAMA"):
            available.append("ollama")

        return available

    @classmethod
    def call_chat_completion(
        cls,
        system_prompt: str,
        user_prompt: str,
        response_format_json: bool = True,
        max_tokens: int = 1500,
        temperature: float = 0.1
    ) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Executes a prompt across the cascading provider chain.
        Returns:
            (response_text, winning_provider, execution_logs)
        If all remote providers fail or no keys are configured, returns (None, None, logs).
        """
        logs: List[str] = []
        providers = cls.get_configured_providers()

        if not providers:
            logs.append("No LLM API keys found (GROQ_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY). Using offline deterministic engine.")
            return None, None, logs

        for provider in providers:
            try:
                logs.append(f"Attempting LLM call via '{provider.upper()}'...")
                response_text = None

                if provider == "groq":
                    response_text = cls._call_groq(system_prompt, user_prompt, response_format_json, max_tokens, temperature)
                elif provider == "openrouter":
                    response_text = cls._call_openrouter(system_prompt, user_prompt, response_format_json, max_tokens, temperature)
                elif provider == "gemini":
                    response_text = cls._call_gemini(system_prompt, user_prompt, response_format_json, max_tokens, temperature)
                elif provider == "ollama":
                    response_text = cls._call_ollama(system_prompt, user_prompt, response_format_json, max_tokens, temperature)

                if response_text:
                    logs.append(f"Successfully received response from '{provider.upper()}'.")
                    return response_text, provider, logs

            except Exception as e:
                logs.append(f"Provider '{provider.upper()}' failed: {str(e)}. Cascading to next fallback...")

        logs.append("All configured LLM providers failed. Dropping back to deterministic offline parser.")
        return None, None, logs

    # =========================================================================
    # Provider Implementations (Zero Proprietary SDK Lock-in, Pure HTTP)
    # =========================================================================

    @classmethod
    def _call_groq(
        cls,
        system_prompt: str,
        user_prompt: str,
        response_format_json: bool,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call Groq API (Ultra-low latency inference, ~500 tok/s)."""
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set.")

        model = os.environ.get("GROQ_MODEL", cls.DEFAULT_MODELS["groq"])
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        return cls._post_http(url, headers, payload)

    @classmethod
    def _call_openrouter(
        cls,
        system_prompt: str,
        user_prompt: str,
        response_format_json: bool,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call OpenRouter API (Universal gateway to 200+ models)."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set.")

        model = os.environ.get("OPENROUTER_MODEL", cls.DEFAULT_MODELS["openrouter"])
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mdie-engine",
            "X-Title": "MDIE Machine Design Engine"
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        return cls._post_http(url, headers, payload)

    @classmethod
    def _call_gemini(
        cls,
        system_prompt: str,
        user_prompt: str,
        response_format_json: bool,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call Google Gemini API via official REST endpoint."""
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        model = os.environ.get("GEMINI_MODEL", cls.DEFAULT_MODELS["gemini"])
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        headers = {"Content-Type": "application/json"}
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": f"System Instructions:\n{system_prompt}\n\nUser Request:\n{user_prompt}"}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if response_format_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        import urllib.request
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            candidates = resp_data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemini returned empty candidates list.")
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text

    @classmethod
    def _call_ollama(
        cls,
        system_prompt: str,
        user_prompt: str,
        response_format_json: bool,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call Local Ollama API."""
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        model = os.environ.get("OLLAMA_MODEL", cls.DEFAULT_MODELS["ollama"])
        url = f"{host}/api/chat"

        headers = {"Content-Type": "application/json"}
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": temperature}
        }
        if response_format_json:
            payload["format"] = "json"

        import urllib.request
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            return resp_data.get("message", {}).get("content", "")

    # =========================================================================
    # Common HTTP Dispatcher using httpx (or standard library urllib fallback)
    # =========================================================================

    @staticmethod
    def _post_http(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> str:
        """Standardized JSON POST request handler with robust error diagnostics."""
        try:
            import httpx
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"HTTP {res.status_code}: {res.text[:300]}")
                data = res.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("API returned empty choices list.")
                return choices[0].get("message", {}).get("content", "")
        except ImportError:
            # Fallback to standard library urllib
            import urllib.request
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("API returned empty choices list.")
                return choices[0].get("message", {}).get("content", "")
