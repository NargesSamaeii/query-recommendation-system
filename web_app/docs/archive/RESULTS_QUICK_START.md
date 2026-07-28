# NL2SPARQL Results Storage - Quick Reference

## What's New?

**Comprehensive JSON results storage** that captures every step of the NL2SPARQL pipeline in a clean, organized format.

## How It Works

When you run a question through NL2SPARQL, a complete result file is automatically saved to:
```
results/result_YYYYMMDD_HHMMSS.json
```

## What Gets Saved?

### ✓ Question & Metadata
- Original question
- Processing timestamp

### ✓ All Pipeline Stages
- **Class Extraction**: Which classes were relevant
- **Property Extraction**: Which properties were selected
- **Missing ID Extraction**: Entity IRIs that were resolved
- **Query Generation**: The SPARQL query that was generated
- **Query Execution**: Results from the SPARQL endpoint

### ✓ Schema at Each Stage
- **WITH Examples**: Full schema including class examples (shown to LLM)
- **WITHOUT Examples**: Schema without examples (for reference)
- Useful for debugging and comparing LLM behavior

### ✓ All LLM Prompts
- Every prompt sent to the LLM
- Exactly as the LLM received it
- Great for understanding and debugging decisions

### ✓ Statistics
- Stages completed
- Errors encountered
- Processing time

## Usage Examples

### View Latest Results
```python
from nl2sparql.results_viewer import get_latest_result, format_result_for_display

result = get_latest_result()
print(format_result_for_display(result))
```

### List All Results
```python
from nl2sparql.results_viewer import list_all_results

results = list_all_results(limit=10)  # Get 10 most recent
for r in results:
    print(f"{r['timestamp']} - {r['question'][:50]}... ({r['result_count']} results)")
```

### Access Specific Fields
```python
# Question
question = result['metadata']['question']

# Classes found
classes = result['pipeline']['class_extraction']['extracted_classes']

# Properties selected
properties = result['pipeline']['property_extraction']['property_selection']

# Resolved entities
entities = result['pipeline']['missing_id_extraction']['resolved_entities']

# Final SPARQL query
query = result['pipeline']['query_generation']['generated_query']

# Query results
results = result['pipeline']['query_execution']['formatted_results']

# Prompts used
class_prompt = result['prompts']['class_extraction_prompts'][0]
```

### Compare Results
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

## Result File Example

See `RESULT_FORMAT_EXAMPLE.json` for a complete example with all fields.

## File Structure

```
results/
├── result_20260223_150000.json  ← JSON file with complete result
├── result_20260223_151000.json
├── result_20260223_152000.json
└── ...
```

Each result file contains:
- `metadata`: Question and timestamp
- `pipeline`: Results from each stage with schemas
- `prompts`: All LLM prompts used
- `statistics`: Stages completed, errors, etc.

## Key Features

### 1. Schema Comparison
Compare `schema_with_examples` vs `schema_without_examples` to see how examples influenced decisions.

### 2. Transparency
Every prompt that goes to the LLM is saved, so you can see exactly why certain decisions were made.

### 3. Reproducibility
Have all the information needed to recreate any result:
- The question
- The schemas used at each stage
- The prompts sent to LLM
- The generated queries

### 4. Debugging
If something went wrong:
- Check which stage failed
- Review the prompts and schemas at that stage
- See any error messages captured

### 5. Analysis
Run multiple questions and compare:
- How many entities needed resolution?
- How many properties were selected?
- What query types were generated?
- How many results were returned?

## Typical Result File Size

- Small results: 200-500 KB
- Medium results: 500 KB - 1 MB
- Large results: 1-2 MB

Results include full schema copies (2 versions × 4-5 stages) and all prompts.

## Integration

Results are automatically saved during normal pipeline execution. No special configuration needed!

Access them anytime via:
1. Python: `results_viewer` module
2. Direct: Browse `results/` directory
3. GUI: Results section (when integrated)

## What to Do With Results

### For Debugging
- Check which stage has the issue
- Review the prompts and schemas
- Look at the exact query generated
- Check for errors in statistics

### For Analysis
- Compare multiple runs
- Understand LLM behavior patterns
- See how schema changes affect results
- Track performance over time

### For Documentation
- Show exact prompts used for reproducibility
- Document schema evolution
- Create audit trails
- Share results for review

### For Learning
- Understand how NL2SPARQL works internally
- See what schemas the LLM receives
- Learn how questions map to SPARQL queries
- Experiment with different configurations

## Tips

1. **Name your questions clearly**
   - "Who is our Sensor expert?" is clear
   - "What?" is not helpful when reviewing results

2. **Check statistics after each run**
   - See which stages succeeded
   - Spot patterns in errors
   - Track improvements

3. **Use schema comparison**
   - Debug by comparing with_examples vs without_examples
   - See how examples influence class/property selection

4. **Review prompts**
   - Understand LLM's reasoning
   - Optimize prompts if needed
   - Share for collaboration

5. **Archive important results**
   - Save historical results separately
   - Compare workflows over time
   - Document schema versions

---

**For complete documentation**, see `RESULTS_FORMAT_DOCUMENTATION.md`
