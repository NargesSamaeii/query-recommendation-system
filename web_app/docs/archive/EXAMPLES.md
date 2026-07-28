# Example Usage

This document provides practical examples of using NL2SPARQL.

## Basic Workflow

### 1. Prepare Your SHACL Schema

Place your SHACL Turtle (.ttl) files in the `data/input/` directory:

```bash
cp your_schema.ttl data/input/
```

### 2. Extract Schema

```bash
nl2sparql extract data/input/your_schema.ttl
```

This generates `data/output/your_schema_mschema.json`

### 3. Ask Questions

```bash
nl2sparql query "Your question here?" --schema data/output/your_schema_mschema.json
```

## Example Questions by Domain

### Academic Domain

```bash
# Who won the Turing Award?
nl2sparql query "Who won the Turing Award?" --schema data/output/academic_mschema.json

# Which universities are in California?
nl2sparql query "Which universities are in California?" --schema data/output/academic_mschema.json
```

### Geographic Domain

```bash
# What is the capital of France?
nl2sparql query "What is the capital of France?" --schema data/output/countries_mschema.json

# Find countries whose motto contains 'freedom'
nl2sparql query "Find countries whose motto contains 'freedom'" --schema data/output/countries_mschema.json
```

### Entertainment Domain

```bash
# Who are the actors born in Rome?
nl2sparql query "Who are the actors born in Rome?" --schema data/output/actors_mschema.json

# List movies directed by Christopher Nolan
nl2sparql query "List movies directed by Christopher Nolan" --schema data/output/movies_mschema.json
```

## Python API Examples

### Basic Usage

```python
from nl2sparql import NL2SPARQLPipeline

# Initialize
pipeline = NL2SPARQLPipeline()

# Extract schema (do this once)
schema = pipeline.extract_schema("data/input/schema.ttl")

# Answer questions
results = pipeline.answer_question(
    "Who are the actors born in Rome?",
    "data/output/schema_mschema.json"
)

# Print results
print(results["formatted_results"])
```

### Custom Configuration

```python
from nl2sparql import NL2SPARQLPipeline, Config

# Create custom config
config = Config()
config.config["llm"]["provider"] = "openai"
config.config["llm"]["model_name"] = "gpt-4"
config.config["sparql"]["default_limit"] = 100

# Initialize with custom config
pipeline = NL2SPARQLPipeline()
pipeline.config = config

# Use pipeline
results = pipeline.answer_question(
    "Your question?",
    "data/output/schema_mschema.json"
)
```

### Batch Processing

```python
from nl2sparql import NL2SPARQLPipeline
import json

pipeline = NL2SPARQLPipeline()

questions = [
    "Who won the Turing Award in 2020?",
    "Which universities are in California?",
    "Who are the actors born in Rome?"
]

schema_path = "data/output/schema_mschema.json"

all_results = []
for question in questions:
    print(f"\nProcessing: {question}")
    results = pipeline.answer_question(question, schema_path)
    all_results.append({
        "question": question,
        "sparql": results.get("sparql_query"),
        "results": results.get("formatted_results")
    })

# Save all results
with open("batch_results.json", "w") as f:
    json.dump(all_results, f, indent=2)
```

### Using Individual Components

```python
from nl2sparql import (
    SHACLSchemaParser,
    SchemaFormatter,
    ClassRelevanceEvaluator,
    create_llm
)

# Parse schema
parser = SHACLSchemaParser(fix_syntax=True)
schema = parser.parse("input.ttl", "output.json")

# Format schema
formatter = SchemaFormatter(schema)
formatted = formatter.format_clean()

# Initialize LLM
llm = create_llm("gemini", api_key="your_key")

# Evaluate class relevance
evaluator = ClassRelevanceEvaluator(llm)
relevant = evaluator.evaluate(
    "Who are the actors born in Rome?",
    formatted
)

print(f"Relevant classes: {relevant}")
```

## Interactive Mode Examples

Start interactive mode:

```bash
nl2sparql interactive --schema data/output/schema_mschema.json
```

Then interact:

```
Question: Who won the Turing Award in 2020?
[Results displayed...]

Question: Which universities are in California?
[Results displayed...]

Question: schema data/output/another_schema.json
Schema changed to: data/output/another_schema.json

Question: exit
Goodbye!
```

## Tips for Better Results

1. **Be Specific**: More specific questions yield better results
   - ❌ "Tell me about actors"
   - ✅ "Who are the actors born in Rome?"

2. **Use Complete Sentences**: Frame questions naturally
   - ❌ "actors Rome"
   - ✅ "Which actors were born in Rome?"

3. **Match Schema Vocabulary**: Use terms that appear in your schema
   - If schema uses "birthPlace", ask "born in" rather than "from"

4. **Check Intermediate Results**: Use `--show-query` to see generated SPARQL
   ```bash
   nl2sparql query "Your question?" --schema schema.json --show-query
   ```

5. **Save Results for Analysis**:
   ```bash
   nl2sparql query "Your question?" --schema schema.json --output result.json
   ```

## Troubleshooting

### Schema Extraction Fails

```bash
# Enable verbose mode
nl2sparql extract input.ttl --verbose

# Check if syntax fixing helps
# (enabled by default, but can verify in config.yaml)
```

### No Results Returned

- Check if your SPARQL endpoint is accessible
- Verify the schema contains relevant classes
- Use interactive mode to iterate on questions

### LLM Errors

- Verify API keys in `.env` file
- Check token limits in `config.yaml`
- Try different LLM providers

## Advanced Examples

### Custom SPARQL Endpoint

Edit `config.yaml`:

```yaml
sparql:
  endpoint_url: "https://your-endpoint.com/sparql"
  timeout: 60
  default_limit: 100
```

### Using Local Mistral Model

1. Download model:
   ```bash
   huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
     mistral-7b-instruct-v0.2.Q2_K.gguf --local-dir .
   ```

2. Edit `config.yaml`:
   ```yaml
   llm:
     provider: "mistral"
     mistral:
       model_path: "mistral-7b-instruct-v0.2.Q2_K.gguf"
       n_ctx: 2048
   ```

3. Use normally:
   ```bash
   nl2sparql query "Your question?" --schema schema.json
   ```
