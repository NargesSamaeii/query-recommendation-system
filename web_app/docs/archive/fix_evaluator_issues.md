# Evaluator Issues to Fix

## Issue 1: Remove `accuracy` from class and property extraction
- **Current**: Both return `accuracy: 0.0`
- **Fix**: Remove accuracy field (only keep precision, recall, F1)

## Issue 2: Property extraction evaluates wrong classes
**Current Problem**:
- Evaluates ALL extracted classes (including false positives like Service, Agent, etc.)
- Ground truth only has Employee and Department
- But evaluation includes Service, Agent, BomPart, etc. with all their properties

**Example**:
```
Service: tp=0, fp=4, fn=0  ← Should NOT be evaluated at all!
Agent: tp=0, fp=1, fn=0    ← Should NOT be evaluated at all!
```

**Root Cause**: Line 161 in evaluator.py
```python
all_classes = set(extracted_dict.keys()) | set(correct_dict.keys())
```

**Fix**: Only evaluate classes in ground truth
```python
all_classes = set(correct_dict.keys())  # Only ground truth classes
```

## Issue 3: Property name normalization
**Current**:
- Ground truth has: `"memberOf"`
- Extracted has: `"prod_vocab:memberOf"`  
- They don't match → tp=0

**Fix**: Normalize by extracting local name (after `:`)

## Issue 4: Query result format mismatch
**Current**:
- Actual result: `{"departmentName": "Engineering"}`
- Expected result: `{"result": "http://ld.company.org/prod-instances/dept-73191"}`
- Different field names and value types (name vs IRI)

**This is a ground truth format issue** - not evaluator bug
