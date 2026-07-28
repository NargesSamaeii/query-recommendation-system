# NL2SPARQL

**Natural Language to SPARQL Query Translation Framework**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

NL2SPARQL is a comprehensive framework that enables natural-language question answering over knowledge graphs by translating user questions into executable SPARQL queries through a multi-stage AI-powered pipeline.

## 🌟 Features

- **Schema Extraction**: Automatically parses SHACL (Shapes Constraint Language) files and generates machine-readable schemas
- **Intelligent Class Detection**: Uses LLMs to identify relevant RDF classes for a given question
- **Property Selection**: Automatically determines which properties are needed to answer questions
- **Embedding-Based Evaluation**: Supports cosine-similarity evaluation for classes and properties
- **Missing Entity Resolution**: Identifies and resolves entity IRIs mentioned in questions
- **SPARQL Query Generation**: Generates optimized SPARQL queries from natural language
- **Query Execution**: Executes queries against SPARQL endpoints and formats results
- **Multiple LLM Support**: Works with Gemini, Mistral (local), Azure OpenAI, and OpenAI models
- **Stage-Specific Providers**: Each pipeline stage can use its own provider and model
- **Interactive GUI**: A web-based chat interface with visual pipeline stages
- **CLI & Python API**: Use via command line or integrate into your Python applications
- **Interactive Mode**: Real-time question answering with immediate results

## 🏗️ Architecture

The framework follows a multi-stage pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                     OFFLINE PROCESSING                       │
├─────────────────────────────────────────────────────────────┤
│  SHACL File → Shape Extractor → M-Schema (JSON)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     ONLINE PROCESSING                        │
├─────────────────────────────────────────────────────────────┤
│  Natural Language Question                                   │
│            ↓                                                 │
│  1. Schema Formatting                                        │
│            ↓                                                 │
│  2. Class Relevance Evaluation (LLM or Embedding)            │
│            ↓                                                 │
│  3. Property Selection (LLM or Embedding)                    │
│            ↓                                                 │
│  4. Missing ID Collection (Optional)                        │
│            ↓                                                 │
│  5. SPARQL Query Generation (LLM)                           │
│            ↓                                                 │
│  6. Query Execution & Result Display                        │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Install from source

```bash
# Clone the repository
git clone https://github.com/Indeewarib/nl2sparql.git
cd nl2sparql

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

## ⚙️ Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

3. (Optional) Customize `config.yaml` to adjust:
   - LLM provider and model settings
   - SPARQL endpoint configuration
   - Pipeline stages
   - Output formats

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Your Endpoint

Edit `config.yaml` to set your SPARQL endpoint:

```yaml
sparql:
  endpoint_url: "http://localhost:8890/sparql"  # Your SPARQL endpoint
  default_graph: "http://localhost:8890/coporateNew"  # Optional: Named graph
```

### 3. Extract Schema (One-time setup)

If you have a SHACL TTL file, extract the schema:

```bash
python -c "
from nl2sparql.schema_parser import SHACLSchemaParser
from nl2sparql.schema_formatter import SchemaFormatter
import json

parser = SHACLSchemaParser()
schema = parser.parse('data/input/your_schema.ttl')

with open('data/output/my_schema_mschema.json', 'w') as f:
    json.dump(schema, f, indent=2)
"
```

### 4. Ask Questions via CLI

```bash
# Auto-detects appropriate schema based on question keywords
python run_query.py "Who is Ms. Brant?"
python run_query.py "What's the longitude of port USJNU?"
```

### 5. Interactive Web GUI (Recommended)

```bash
# Install Streamlit (first time only)
pip install streamlit

