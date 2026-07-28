# Ground Truth Folder Structure for NL2SPARQL Evaluation

## How to Organize Ground Truth Files

- For each knowledge graph (KG), create a subfolder inside `tests/ground_truth` named after the KG (should match the mschema name used in the GUI).
- Place your ground-truth files (JSON format) for that KG inside its subfolder.
- Example folder structure:

```
tests/ground_truth/
    corporate/
        gt_corporate.json
    wikidata/
        gt_wikidata.json
```

## Ground Truth JSON Example

Each ground-truth file should be a JSON array of QA pairs, e.g.:

```
[
  {
    "id": 1,
    "question": "How many employees does Company X have?",
    "answers": ["1000"]
  },
  {
    "id": 2,
    "question": "Who is the CEO of Company Y?",
    "answers": ["Alice Smith"]
  }
]
```

- `id`: Unique identifier for the question.
- `question`: The natural language question.
- `answers`: List of correct answers (strings).

## Notes
- The subfolder name must match the KG/mschema name used in the GUI for correct evaluation alignment.
- You can have multiple ground-truth files per KG if needed.
- Only JSON files are supported.

## See Also
- The GUI will automatically detect and use these files for evaluation.
- For more details, see the main project documentation.
