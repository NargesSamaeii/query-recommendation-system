# Complete Setup and Usage Guide

## 📋 Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Basic Usage](#basic-usage)
4. [Advanced Usage](#advanced-usage)
5. [Troubleshooting](#troubleshooting)
6. [GitHub Upload](#github-upload)

---

## Installation

### Step 1: Navigate to Project Directory

```powershell
cd C:\Users\dhami\nl2sparql
```

### Step 2: Create Virtual Environment (Recommended)

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### Step 3: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 4: Install Package

```powershell
pip install -e .
```

### Step 5: Verify Installation

```powershell
nl2sparql --help
```

---

## Configuration

### 1. Setup Environment Variables

```powershell
# Copy example file
copy .env.example .env

# Edit .env and add your Gemini API key
notepad .env
```

In `.env`, replace:
```
GEMINI_API_KEY=your_api_key_here
```

With your actual API key from: https://makersuite.google.com/app/apikey

### 2. Review config.yaml (Optional)

```powershell
notepad config.yaml
```

Default settings are usually fine, but you can customize:
- LLM provider and model
- SPARQL endpoint
- Output formats
- Pipeline stages

---

## Basic Usage

### Workflow Overview

```
1. Place SHACL file → 2. Extract Schema → 3. Ask Questions
```

### 1. Extract Schema from Your Notebook's SHACL File

First, copy your SHACL file to the input directory:

```powershell
# Example: Copy your European Union schema
copy "C:\Users\dhami\Downloads\european_union_QSE_FULL_SHACL_.ttl" data\input\
```

Then extract:

```powershell
nl2sparql extract data\input\european_union_QSE_FULL_SHACL_.ttl
```

This creates: `data\output\european_union_QSE_FULL_SHACL__mschema.json`

### 2. Ask Questions

```powershell
nl2sparql query "Find country types whose motto contains the word Earth" --schema data\output\european_union_QSE_FULL_SHACL__mschema.json --show-query
```

### 3. Interactive Mode

```powershell
nl2sparql interactive --schema data\output\european_union_QSE_FULL_SHACL__mschema.json
```

Then type questions:
```
Question: Who are the actors born in Rome?
Question: What is the population of France?
Question: exit
```

---

## Advanced Usage

### Using Python API

Create a script `my_queries.py`:

```python
from nl2sparql import NL2SPARQLPipeline

# Initialize
pipeline = NL2SPARQLPipeline()

# Your question
question = "Find country types whose motto contains the word 'Earth'"
schema_path = "data/output/european_union_QSE_FULL_SHACL__mschema.json"

# Get answer
results = pipeline.answer_question(question, schema_path)

# Print results
print("SPARQL Query:")
print(results.get("sparql_query", ""))

print("\nResults:")
print(results.get("formatted_results", ""))

# Access intermediate steps
print("\nRelevant Classes:")
print(results["intermediate"].get("relevant_classes", []))

print("\nProperty Selection:")
print(results["intermediate"].get("property_selection", []))
```

Run it:
```powershell
python my_queries.py
```

### Batch Processing Multiple Questions

Create `batch_questions.py`:

```python
from nl2sparql import NL2SPARQLPipeline
import json

pipeline = NL2SPARQLPipeline()

questions = [
    "Find countries whose motto contains 'Earth'",
    "Who are the actors born in Rome?",
    "What universities are in California?"
]

schema_path = "data/output/your_schema_mschema.json"

results_list = []
for q in questions:
    print(f"\nProcessing: {q}")
    result = pipeline.answer_question(q, schema_path)
    results_list.append({
        "question": q,
        "sparql": result.get("sparql_query"),
        "answer": result.get("formatted_results")
    })

# Save all results
with open("batch_results.json", "w") as f:
    json.dump(results_list, f, indent=2)

print("\n✓ Results saved to batch_results.json")
```

### Using Different LLM Providers

#### OpenAI (GPT-4)

1. Edit `config.yaml`:
```yaml
llm:
  provider: "openai"
  model_name: "gpt-4"
```

2. Add OpenAI key to `.env`:
```
OPENAI_API_KEY=your_openai_key
```

#### Mistral (Local Model)

1. Download model:
```powershell
pip install huggingface-hub
huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF mistral-7b-instruct-v0.2.Q2_K.gguf --local-dir .
```

2. Edit `config.yaml`:
```yaml
llm:
  provider: "mistral"
  mistral:
    model_path: "mistral-7b-instruct-v0.2.Q2_K.gguf"
    n_ctx: 2048
```

---

## Troubleshooting

### Common Issues

#### 1. "GEMINI_API_KEY not found"

**Solution:**
```powershell
# Check .env file exists
dir .env

# If not, create it
copy .env.example .env

# Edit and add your API key
notepad .env
```

#### 2. "Module 'nl2sparql' not found"

**Solution:**
```powershell
# Make sure you're in the project directory
cd C:\Users\dhami\nl2sparql

# Reinstall package
pip install -e .
```

#### 3. Schema Extraction Fails

**Solution:**
```powershell
# Try with verbose mode
nl2sparql extract your_file.ttl --verbose

# Check if file exists
dir data\input\your_file.ttl

# Verify TTL syntax is valid
```

#### 4. No Results Returned

**Possible causes:**
- SPARQL endpoint not accessible
- Schema doesn't contain relevant classes
- Question not matching schema vocabulary

**Solution:**
```powershell
# Check endpoint in config.yaml
nl2sparql config --key sparql.endpoint_url

# Show intermediate results
nl2sparql query "Your question?" --schema schema.json --show-query
```

#### 5. Query Execution Timeout

**Solution:**
Edit `config.yaml`:
```yaml
sparql:
  timeout: 60  # Increase from 30 to 60 seconds
```

---

## GitHub Upload

### Step 1: Initialize Git

```powershell
cd C:\Users\dhami\nl2sparql
git init
git add .
git commit -m "Initial commit: NL2SPARQL framework"
```

### Step 2: Create GitHub Repository

1. Go to https://github.com/new
2. Name: `nl2sparql`
3. Description: "Natural Language to SPARQL Query Translation Framework"
4. Public or Private
5. **Don't** initialize with README
6. Click "Create repository"

### Step 3: Push to GitHub

```powershell
git remote add origin https://github.com/YOUR_USERNAME/nl2sparql.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

### Step 4: Verify

Visit: `https://github.com/YOUR_USERNAME/nl2sparql`

**For detailed instructions, see [GITHUB_SETUP.md](GITHUB_SETUP.md)**

---

## Testing Your Setup

### Quick Test Script

Create `test_setup.py`:

```python
"""Quick test to verify installation."""

print("Testing NL2SPARQL installation...")

# Test 1: Import package
try:
    import nl2sparql
    print("✓ Package imported successfully")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    exit(1)

# Test 2: Check config
try:
    from nl2sparql import Config
    config = Config()
    print("✓ Configuration loaded")
except Exception as e:
    print(f"✗ Config failed: {e}")

# Test 3: Check LLM
try:
    from nl2sparql import create_llm
    llm = create_llm("gemini")
    print("✓ LLM initialized")
except Exception as e:
    print(f"✗ LLM initialization failed: {e}")
    print("  Make sure GEMINI_API_KEY is set in .env file")

# Test 4: Check CLI
import subprocess
result = subprocess.run(["nl2sparql", "--help"], capture_output=True)
if result.returncode == 0:
    print("✓ CLI command working")
else:
    print("✗ CLI command failed")

print("\n✅ Setup complete! You're ready to use NL2SPARQL.")
```

Run it:
```powershell
python test_setup.py
```

---

## Next Steps

1. **Extract your first schema**: 
   ```powershell
   nl2sparql extract data\input\your_schema.ttl
   ```

2. **Ask your first question**:
   ```powershell
   nl2sparql query "Your question?" --schema data\output\your_schema_mschema.json
   ```

3. **Read more examples**: See [EXAMPLES.md](EXAMPLES.md)

4. **Upload to GitHub**: Follow [GITHUB_SETUP.md](GITHUB_SETUP.md)

---

## Resources

- **Main Documentation**: [README.md](README.md)
- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **Examples**: [EXAMPLES.md](EXAMPLES.md)
- **GitHub Setup**: [GITHUB_SETUP.md](GITHUB_SETUP.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Support

- **Issues**: Open an issue on GitHub
- **Questions**: Create a discussion on GitHub
- **Email**: [Your email if you want to provide it]

---

**🎉 Congratulations! Your NL2SPARQL framework is ready to use!**
