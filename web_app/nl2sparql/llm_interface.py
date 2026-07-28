"""
LLM Interface Module

Provides unified interface to different LLM providers.
"""

import os
from abc import ABC, abstractmethod


class LLMInterface(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(self, prompt, max_tokens=500):
        """Generate response from prompt."""
        pass


class GeminiLLM(LLMInterface):
    """Google Gemini LLM interface."""
    
    def __init__(self, api_key=None, model_name="gemini-2.5-flash", temperature=0.0, seed=None):
        """
        Initialize Gemini LLM.
        
        Args:
            api_key: Gemini API key (reads from env if not provided)
            model_name: Model name to use (e.g., gemini-2.5-flash, gemini-1.5-pro)
            temperature: Sampling temperature (0.0-2.0)
            seed: Optional deterministic seed for generation
        """
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Please install google-generativeai: pip install google-generativeai")
        
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key not provided. Set GEMINI_API_KEY environment variable.")

        try:
            self.temperature = float(temperature)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid Gemini temperature: {temperature}")

        if seed is None or str(seed).strip() == "":
            self.seed = None
        else:
            try:
                self.seed = int(seed)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid Gemini seed: {seed}")

        # Some google-generativeai versions do not support GenerationConfig.seed.
        # Start optimistic and downgrade automatically on first unsupported-field error.
        self._seed_supported = True
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def generate(self, prompt, max_tokens=500):
        """Generate response from Gemini."""
        base_generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": self.temperature,
        }

        generation_config = dict(base_generation_config)
        if self.seed is not None and self._seed_supported:
            generation_config["seed"] = self.seed

        try:
            response = self.model.generate_content(
                contents=prompt,
                generation_config=generation_config
            )
            return response.text.strip()
        except ValueError as exc:
            msg = str(exc)
            if (
                self.seed is not None
                and self._seed_supported
                and "Unknown field" in msg
                and "GenerationConfig" in msg
                and "seed" in msg
            ):
                self._seed_supported = False
                response = self.model.generate_content(
                    contents=prompt,
                    generation_config=base_generation_config
                )
                return response.text.strip()
            raise


class MistralLLM(LLMInterface):
    """Mistral local LLM interface."""
    
    def __init__(self, model_path=None, n_ctx=2048):
        """
        Initialize Mistral LLM.
        
        Args:
            model_path: Path to Mistral GGUF model file
            n_ctx: Context window size
        """
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError("Please install llama-cpp-python: pip install llama-cpp-python")
        
        if model_path is None:
            model_path = "mistral-7b-instruct-v0.2.Q2_K.gguf"
        
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx
        )
    
    def generate(self, prompt, max_tokens=500):
        """Generate response from Mistral."""
        response = self.llm(prompt=prompt, max_tokens=max_tokens)
        
        # Extract text from response
        if isinstance(response, dict) and "choices" in response:
            return response["choices"][0].get("text", "").strip()
        return str(response).strip()


class MistralLLMWrapper:
    """Wrapper for Mistral to provide generate() method matching other LLMs."""
    
    def __init__(self, llm_instance):
        """Wrap an existing Llama instance."""
        self.llm = llm_instance
    
    def generate(self, prompt, max_tokens=500):
        """Generate response from Mistral."""
        response = self.llm(prompt=prompt, max_tokens=max_tokens)
        
        # Extract text from response
        if isinstance(response, dict) and "choices" in response:
            return response["choices"][0].get("text", "").strip()
        return str(response).strip()


class OllamaLLM(LLMInterface):
    """Local Ollama LLM interface -- no API key, no quota/billing, talks to a local
    (or dockerized) Ollama server's HTTP API."""

    def __init__(self, base_url=None, model_name="llama3.1:8b", temperature=0.0):
        """
        Initialize Ollama LLM.

        Args:
            base_url: Ollama server URL (reads from OLLAMA_BASE_URL if not provided,
                defaults to http://localhost:11434)
            model_name: Model tag as pulled via `ollama pull <model_name>`
            temperature: Sampling temperature
        """
        try:
            import requests
        except ImportError:
            raise ImportError("Please install requests: pip install requests")

        self._requests = requests
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model_name = model_name
        self.temperature = float(temperature)

    def generate(self, prompt, max_tokens=500):
        """Generate response from Ollama's /api/generate endpoint."""
        response = self._requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": max_tokens,
                },
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()


