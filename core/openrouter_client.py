"""
OpenRouter API Client for VoxNav
Uses OpenRouter's free tier for LLM access with automatic fallback.
"""

import os
import json
import logging
import time
from typing import Optional, Dict, Any, Generator

import requests

logger = logging.getLogger(__name__)

# Free models to try (in order of preference) - 2024/2025 models
FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",  # Meta Llama 3.2
    "qwen/qwen3-4b:free",                      # Qwen3 4B
    "google/gemma-3-4b-it:free",               # Google Gemma 3
    "mistralai/mistral-small-3.1-24b-instruct:free",  # Mistral Small
    "deepseek/deepseek-r1-0528:free",          # DeepSeek R1
]

DEFAULT_MODEL = FREE_MODELS[0]


class OpenRouterClient:
    """
    OpenRouter API client for VoxNav.
    Uses OpenAI-compatible API format with automatic model fallback.
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key. If not provided, reads from OPENROUTER_API_KEY env.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key not provided. Set OPENROUTER_API_KEY env variable.")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://voxnav.app",
            "X-Title": "VoxNav Voice Assistant"
        }
        
        logger.info("OpenRouter client initialized successfully.")
    
    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        stream: bool = False
    ) -> str:
        """
        Generate a response with automatic model fallback on rate limits.
        
        Args:
            prompt: User prompt/message
            model: Primary model to use
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum output tokens
            stream: Whether to stream the response
            
        Returns:
            Generated text response
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        # Try primary model first, then fallbacks
        models_to_try = [model] + [m for m in FREE_MODELS if m != model]
        last_error = None
        
        for i, try_model in enumerate(models_to_try):
            payload = {
                "model": try_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream
            }
            
            try:
                if stream:
                    return self._generate_stream(payload)
                else:
                    result = self._generate_sync(payload)
                    if i > 0:
                        logger.info(f"Fallback succeeded with model: {try_model}")
                    return result
                    
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Retry on rate limits, timeouts, or model not found
                if any(x in str(e) for x in ["429", "408", "404"]) or "rate" in error_str or "timeout" in error_str:
                    logger.warning(f"Model {try_model} unavailable, trying next...")
                    time.sleep(0.5)  # Brief pause before trying next
                    continue
                else:
                    # Other errors - don't retry
                    raise
        
        # All models failed
        logger.error(f"All {len(models_to_try)} models failed!")
        raise Exception(f"All free models are unavailable. Please wait and try again. Last error: {last_error}")
    
    def _generate_sync(self, payload: Dict[str, Any]) -> str:
        """Synchronous generation."""
        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code != 200:
            error_msg = response.text
            raise Exception(f"OpenRouter API error: {response.status_code} - {error_msg}")
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _generate_stream(self, payload: Dict[str, Any]) -> Generator[str, None, None]:
        """Streaming generation."""
        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self.headers,
            json=payload,
            stream=True,
            timeout=120
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code}")
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            full_response += content
                            yield content
                    except json.JSONDecodeError:
                        continue
        
        return full_response
    
    def chat(
        self,
        messages: list[Dict[str, str]],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        max_tokens: int = 1024
    ) -> str:
        """
        Multi-turn chat completion.
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        return self._generate_sync(payload)


# Singleton instance
_client: Optional[OpenRouterClient] = None


def get_client() -> OpenRouterClient:
    """Get or create the OpenRouter client singleton."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client


def generate(prompt: str, **kwargs) -> str:
    """Convenience function for generation."""
    return get_client().generate(prompt, **kwargs)
