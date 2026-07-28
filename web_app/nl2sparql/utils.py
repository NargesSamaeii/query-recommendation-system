"""
Utility functions for NL2SPARQL
"""

from pathlib import Path
from typing import Optional


def detect_schema_from_question(question: str, schema_dir: str = "data/output") -> Optional[str]:
    """
    Intelligently detect which schema to use based on question keywords.
    
    Args:
        question: The natural language question
        schema_dir: Directory containing schema files
    
    Returns:
        Full path to the selected schema file, or None if not found
    """
    question_lower = question.lower()
    schema_dir_path = Path(schema_dir)
    
    # Define keyword patterns for each schema
    schemas = {
        "coporate_mschema.json": ["brant", "department", "employee", "staff", "person", "name", "manager", "organization", "working", "works"],
        "copypu_mschema.json": ["port", "longitude", "latitude", "location", "maritime", "sea", "shipping", "harbor"],
        "dbpedia_mschema.json": ["dbpedia", "wiki", "entity", "wikipedia"],
        "movie_mschema.json": ["movie", "film", "watch", "genre", "director", "review", "actor", "recommendation", "subscription", "streaming"],
        "tourism_mschema.json": ["church", "chiese", "verona", "tour", "event", "art", "museum", "poi", "attraction", "sightseeing"],
    }
    
    # Check which schema matches best
    for schema_file, keywords in schemas.items():
        schema_path = schema_dir_path / schema_file
        if schema_path.exists():
            if any(keyword in question_lower for keyword in keywords):
                return str(schema_path)
    
    # Default: return first available schema
    if schema_dir_path.exists():
        schema_files = list(schema_dir_path.glob("*_mschema.json"))
        if schema_files:
            return str(schema_files[0])
    
    return None


def list_available_schemas(schema_dir: str = "data/output") -> list:
    """
    Get list of available schema files.
    
    Args:
        schema_dir: Directory containing schema files
    
    Returns:
        List of schema file names
    """
    schema_dir_path = Path(schema_dir)
    if schema_dir_path.exists():
        return sorted([f.name for f in schema_dir_path.glob("*_mschema.json")])
    return []
