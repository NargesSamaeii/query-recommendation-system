# Example Ground Truth Files

This directory contains ground truth data for evaluating the NL2SPARQL pipeline. Ground truth files define what the correct answer should be, allowing the system to measure precision, recall, and F1-score.

## File Format

Each ground truth file is a JSON file named `gt_<hash>.json` where `<hash>` is derived from the question text.

### Ground Truth Structure

```json
{
  "question": "The original natural language question",
  "expected_classes": [
    "Class or Type 1",
    "Class or Type 2"
  ],
  "expected_properties": [
    {
      "class_name": "Class or Type 1",
      "relevant_properties": [
        "property1",
        "property2"
      ]
    }
  ],
  "expected_entities": {
    "entity_name": "full_iri_or_label",
    "another_entity": "another_iri"
  },
  "expected_results": [
    {
      "result_field_1": "expected_value_1",
      "result_field_2": "expected_value_2"
    }
  ],
  "key_field": "result_field_1"
}
```

### Field Definitions

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `question` | string | Original question (informational) | "Who manages the Sensor category?" |
| `expected_classes` | array of strings | Classes/types the system should extract | `["prod_vocab:Employee", "prod_vocab:Manager"]` |
| `expected_properties` | array of objects | Properties relevant to each class | `[{"class_name": "prod_vocab:Employee", "relevant_properties": ["name", "email"]}]` |
| `expected_entities` | object | Named entities and their IRIs/labels | `{"Sensor": "http://ld.company.org/prod-cat-Sensor"}` |
| `expected_results` | array of objects | Rows expected from query execution | `[{"name": "John", "role": "Manager"}]` |
| `key_field` | string | Field to use for result comparison | `"name"` |

## Example 1: Employee Query

**Question**: "Who is our Sensor expert?"

**Ground Truth**:
```json
{
  "question": "Who is our Sensor expert?",
  "expected_classes": [
    "prod_vocab:Employee",
    "prod_vocab:ProductCategory"
  ],
  "expected_properties": [
    {
      "class_name": "prod_vocab:Employee",
      "relevant_properties": [
        "ns_0_1:name",
        "prod_vocab:areaOfExpertise",
        "prod_vocab:employeeID"
      ]
    },
    {
      "class_name": "prod_vocab:ProductCategory",
      "relevant_properties": [
        "rdfs:label",
        "rdf:type"
      ]
    }
  ],
  "expected_entities": {
    "Sensor": "http://ld.company.org/prod-instances/prod-cat-Sensor"
  },
  "expected_results": [
    {
      "employeeName": "John Smith",
      "expertise": "Sensor Technology"
    },
    {
      "employeeName": "Jane Doe",
      "expertise": "Sensor Design"
    }
  ],
  "key_field": "employeeName"
}
```

**Rationale**:
- The system should find that employees and product categories are relevant
- For employees, name and expertise are critical properties
- For product categories, label and type are relevant
- The entity "Sensor" should be resolved to its IRI
- Should return employee names and their expertise areas

## Example 2: Product Query

**Question**: "What are the dimensions of all lightweight products?"

**Ground Truth**:
```json
{
  "question": "What are the dimensions of all lightweight products?",
  "expected_classes": [
    "prod_vocab:Product",
    "prod_vocab:Specification"
  ],
  "expected_properties": [
    {
      "class_name": "prod_vocab:Product",
      "relevant_properties": [
        "prod_vocab:weight",
        "prod_vocab:name",
        "prod_vocab:hasSpecification"
      ]
    },
    {
      "class_name": "prod_vocab:Specification",
      "relevant_properties": [
        "prod_vocab:width",
        "prod_vocab:height",
        "prod_vocab:depth"
      ]
    }
  ],
  "expected_entities": {
    "lightweight": "http://ld.company.org/concepts/Weight/Lightweight"
  },
  "expected_results": [
    {
      "productName": "Widget A",
      "weight": 2.5,
      "width": 10,
      "height": 5,
      "depth": 8
    },
    {
      "productName": "Widget B",
      "weight": 1.8,
      "width": 12,
      "height": 6,
      "depth": 7
    }
  ],
  "key_field": "productName"
}
```

