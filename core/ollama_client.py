"""
Ollama Client for VoxNav
Local LLM inference using Ollama - faster and no rate limits.
"""

import json
import logging
from typing import Optional, Dict, Any, Generator

import requests

logger = logging.getLogger(__name__)

# Recommended models for intent classification (smaller = faster)
RECOMMENDED_MODELS = [
    "llama3.2:3b",      # Fast, good for classification
    "phi3:mini",        # Very fast, Microsoft's small model
    "mistral:7b",       # Good balance of speed and quality
    "gemma2:2b",        # Google's small model
    "qwen2.5:3b",       # Alibaba's model, good for multilingual
]

DEFAULT_MODEL = "llama3.2:3b"


class OllamaClient:
    """
    Ollama client for local LLM inference.
    Much faster than cloud APIs with no rate limits.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = DEFAULT_MODEL):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama server URL (default: localhost:11434)
            model: Model to use for inference
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._check_connection()
    
    def _check_connection(self):
        """Check if Ollama is running and the model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]
                logger.info(f"Ollama connected. Available models: {model_names}")
                
                # Check if our model is available
                if not any(self.model.split(":")[0] in name for name in model_names):
                    logger.warning(f"Model {self.model} not found. You may need to pull it: ollama pull {self.model}")
            else:
                logger.warning(f"Ollama connection check failed: {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning("Ollama not running. Start it with: ollama serve")
        except Exception as e:
            logger.warning(f"Ollama check failed: {e}")
    
    def is_available(self) -> bool:
        """Check if Ollama is available and responding."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> list:
        """List available Ollama models."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                return [m.get("name") for m in response.json().get("models", [])]
        except:
            pass
        return []
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
        stream: bool = False
    ) -> str:
        """
        Generate a response from the model.
        
        Args:
            prompt: User prompt
            model: Model to use (default: instance model)
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            stream: Whether to stream (not implemented yet)
            
        Returns:
            Generated text
        """
        model = model or self.model
        
        # Build the full prompt
        full_prompt = ""
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        else:
            full_prompt = prompt
        
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.status_code} - {response.text}")
            
            result = response.json()
            return result.get("response", "")
            
        except requests.exceptions.ConnectionError:
            raise Exception("Ollama not running. Start with: ollama serve")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
    
    def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 500
    ) -> str:
        """
        Chat completion (multi-turn).
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Max tokens
            
        Returns:
            Assistant response
        """
        model = model or self.model
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama error: {response.status_code}")
            
            result = response.json()
            return result.get("message", {}).get("content", "")
            
        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            raise


# Singleton instance
_client: Optional[OllamaClient] = None


def get_client(model: str = DEFAULT_MODEL) -> OllamaClient:
    """Get or create Ollama client singleton."""
    global _client
    if _client is None:
        _client = OllamaClient(model=model)
    return _client


def is_ollama_available() -> bool:
    """Quick check if Ollama is running."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False
