# NL2SPARQL Results Storage Format

## Overview

Results are now saved in a **comprehensive JSON format** that captures every stage of the NL2SPARQL pipeline, including:
- Original question
- Schema used at each stage (with and without examples)
- Extracted classes and properties
- Generated queries
- Entity resolution results
- Final SPARQL query and results
- All prompts sent to LLMs
- Statistics and error tracking

## File Location

Results are saved to: `results/result_YYYYMMDD_HHMMSS.json`

## Result Structure

### 1. **Metadata Section**
Contains the question and processing timestamp:
```json
"metadata": {
  "timestamp": "2026-02-23T15:30:45.123456",
  "question": "Who is our Sensor expert?"
}
```

### 2. **Pipeline Section**
The main section with results from each pipeline stage:

#### 2.1 Class Extraction
```json
"pipeline": {
  "class_extraction": {
    "config": {
      "include_examples": true
    },
    "extracted_classes": ["prod_vocab:Employee", "prod_vocab:ProductCategory"],
    "class_count": 2,
    "schema_with_examples": "Prefixes:\n  prod_vocab: ...\nClass Name: prod_vocab:Employee\n...",
    "schema_without_examples": "Prefixes:\n  prod_vocab: ...\nClass Name: prod_vocab:Employee\nClass Examples: (No examples)"
  }
}
```

**Key Fields:**
- `extracted_classes`: List of class names found to be relevant
- `class_count`: Total number of extracted classes
- `config.include_examples`: Whether examples were included in the schema shown to LLM
- `schema_with_examples`: Full schema including class examples
- `schema_without_examples`: Schema without examples (for comparison)

#### 2.2 Property Extraction
```json
"property_extraction": {
  "config": {
    "include_examples": true
  },
  "property_selection": [
    {
      "class_name": "prod_vocab:Employee",
      "relevant_properties": ["ns_0_1:name", "prod_vocab:areaOfExpertise"]
    }
  ],
  "total_properties": 3,
  "schema_with_examples": "...",
  "schema_without_examples": "..."
}
```

**Key Fields:**
- `property_selection`: List of classes with their selected properties
- `total_properties`: Total count of all selected properties across all classes
- `schema_with_examples` and `schema_without_examples`: Schema versions used at this stage

#### 2.3 Missing ID Extraction
```json
"missing_id_extraction": {
  "config": {
    "enabled": true,
    "max_iris": 5
  },
  "missing_id_query": "PREFIX prod_vocab: ...\nSELECT DISTINCT (?entity AS ?IRI) ...",
  "resolved_entities": {
    "Sensor": "http://ld.company.org/prod-instances/prod-cat-Sensor",
    "Driver": "http://ld.company.org/prod-instances/prod-cat-Driver"
  },
  "resolved_count": 2,
  "schema_passed_to_llm": "..."
}
```

**Key Fields:**
- `enabled`: Whether missing ID extraction was performed
- `max_iris`: Limit configured in config (if any)
- `missing_id_query`: SPARQL query generated to resolve entity IRIs
- `resolved_entities`: Map of entity names to their IRIs
- `resolved_count`: Number of entities successfully resolved
- `schema_passed_to_llm`: The schema version that was used to generate the missing ID query

#### 2.4 Query Generation
```json
"query_generation": {
  "config": {
    "include_examples": true
  },
  "generated_query": "PREFIX prod_vocab: ...\nSELECT ?employeeName WHERE { ... }",
  "schema_with_examples": "...",
  "schema_without_examples": "..."
}
```

**Key Fields:**
- `generated_query`: The final SPARQL query that was executed
- `schema_with_examples` and `schema_without_examples`: Schema versions passed to query generator

#### 2.5 Query Execution
```json
"query_execution": {
  "executed_query": "PREFIX prod_vocab: ...\nSELECT ?employeeName WHERE { ... }",
  "query_type": "SELECT",
  "raw_results": {
    "results": {
      "bindings": [
        {
          "employeeName": {
            "type": "literal",
            "value": "John Smith"
          }
        }
      ]
    }
  },
  "formatted_results": "employeeName\nJohn Smith",
  "result_count": 1,
  "execution_error": null
}
```