**Rationale**:
- Product and Specification classes capture dimension information
- Weight and dimension properties are relevant
- "lightweight" is an entity constraint (may or may not have direct IRI)
- Results should include product name and all three dimensions

## Example 3: Relationship Query

**Question**: "Which managers oversee product development teams?"

**Ground Truth**:
```json
{
  "question": "Which managers oversee product development teams?",
  "expected_classes": [
    "prod_vocab:Manager",
    "prod_vocab:Team",
    "prod_vocab:Department"
  ],
  "expected_properties": [
    {
      "class_name": "prod_vocab:Manager",
      "relevant_properties": [
        "ns_0_1:name",
        "prod_vocab:manages"
      ]
    },
    {
      "class_name": "prod_vocab:Team",
      "relevant_properties": [
        "prod_vocab:teamName",
        "prod_vocab:focus"
      ]
    },
    {
      "class_name": "prod_vocab:Department",
      "relevant_properties": [
        "prod_vocab:departmentName"
      ]
    }
  ],
  "expected_entities": {
    "product development": "http://ld.company.org/concepts/TeamFocus/ProductDevelopment"
  },
  "expected_results": [
    {
      "managerName": "Alice Johnson",
      "teamName": "Development Team 1"
    },
    {
      "managerName": "Bob Smith",
      "teamName": "Development Team 2"
    }
  ],
  "key_field": "managerName"
}
```

## How to Create Your Own Ground Truth

### Step 1: Identify Relevant Classes

Run your question through the system and note which classes were extracted:

```python
from nl2sparql.pipeline import NL2SPARQLPipeline
pipeline = NL2SPARQLPipeline()
result = pipeline.answer_question("Your question?", "schema.json")
print(result["stages"]["class_extraction"]["extracted"])
```

### Step 2: Identify Relevant Properties

For each class, which properties are actually relevant?

```python
print(result["stages"]["property_extraction"]["extracted_properties"])
```

### Step 3: Check Named Entities

What entities were resolved?

```python
print(result["stages"]["missing_id_extraction"]["resolved_entities"])
```

### Step 4: Verify Result Format

What fields does the actual query return?

```python
actual_results = result["stages"]["query_execution"]["results"]
print(actual_results)
```

### Step 5: Create Ground Truth

```python
from nl2sparql.ground_truth_manager import GroundTruthManager

gt_manager = GroundTruthManager()

ground_truth = {
    "question": "Your question?",
    "expected_classes": [
        "verified_class_1",
        "verified_class_2"
    ],
    "expected_properties": [
        {
            "class_name": "verified_class_1",
            "relevant_properties": [
                "property_a",
                "property_b"
            ]
        }
    ],
    "expected_entities": {
        "entity_name": "http://actual_iri"
    },
    "expected_results": actual_results,  # Use actual results or modify as needed
    "key_field": "main_field"
}

gt_manager.save_ground_truth("Your question?", ground_truth)
```

## Best Practices

1. **Be Precise**: Ground truth should reflect what you actually want, not what the current system does
2. **Include All Variants**: If multiple answers are correct, include them all
3. **Use Full IRIs**: Always use complete IRIs, not shortened formats
4. **Test incrementally**: Start with one ground truth, evaluate, then add more
5. **Keep Properties Minimal**: Only include properties actually needed to answer the question
6. **Document Edge Cases**: If a question is ambiguous, note it in the expected results

## Testing Your Ground Truth

```python
from nl2sparql.evaluator import PipelineEvaluator
from nl2sparql.ground_truth_manager import GroundTruthManager
from nl2sparql.results_viewer import get_latest_result

# Load your ground truth
gt_manager = GroundTruthManager()
ground_truth = gt_manager.load_ground_truth_by_question("Your question?")

# Get latest result
result = get_latest_result()

# Evaluate
evaluator = PipelineEvaluator()
evaluation = evaluator.evaluate_full_pipeline(result, ground_truth)

# Check metrics
print(f"Class F1: {evaluation['stages']['class_extraction']['f1']}")
print(f"Property F1: {evaluation['stages']['property_extraction']['macro_average']['f1']}")
print(f"Overall F1: {evaluation['overall']['average_f1']}")
```

---

**Version**: 1.0
**Created**: 2025-02-23
