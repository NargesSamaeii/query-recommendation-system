# Results Storage Architecture

## Data Flow

```
User Question
    ↓
[Pipeline Processing]
    ├─ Class Extraction
    │  ├─ Extracted classes → Result
    │  ├─ Schema with examples
    │  ├─ Schema without examples
    │  └─ Prompts used
    │
    ├─ Property Extraction
    │  ├─ Property selection → Result
    │  ├─ Schema with examples
    │  ├─ Schema without examples
    │  └─ Prompts used
    │
    ├─ Missing ID Extraction
    │  ├─ Generated query → Result
    │  ├─ Resolved entities → Result
    │  ├─ Schema passed to LLM
    │  └─ Prompt used
    │
    ├─ Query Generation
    │  ├─ Generated SPARQL → Result
    │  ├─ Schema with examples
    │  ├─ Schema without examples
    │  └─ Prompt used
    │
    └─ Query Execution
       ├─ Raw results → Result
       ├─ Formatted results → Result
       ├─ Query type (SELECT/ASK/etc)
       └─ Error (if any)
    ↓
[ResultsManager]
    ├─ Create entry structure
    ├─ Update with each stage
    ├─ Add statistics
    └─ Save to JSON
    ↓
result_YYYYMMDD_HHMMSS.json
    ├─ metadata (question, timestamp)
    ├─ pipeline (all stage results)
    ├─ prompts (all LLM prompts)
    └─ statistics (stages_completed, errors)
    ↓
[Results Available]
    ├─ Direct file access (JSON)
    ├─ Python API (results_viewer)
    ├─ CSV export (analysis)
    └─ GUI display (future)
```

## Result Components by Stage

### Stage 1: Class Extraction
```
Input: Question + Full Schema
    ↓
LLM Decision: Which classes are relevant?
    ↓
Output:
  ├─ extracted_classes: [list of class names]
  ├─ config: { include_examples: bool }
  ├─ schema_with_examples: full schema used
  ├─ schema_without_examples: reference schema
  └─ prompts: list of prompts sent to LLM
```

### Stage 2: Property Extraction
```
Input: Question + Relevant Classes + Schema
    ↓
LLM Decision: Which properties are needed?
    ↓
Output:
  ├─ property_selection: [{class, properties}, ...]
  ├─ total_properties: count
  ├─ config: { include_examples: bool }
  ├─ schema_with_examples: full schema used
  ├─ schema_without_examples: reference schema
  └─ prompts: list of prompts sent to LLM
```

### Stage 3: Missing ID Extraction
```
Input: Question + Selected Properties
    ↓
LLM Decision: What entity names need lookup?
    ↓
Generate Query → Execute → Collect IRIs
    ↓
Output:
  ├─ missing_id_query: SPARQL query generated
  ├─ resolved_entities: { "EntityName": "IRI", ... }
  ├─ resolved_count: number of entities found
  ├─ config: { enabled: bool, max_iris: int }
  ├─ schema_passed_to_llm: schema used
  └─ prompts: prompt sent to LLM
```

### Stage 4: Query Generation
```
Input: Extracted Classes + Properties + Resolved Entities
    ↓
LLM Decision: How to query for the answer?
    ↓
Output:
  ├─ generated_query: SPARQL query (SELECT/ASK/CONSTRUCT/DESCRIBE)
  ├─ config: { include_examples: bool }
  ├─ schema_with_examples: full schema used
  ├─ schema_without_examples: reference schema
  └─ prompts: prompt sent to LLM
```

### Stage 5: Query Execution
```
Input: Generated SPARQL Query
    ↓
Execute on SPARQL Endpoint → Get Results
    ↓
Output:
  ├─ executed_query: exact query sent to endpoint
  ├─ query_type: SELECT | ASK | CONSTRUCT | DESCRIBE
  ├─ raw_results: JSON from endpoint
  ├─ formatted_results: human-readable format
  ├─ result_count: number of results
  └─ execution_error: error message (if any)
```

## Result File Example Structure