**Key Fields:**
- `executed_query`: The exact query that was sent to SPARQL endpoint
- `query_type`: Type of query (SELECT, ASK, CONSTRUCT, DESCRIBE)
- `raw_results`: Raw JSON response from SPARQL endpoint
- `formatted_results`: Human-readable formatted results
- `result_count`: Number of results returned
- `execution_error`: Error message if query failed (null if successful)

### 3. **Prompts Section**
Contains all LLM prompts used during processing:

```json
"prompts": {
  "class_extraction_prompts": ["Prompt 1", "Prompt 2", ...],
  "property_extraction_prompts": ["Prompt 1"],
  "missing_id_query_prompt": "Full prompt text...",
  "final_query_generation_prompt": "Full prompt text..."
}
```

**Key Features:**
- All prompts are stored in full for transparency and debugging
- Class/property prompts are arrays (multiple prompts might be used)
- Missing ID and query generation prompts are single strings

### 4. **Statistics Section**
Summary statistics and error tracking:

```json
"statistics": {
  "stages_completed": [
    "class_extraction",
    "property_extraction",
    "missing_id_extraction",
    "query_generation",
    "query_execution"
  ],
  "total_time_ms": 5420,
  "errors": [
    {
      "stage": "query_execution",
      "message": "Connection timeout after 30 seconds",
      "timestamp": "2026-02-23T15:30:50.123456"
    }
  ]
}
```

**Key Fields:**
- `stages_completed`: List of stages that completed successfully
- `total_time_ms`: Total processing time (when tracked)
- `errors`: Array of errors that occurred, with stage, message, and timestamp

## Usage Examples

### Python - Access Results Programmatically

```python
from nl2sparql.results_viewer import get_latest_result, list_all_results

# Get latest result
latest = get_latest_result()
print(latest['metadata']['question'])
print(f"Classes found: {latest['pipeline']['class_extraction']['class_count']}")
print(f"Results: {latest['pipeline']['query_execution']['result_count']}")

# List all results
all_results = list_all_results(limit=5)
for r in all_results:
    print(f"{r['timestamp']} - {r['question']} ({r['classes_extracted']} classes)")

# Get specific result by filename
from nl2sparql.results_viewer import get_result_details
result = get_result_details("result_20260223_153045.json")

# Format for display
from nl2sparql.results_viewer import format_result_for_display
print(format_result_for_display(result))
```

### Compare Two Results

```python
from nl2sparql.results_viewer import compare_results

comparison = compare_results(
    "result_20260223_153045.json",
    "result_20260223_153100.json"
)
print(comparison)
```

### Export to CSV

```python
from nl2sparql.results_manager import ResultsManager

rm = ResultsManager()
rm.export_to_csv("results_analysis.csv")
```

## Schema Comparison

One powerful feature is that both `schema_with_examples` and `schema_without_examples` are stored for each stage. This allows you to:

1. **Debug LLM behavior** - See exactly what schema the LLM saw
2. **Compare decisions** - Check how including/excluding examples affected extraction
3. **Understand filtering** - See which properties were filtered at which stage

## Result File Organization

```
results/
├── result_20260223_153045.json    # First query
├── result_20260223_153100.json    # Second query
├── result_20260223_154230.json    # Third query
└── ...
```

Each file is timestamped and sorted by creation time. Use `list_all_results()` to browse.

## Integration with GUI

Results are accessible from the GUI via the "Results" section which shows:
- ✅ All processed questions
- ✅ Classes and properties extracted
- ✅ Entity IRIs resolved
- ✅ Final SPARQL query
- ✅ Query results
- ✅ Pipeline statistics

## Key Advantages

1. **Complete Transparency** - See every decision the pipeline made
2. **Auditability** - Track exactly what prompts were used and what they produced
3. **Debugging** - Identify where things went wrong
4. **Analysis** - Compare multiple runs to understand patterns
5. **Schema Evolution** - See how schema changes affect results
6. **Reproducibility** - Recreate any result using stored prompts and schemas

## Storage Size Note

Each result file typically contains:
- Full schemas (with examples): ~50-200KB per schema
- 4 stages × 2 schema versions = 8 schema copies
- All prompts (100-500 lines each × 4 stages)
- Full SPARQL results

**Typical file size per result: 500KB - 2MB**

Use `results_viewer.get_summary_stats()` to check total storage used.
