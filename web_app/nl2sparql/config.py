"""
Configuration Management Module

Handles loading and managing configuration settings.
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration manager for NL2SPARQL."""
    
    def __init__(self, config_path=None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to config.yaml file (defaults to package root)
        """
        # Load environment variables
        load_dotenv()
        
        # Find config file
        if config_path is None:
            # Try current directory first
            if os.path.exists("config.yaml"):
                config_path = "config.yaml"
            else:
                # Try package directory
                package_dir = Path(__file__).parent.parent
                config_path = package_dir / "config.yaml"
        
        # Load YAML config
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            print(f"Warning: Config file not found at {config_path}. Using defaults.")
            self.config = self._default_config()
    
    def _default_config(self):
        """Return default configuration."""
        return {
            "llm": {
                "provider": "gemini",
                "model_name": "gemini-2.0-flash-exp",
                "max_tokens": 500,
                "temperature": 0.0
            },
            "sparql": {
                "endpoint_url": "http://localhost:8890/sparql",
                "timeout": 30,
                "default_limit": 50,
                "default_graph": "http://localhost:8890/coporateNew"
            },
            "schema": {
                "input_dir": "data/input",
                "output_dir": "data/output",
                "fix_syntax": True
            },
            "pipeline": {
                "stages": {
                    "query_routing": True,
                    "schema_extraction": True,
                    "class_extraction": True,
                    "property_extraction": True,
                    "missing_id_extraction": True,
                    "query_generation": True,
                    "query_execution": True
                },
                "log_level": "INFO",
                "log_file": "logs/nl2sparql.log",
                "evaluation": {
                    "query_execution": {
                        "method": "row_based",
                        "normalize_values": False,
                        "order_matters": False,
                        "order_required_questions": []
                    }
                }
            },
            "output": {
                "format": "json",
                "save_intermediate": True,
                "results_dir": "results"
            },
            "toon": {
                "formatting": {
                    "include_examples": True,
                    "include_descriptions": True,
                    "max_examples": 2
                }
            }
        }
    
    def get(self, key_path, default=None):
        """
        Get configuration value by dot-separated key path.
        
        Args:
            key_path: Dot-separated path (e.g., "llm.provider")
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key_path.split(".")
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_llm_config(self):
        """Get LLM configuration with environment variable overrides."""
        llm_config = self.config.get("llm", {}).copy()
        
        provider = llm_config.get("provider", "gemini")
        
        # Override API key from environment
        if provider == "gemini":
            llm_config["api_key"] = os.getenv("GEMINI_API_KEY", llm_config.get("api_key"))
        elif provider == "openai":
            llm_config["api_key"] = os.getenv("OPENAI_API_KEY", llm_config.get("api_key"))
        
        # Remove parameters that are not for initialization
        llm_config.pop("max_tokens", None)
        llm_config.pop("temperature", None)
        
        # Remove provider-specific nested configs
        llm_config.pop("mistral", None)
        llm_config.pop("openai", None)
        llm_config.pop("gemini", None)
        
        return llm_config
    
    def get_sparql_config(self):
        """Get SPARQL configuration with environment variable overrides."""
        sparql_config = self.config.get("sparql", {}).copy()
        
        # Override endpoint from environment
        endpoint = os.getenv("SPARQL_ENDPOINT")
        if endpoint:
            sparql_config["endpoint_url"] = endpoint
        
        return sparql_config
    
    def get_schema_config(self):
        """Get schema configuration."""
        return self.config.get("schema", {})
    
    def get_pipeline_config(self):
        """Get pipeline configuration."""
        return self.config.get("pipeline", {})
    
    def get_output_config(self):
        """Get output configuration."""
        return self.config.get("output", {})
    
    def get_evaluation_config(self):
        """Get evaluation configuration for query execution."""
        pipeline_config = self.config.get("pipeline", {})
        evaluation_config = pipeline_config.get("evaluation", {})
        query_exec_config = evaluation_config.get("query_execution", {})
        
        return {
            "method": query_exec_config.get("method", "row_based"),
            "normalize_values": query_exec_config.get("normalize_values", False),
            "order_matters": query_exec_config.get("order_matters", False),
            "order_required_questions": query_exec_config.get("order_required_questions", [])
        }