```
result_20260223_153045.json
│
├─ metadata
│  ├─ timestamp: "2026-02-23T15:30:45.123456"
│  └─ question: "Who is our Sensor expert?"
│
├─ pipeline
│  ├─ class_extraction
│  │  ├─ config: { include_examples: true }
│  │  ├─ extracted_classes: ["prod_vocab:Employee", "prod_vocab:ProductCategory"]
│  │  ├─ class_count: 2
│  │  ├─ schema_with_examples: "Prefixes: ...", "Class Name: ..."
│  │  └─ schema_without_examples: "Prefixes: ...", "Class Name: ..."
│  │
│  ├─ property_extraction
│  │  ├─ config: { include_examples: true }
│  │  ├─ property_selection: [{ class, properties }, ...]
│  │  ├─ total_properties: 3
│  │  ├─ schema_with_examples: "..."
│  │  └─ schema_without_examples: "..."
│  │
│  ├─ missing_id_extraction
│  │  ├─ config: { enabled: true, max_iris: 5 }
│  │  ├─ missing_id_query: "PREFIX ... SELECT ..."
│  │  ├─ resolved_entities: { "Sensor": "http://..." }
│  │  ├─ resolved_count: 1
│  │  └─ schema_passed_to_llm: "..."
│  │
│  ├─ query_generation
│  │  ├─ config: { include_examples: true }
│  │  ├─ generated_query: "PREFIX ... SELECT ..."
│  │  ├─ schema_with_examples: "..."
│  │  └─ schema_without_examples: "..."
│  │
│  └─ query_execution
│     ├─ config: {}
│     ├─ executed_query: "PREFIX ... SELECT ..."
│     ├─ query_type: "SELECT"
│     ├─ raw_results: { results: { bindings: [...] } }
│     ├─ formatted_results: "..."
│     ├─ result_count: 1
│     └─ execution_error: null
│
├─ prompts
│  ├─ class_extraction_prompts: ["You are an expert...", ...]
│  ├─ property_extraction_prompts: ["You are an expert...", ...]
│  ├─ missing_id_query_prompt: "You are an expert..."
│  └─ final_query_generation_prompt: "You are an expert..."
│
└─ statistics
   ├─ stages_completed: [
   │    "class_extraction",
   │    "property_extraction",
   │    "missing_id_extraction",
   │    "query_generation",
   │    "query_execution"
   │  ]
   ├─ total_time_ms: 5420
   └─ errors: []
```

## Access Patterns

### Access 1: Direct File Reading
```
results/result_20260223_153045.json
├─ Load JSON
├─ Parse structure
└─ Extract needed fields
```

### Access 2: Python API
```
from nl2sparql.results_viewer import get_latest_result
result = get_latest_result()
classes = result['pipeline']['class_extraction']['extracted_classes']
```

### Access 3: Formatted Display
```
from nl2sparql.results_viewer import format_result_for_display
print(format_result_for_display(result))
```

### Access 4: Batch Analysis
```
from nl2sparql.results_viewer import list_all_results
results = list_all_results(limit=100)
for r in results:
    # Analyze each result
```

### Access 5: CSV Export
```
from nl2sparql.results_manager import ResultsManager
rm = ResultsManager()
rm.export_to_csv("analysis.csv")
```

## Key Differences: With Examples vs Without Examples

The results show schema used at each stage in two versions:

### With Examples (what LLM saw)
```
Class Name: prod_vocab:Employee
Class Examples:
  - Product 1
  - Product 2
Properties:
  - Property 1 | Examples: Value1, Value2
  - Property 2 | Examples: Value3, Value4
```

### Without Examples (reference)
```
Class Name: prod_vocab:Employee
Class Examples:
  (No examples available)
Properties:
  - Property 1 | Label: Property Label
  - Property 2 | Label: Property Label
```

**Use Case**: Debug by comparing - did examples help or hurt the LLM's decisions?

## Storage Considerations

### Typical Sizes
- Minimal result: 200 KB (no examples, few classes)
- Standard result: 500 KB - 1 MB (typical queries)
- Large result: 1-2 MB (many classes/properties, long schemas)

### What Takes Space
- Schemas (50-200 KB each × 8 = 400-1600 KB)
- Prompts (5-20 KB each × 4 = 20-80 KB)
- Results (varies: 1-100 KB)

### Optimization Tips
- Use `include_examples: false` in config to reduce size
- Archive old results periodically
- Consider compression for long-term storage
- Export to CSV for historical analysis

## Future Extensions

```
Current: Single Query Result
    ↓
Advanced: Batch Processing
    ├─ Process multiple questions
    ├─ Compare results side-by-side
    └─ Aggregate statistics
    ↓
Analysis: Pattern Detection
    ├─ How often entities needed resolution?
    ├─ Which properties always selected?
    ├─ Schema quality metrics
    └─ Performance trends
    ↓
UI: Results Dashboard
    ├─ Browse all results
    ├─ Compare runs
    ├─ View prompts
    └─ Download/export
```

---

**Current Status**: ✅ **Core Implementation Complete**  
**Testing**: ✅ **All Tests Passing**  
**Documentation**: ✅ **Complete**  
**Ready for Production**: ✅ **Yes**
