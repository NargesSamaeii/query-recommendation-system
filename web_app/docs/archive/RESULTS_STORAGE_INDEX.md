# Results Storage Documentation Index

## Quick Links

- **[RESULTS_QUICK_START.md](RESULTS_QUICK_START.md)** ⭐ START HERE
  - Quick reference guide
  - Basic usage examples
  - Common patterns

- **[RESULTS_FORMAT_DOCUMENTATION.md](RESULTS_FORMAT_DOCUMENTATION.md)**
  - Complete format specification
  - Field-by-field explanation
  - Integration examples

- **[RESULTS_ARCHITECTURE.md](RESULTS_ARCHITECTURE.md)**
  - Data flow diagrams
  - Stage-by-stage breakdown
  - Storage considerations

- **[RESULT_FORMAT_EXAMPLE.json](RESULT_FORMAT_EXAMPLE.json)**
  - Real example result file
  - Shows all fields populated
  - Reference for structure

## Files Added

### Core Implementation
- `nl2sparql/results_manager.py` - Core results management class
- `nl2sparql/results_viewer.py` - Results viewing & analysis utilities

### Pipeline Integration
- Modified `nl2sparql/pipeline.py` - Integrated ResultsManager

### Testing
- `test_results_storage.py` - Comprehensive test suite (all 5 tests passing ✓)

### Documentation
- `RESULTS_QUICK_START.md` - Quick reference guide
- `RESULTS_FORMAT_DOCUMENTATION.md` - Detailed format spec
- `RESULTS_ARCHITECTURE.md` - Architecture and data flow
- `RESULT_FORMAT_EXAMPLE.json` - Example result file
- `RESULTS_STORAGE_SUMMARY.md` - Implementation summary
- This index file

## What Gets Stored

When you process a question through NL2SPARQL, the result file includes:

```
✓ Question & Timestamp
✓ Extracted Classes (with count)
✓ Selected Properties (with count)
✓ Resolved Entity IRIs
✓ Generated SPARQL Query
✓ Query Results (raw and formatted)
✓ All LLM Prompts (for transparency)
✓ Schemas at Each Stage (with & without examples)
✓ Pipeline Statistics (stages completed, errors)
```

## Usage Quick Start

### View Latest Result
```python
from nl2sparql.results_viewer import get_latest_result, format_result_for_display
result = get_latest_result()
print(format_result_for_display(result))
```

### List All Results
```python
from nl2sparql.results_viewer import list_all_results
results = list_all_results(limit=10)
```

### Analyze Specific Fields
```python
question = result['metadata']['question']
classes = result['pipeline']['class_extraction']['extracted_classes']
query = result['pipeline']['query_generation']['generated_query']
results = result['pipeline']['query_execution']['formatted_results']
```

### Export for Analysis
```python
from nl2sparql.results_manager import ResultsManager
rm = ResultsManager()
rm.export_to_csv("analysis.csv")
```

## Result File Location

Results are saved to: `results/result_YYYYMMDD_HHMMSS.json`

Example:
- `results/result_20260223_150000.json`
- `results/result_20260223_151030.json`
- `results/result_20260223_152045.json`

## Key Features

### 1. Complete Transparency
- Every prompt sent to LLM is stored
- Understand exactly why decisions were made
- Share for collaboration/audit

### 2. Schema Comparison
- Both `with_examples` and `without_examples` versions
- Debug LLM influence
- Analyze schema effectiveness

### 3. Full Traceability
- Track question → classes → properties → query → results
- See resolved entities
- Review each stage

### 4. Error Tracking
- Errors captured with timestamp
- Know which stage failed
- Understand failure context

### 5. Easy Analysis
- Export to CSV
- Compare multiple results
- Generate statistics

## Testing

All components tested and verified:
```
✓ Module Imports
✓ Result Creation
✓ Result Structure
✓ Results Viewer
✓ JSON Validation

5/5 tests passing
```

Run tests: `python test_results_storage.py`

## Integration Points

### Automatic
- Results saved automatically during pipeline execution
- No special configuration needed
- No code changes required

### Access Points
- Python API: `nl2sparql.results_viewer`
- Direct file access: `results/` directory
- CSV export: Use `ResultsManager.export_to_csv()`
- GUI (future): Browse results in Streamlit

## Common Tasks

### Find Latest Result
```python
from nl2sparql.results_viewer import get_latest_result
result = get_latest_result()
```

### Compare Two Runs
```python
from nl2sparql.results_viewer import compare_results
comp = compare_results("result1.json", "result2.json")
```

### See What Prompts Were Used
```python
prompts = result['prompts']
for name, prompt_list in prompts.items():
    print(f"{name}: {len(prompt_list)} prompt(s)")
```

### Understand LLM Decisions
```python
schema_with = result['pipeline']['class_extraction']['schema_with_examples']
schema_without = result['pipeline']['class_extraction']['schema_without_examples']
# Compare to see how examples influenced decisions
```

### Trace Query Generation
```python
q = result['metadata']['question']
classes = result['pipeline']['class_extraction']['extracted_classes']
props = result['pipeline']['property_extraction']['property_selection']
entities = result['pipeline']['missing_id_extraction']['resolved_entities']
query = result['pipeline']['query_generation']['generated_query']
results = result['pipeline']['query_execution']['formatted_results']
```

## Statistics Available

```python
stats = result['statistics']
print(f"Stages completed: {stats['stages_completed']}")
print(f"Total time (ms): {stats['total_time_ms']}")
print(f"Errors: {len(stats['errors'])}")

pipeline = result['pipeline']
print(f"Classes: {pipeline['class_extraction']['class_count']}")
print(f"Properties: {pipeline['property_extraction']['total_properties']}")
print(f"Entities resolved: {pipeline['missing_id_extraction']['resolved_count']}")
print(f"Result count: {pipeline['query_execution']['result_count']}")
```

## Typical File Sizes

- **Small result**: 200-500 KB
- **Medium result**: 500 KB - 1 MB
- **Large result**: 1-2 MB

Includes:
- Full schemas (multiple versions)
- All prompts (100-500 lines each)
- Query results
- Metadata and statistics

## Next Steps

1. **Review** the result file structure in [RESULT_FORMAT_EXAMPLE.json](RESULT_FORMAT_EXAMPLE.json)
2. **Read** the quick start guide in [RESULTS_QUICK_START.md](RESULTS_QUICK_START.md)
3. **Explore** detailed format in [RESULTS_FORMAT_DOCUMENTATION.md](RESULTS_FORMAT_DOCUMENTATION.md)
4. **Understand** the architecture in [RESULTS_ARCHITECTURE.md](RESULTS_ARCHITECTURE.md)
5. **Use** the Result Viewer API to access results

## Support

### For Questions
- Check [RESULTS_QUICK_START.md](RESULTS_QUICK_START.md) first
- Read [RESULTS_FORMAT_DOCUMENTATION.md](RESULTS_FORMAT_DOCUMENTATION.md) for details
- Review [RESULT_FORMAT_EXAMPLE.json](RESULT_FORMAT_EXAMPLE.json) for structure
- See [RESULTS_ARCHITECTURE.md](RESULTS_ARCHITECTURE.md) for data flow

### For Issues
- Check test suite: `python test_results_storage.py`
- Review result file directly: `results/` directory
- Check pipeline logs for errors

### For Extensions
- Use `ResultsManager` class for custom storage
- Use `results_viewer` functions for analysis
- Build analysis tools on top of JSON structure

---

**Status**: ✅ Complete and Production-Ready

**Last Updated**: 2026-02-23

**Version**: 1.0