# Launch the interactive web interface
streamlit run nl2sparql/gui_v2.py
```

Then open **http://localhost:8501** in your browser!


## 📁 Project Structure

```
nl2sparql/
├── nl2sparql/              # Main package
│   ├── __init__.py
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Configuration management
│   ├── pipeline.py         # Pipeline orchestrator
│   ├── schema_parser.py    # SHACL parser
│   ├── schema_formatter.py # Schema formatting
│   ├── class_evaluator.py  # Class relevance evaluation
│   ├── property_evaluator.py # Property selection
│   ├── embedding_evaluator.py   # Legacy embedding evaluator
│   ├── embedding_evaluator_v2.py # Current embedding evaluator used by the pipeline
│   ├── sparql_generator.py # SPARQL query generation
│   ├── sparql_executor.py  # Query execution
│   └── llm_interface.py    # LLM abstraction layer
├── data/
│   ├── input/              # Input SHACL files
│   └── output/             # Generated schemas
├── tests/
│   ├── prompts/            # Saved prompts
│   ├── results/            # Saved query runs
│   ├── extractions/        # Saved extracted classes/properties
│   └── evaluation_results/ # Saved evaluation reports
├── evaluation_results/     # Top-level evaluation reports
├── logs/                   # Application logs
├── config.yaml             # Configuration file
├── .env.example            # Environment variables template
├── requirements.txt        # Python dependencies
├── setup.py               # Package setup
└── README.md              # This file
```

## 🔧 Configuration Options

### LLM Configuration

```yaml
llm:
  provider: "gemini"  # gemini, mistral, openai, azure
  model_name: "gemini-2.0-flash-exp"
  max_tokens: 500
  temperature: 0.0
```

### SPARQL Endpoint

```yaml
sparql:
  endpoint_url: "https://gptkb.org/query/"
  timeout: 30
  default_limit: 50
```

### Pipeline Stages

Enable or disable specific pipeline stages:

```yaml
pipeline:
  stages:
    schema_extraction: true
    class_extraction: true
    property_extraction: true
    missing_id_extraction: true
    query_generation: true
    query_execution: true
```

## 🎯 Features Examples

### Command Line Interface (CLI)

The CLI automatically detects which schema to use based on keywords in your question:

```bash
# Corporate/employee questions → uses coporate_mschema.json
python run_query.py "Which department is Ms. Brant in?"

# Maritime/port questions → uses copypu_mschema.json  
python run_query.py "What is the longitude of port USJNU?"

# To specify schema explicitly, use the installed CLI command
nl2sparql query "Your question" --schema data/output/specific_schema.json
```

### Pipeline API: End-to-End (Extract + Query)

```python
from nl2sparql import NL2SPARQLPipeline
from nl2sparql.utils import detect_schema_from_question

# Initialize pipeline
pipeline = NL2SPARQLPipeline()

# Ask a question
question = "Which department is Ms. Brant in?"
schema_path = detect_schema_from_question(question)

# Get results
results = pipeline.answer_question(question, schema_path)

# Access the generated SPARQL query
print(results["sparql_query"])

# Access formatted results
print(results["formatted_results"])
```

### Web GUI

Features:
- 🎨 Beautiful chat interface
- 🔍 Real-time schema selection (auto or manual)
- 📊 Visualize pipeline execution stages
- 💾 Export results as JSON
- 🔧 Configure and toggle pipeline stages
- 📋 View generated SPARQL queries

#### Read Question from File
```bash
nl2sparql query --question-file questions.txt --schema data/output/schema.json
```

### Python API: Online Q&A (Auto Schema)

```python
from nl2sparql import NL2SPARQLPipeline

# Initialize pipeline
pipeline = NL2SPARQLPipeline(config_path="config.yaml")

# Extract schema (offline step)
schema = pipeline.extract_schema("my_shacl_file.ttl")

# Answer questions (online step)
results = pipeline.answer_question(
    question="Who are the actors born in Rome?",
    schema_path="data/output/my_shacl_file_mschema.json"
)

# Access results
print(results["formatted_results"])
print(results["sparql_query"])
```
### Advanced Usage

#### Custom LLM Configuration

```python
from nl2sparql import NL2SPARQLPipeline, Config

# Load and customize config
config = Config()
config.config["llm"]["provider"] = "openai"
config.config["llm"]["model_name"] = "gpt-4"

pipeline = NL2SPARQLPipeline(config_path=config)
```

#### Using Individual Components

```python
from nl2sparql import SHACLSchemaParser, SchemaFormatter, create_llm

# Parse SHACL file
parser = SHACLSchemaParser(fix_syntax=True)
schema = parser.parse("input.ttl", save_json_path="output.json")

# Format for LLM consumption
formatter = SchemaFormatter(schema)
formatted = formatter.format_clean()

# Initialize LLM
llm = create_llm("gemini", api_key="your_key", model_name="gemini-2.0-flash-exp")
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Acknowledgments

- Built with support for multiple LLM providers (Gemini, Mistral, OpenAI)
- SHACL parsing powered by RDFLib
- SPARQL execution via SPARQLWrapper

## Contact

For questions or support, please open an issue on GitHub.

---

