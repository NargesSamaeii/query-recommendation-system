"""
Direct CLI usage of NL2SPARQL pipeline
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nl2sparql import NL2SPARQLPipeline
from nl2sparql.utils import detect_schema_from_question

# Get question from command line or use default
if len(sys.argv) > 1:
    question = " ".join(sys.argv[1:])
else:
    question = "Who is Ms. Brant and what department does she work in?"

# Auto-detect appropriate schema based on question
schema_path = detect_schema_from_question(question)
if not schema_path:
    print("[ERROR] No schema files found in data/output/")
    sys.exit(1)

# Initialize pipeline
pipeline = NL2SPARQLPipeline()

print(f"\nQuestion: {question}\n")
print(f"Schema: {os.path.basename(schema_path)}\n")
print("="*60)

# Process the question
results = pipeline.answer_question(question, schema_path)

# Display SPARQL query
if "sparql_query" in results:
    print("\n[QUERY] Generated SPARQL Query:")
    print("-"*60)
    print(results["sparql_query"])
    print("-"*60)

# Display results
if "formatted_results" in results:
    print("\n[OK] Query Results:")
    print("-"*60)
    print(results["formatted_results"])
    print("-"*60)
else:
    print("\n[EMPTY] No results found")

# Display intermediate steps (optional)
print("\n[INFO] Intermediate Steps:")
if "relevant_classes" in results.get("intermediate", {}):
    print(f"  Relevant Classes: {results['intermediate']['relevant_classes']}")
if "property_selection" in results.get("intermediate", {}):
    print(f"  Property Selection: {results['intermediate']['property_selection']}")

print("\n" + "="*60)
print("[OK] Complete!")