class OpenAILLM(LLMInterface):
    """OpenAI LLM interface."""
    
    def __init__(self, api_key=None, model_name="gpt-4", temperature=0.0, seed=None):
        """
        Initialize OpenAI LLM.
        
        Args:
            api_key: OpenAI API key (reads from env if not provided)
            model_name: Model name to use
            temperature: Sampling temperature
            seed: Optional deterministic seed for generation
        """
        try:
            import openai
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable.")
        
        openai.api_key = self.api_key
        self.model_name = model_name
        try:
            self.temperature = float(temperature)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid OpenAI temperature: {temperature}")

        if seed is None or str(seed).strip() == "":
            self.seed = None
        else:
            try:
                self.seed = int(seed)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid OpenAI seed: {seed}")

        self.client = openai.OpenAI(api_key=self.api_key)

    def generate(self, prompt, max_tokens=500):
        """Generate response from OpenAI."""
        request_kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if self.seed is not None:
            request_kwargs["seed"] = self.seed

        response = self.client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content.strip()


class AzureOpenAILLM(LLMInterface):
    """Azure OpenAI LLM interface."""

    def __init__(self, api_key=None, endpoint=None, deployment=None,
                 model_name=None,
                 api_version="2024-02-15-preview", temperature=0.0, seed=None):
        """
        Initialize Azure OpenAI LLM.

        Args:
            api_key: Azure OpenAI API key (reads from AZURE_OPENAI_API_KEY if not provided)
            endpoint: Azure OpenAI endpoint URL (reads from AZURE_OPENAI_ENDPOINT if not provided)
            deployment: Azure deployment name (reads from AZURE_OPENAI_DEPLOYMENT if not provided)
            model_name: Alias for deployment — used as fallback if deployment is not set
            api_version: Azure OpenAI API version
            temperature: Sampling temperature
            seed: Optional deterministic seed
        """
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise ImportError("Please install openai: pip install openai")

        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT") or model_name

        if not self.api_key:
            raise ValueError("Azure OpenAI API key not provided. Set AZURE_OPENAI_API_KEY.")
        if not self.endpoint:
            raise ValueError("Azure OpenAI endpoint not provided. Set AZURE_OPENAI_ENDPOINT.")
        if not self.deployment:
            raise ValueError("Azure OpenAI deployment not provided. Set AZURE_OPENAI_DEPLOYMENT.")

        try:
            self.temperature = float(temperature)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid temperature: {temperature}")

        self.seed = int(seed) if seed not in (None, "") else None

        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=api_version,
            azure_endpoint=self.endpoint,
        )

    def generate(self, prompt, max_tokens=500):
        """Generate response from Azure OpenAI."""
        request_kwargs = {
            "model": self.deployment,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if self.seed is not None:
            request_kwargs["seed"] = self.seed

        response = self.client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content.strip()


def create_llm(provider="gemini", **kwargs):
    """
    Factory function to create LLM instance.

    Args:
        provider: LLM provider (gemini, mistral, ollama, openai, azure)
        **kwargs: Provider-specific arguments

    Returns:
        LLMInterface instance
    """
    if provider.lower() == "gemini":
        return GeminiLLM(**kwargs)
    elif provider.lower() == "mistral":
        return MistralLLM(**kwargs)
    elif provider.lower() == "ollama":
        return OllamaLLM(**kwargs)
    elif provider.lower() == "openai":
        return OpenAILLM(**kwargs)
    elif provider.lower() in ("azure", "azure_openai", "azureopenai"):
        return AzureOpenAILLM(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")