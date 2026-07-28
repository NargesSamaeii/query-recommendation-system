"""
Command Line Interface for NL2SPARQL

Provides CLI commands for the NL2SPARQL pipeline.
"""

import argparse
import sys
import json
import subprocess
from pathlib import Path

from .pipeline import NL2SPARQLPipeline
from .config import Config


def extract_schema_command(args):
    """Handle schema extraction command."""
    pipeline = NL2SPARQLPipeline(args.config)
    
    for ttl_file in args.input:
        print(f"\nProcessing: {ttl_file}")
        try:
            schema = pipeline.extract_schema(ttl_file, args.output)
            print(f"✓ Schema extracted successfully")
            
            # Ask user if they want to precompute embeddings
            num_classes = len(schema.get('classes', {}))
            num_properties = sum(len(c.get('properties', [])) for c in schema.get('classes', {}).values())
            print(f"\n  Schema contains: {num_classes} classes, {num_properties} properties")
            print(f"  Using embedding method will compute ~17 min on first query (DBpedia size)")
            print(f"  Pre-computing embeddings now will save time for repeated queries:")
            
            response = input("\n  Pre-compute embeddings for this schema? (y/n): ").strip().lower()
            
            if response in ['y', 'yes']:
                # Precompute embeddings
                from .embedding_evaluator_v2 import EmbeddingEvaluator
                
                extraction_config = pipeline.config.get("pipeline.extraction.embedding", {})
                model_name = extraction_config.get("model", "all-mpnet-base-v2")
                cache_config = extraction_config.get("cache", {})
                use_cache = cache_config.get("enabled", True)
                cache_dir = cache_config.get("cache_dir", "cache/embeddings")
                
                print(f"\n  Initializing embedding model ({model_name})...")
                evaluator = EmbeddingEvaluator(
                    model_name=model_name,
                    use_cache=use_cache,
                    cache_dir=cache_dir
                )
                
                result = evaluator.precompute_embeddings(schema)
                
                if result.get("status") == "success":
                    print(f"\n✓ Embeddings precomputed and cached!")
                    print(f"  Classes: {result['classes_cached']}")
                    print(f"  Properties: {result['properties_cached']}")
                else:
                    print(f"\n✗ Failed to precompute embeddings: {result.get('reason', 'unknown error')}")
            else:
                print(f"\n  Embeddings will be computed on first query (can take 17+ min for large schemas)")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()


def query_command(args):
    """Handle query command."""
    pipeline = NL2SPARQLPipeline(args.config)
    
    # Read question
    if args.question:
        question = args.question
    elif args.question_file:
        with open(args.question_file, 'r', encoding='utf-8') as f:
            question = f.read().strip()
    else:
        # Interactive mode
        question = input("Enter your question: ").strip()
    
    if not question:
        print("Error: No question provided")
        return
    
    print(f"\nQuestion: {question}\n")
    
    try:
        results = pipeline.answer_question(question, args.schema)
        
        # Display results
        if "formatted_results" in results:
            print("\n" + "="*60)
            print("RESULTS")
            print("="*60)
            print(results["formatted_results"])
        
        if args.show_query and "sparql_query" in results:
            print("\n" + "="*60)
            print("GENERATED SPARQL QUERY")
            print("="*60)
            print(results["sparql_query"])
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n✓ Full results saved to {args.output}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()


def interactive_command(args):
    """Handle interactive mode."""
    pipeline = NL2SPARQLPipeline(args.config)
    
    print("\n" + "="*60)
    print("NL2SPARQL Interactive Mode")
    print("="*60)
    print("Type 'exit' or 'quit' to exit")
    print("Type 'help' for commands\n")
    
    while True:
        try:
            question = input("Question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit', 'q']:
                print("Goodbye!")
                break
            
            if question.lower() == 'help':
                print("\nCommands:")
                print("  exit, quit, q  - Exit interactive mode")
                print("  help           - Show this help message")
                print("  schema <path>  - Change schema file")
                print("\nOtherwise, type your question in natural language.\n")
                continue
            
            if question.lower().startswith('schema '):
                args.schema = question.split(' ', 1)[1]
                print(f"Schema changed to: {args.schema}\n")
                continue
            
            # Process question
            results = pipeline.answer_question(question, args.schema)
            
            if "formatted_results" in results:
                print("\n" + "-"*60)
                print(results["formatted_results"])
                print("-"*60 + "\n")
            
            if "sparql_query" in results:
                show = input("Show generated SPARQL query? (y/n): ").strip().lower()
                if show == 'y':
                    print("\n" + results["sparql_query"] + "\n")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


def config_command(args):
    """Handle config command."""
    config = Config(args.config)
    
    if args.show:
        import yaml
        print("\nCurrent Configuration:")
        print("="*60)
        print(yaml.dump(config.config, default_flow_style=False))
    
    if args.key:
        value = config.get(args.key)
        if value is not None:
            print(f"{args.key} = {value}")
        else:
            print(f"Key '{args.key}' not found in configuration")


def gui_command(args):
    """Handle GUI command - launch Streamlit interface."""
    print(f"\n🔮 Launching NL2SPARQL Interactive GUI...")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"\n   Open your browser to: http://{args.host}:{args.port}\n")
    
    # Get the directory of the gui.py file
    gui_path = Path(__file__).parent / "gui_v2.py"
    
    # Verify GUI file exists
    if not gui_path.exists():
        print(f"❌ Error: GUI file not found at {gui_path}")
        print(f"\nAvailable files in {gui_path.parent}:")
        for f in gui_path.parent.glob("*.py"):
            print(f"  - {f.name}")
        sys.exit(1)
    
    try:
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(gui_path),
            "--server.port", str(args.port),
            "--server.address", args.host
        ], check=False)
    except KeyboardInterrupt:
        print("\n\n👋 GUI closed. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error launching GUI: {e}")
        print("\nMake sure Streamlit is installed:")
        print("   pip install streamlit pandas")
        print("\nTroubleshooting:")
        print("   1. Check GUI file exists: " + str(gui_path))
        print("   2. Try manual launch: streamlit run " + str(gui_path))
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="NL2SPARQL - Natural Language to SPARQL Query Translation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract schema from SHACL file
  nl2sparql extract input.ttl
  
  # Ask a question
  nl2sparql query "Who are actors born in Rome?" --schema data/output/schema.json
  
  # Interactive mode
  nl2sparql interactive --schema data/output/schema.json
  
  # Show configuration
  nl2sparql config --show
        """
    )
    
    parser.add_argument('--config', type=str, help='Path to config.yaml file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract schema from SHACL TTL file')
    extract_parser.add_argument('input', nargs='+', help='Input SHACL TTL file(s)')
    extract_parser.add_argument('--output', '-o', help='Output JSON filename')
    extract_parser.set_defaults(func=extract_schema_command)
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Answer a natural language question')
    query_parser.add_argument('question', nargs='?', help='Natural language question')
    query_parser.add_argument('--schema', '-s', required=True, help='Path to m_schema JSON file')
    query_parser.add_argument('--question-file', '-f', help='Read question from file')
    query_parser.add_argument('--output', '-o', help='Save full results to JSON file')
    query_parser.add_argument('--show-query', action='store_true', help='Show generated SPARQL query')
    query_parser.set_defaults(func=query_command)
    
    # Interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Start interactive Q&A mode')
    interactive_parser.add_argument('--schema', '-s', required=True, help='Path to m_schema JSON file')
    interactive_parser.set_defaults(func=interactive_command)
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_parser.add_argument('--show', action='store_true', help='Show current configuration')
    config_parser.add_argument('--key', help='Get specific configuration value')
    config_parser.set_defaults(func=config_command)
    
    # GUI command
    gui_parser = subparsers.add_parser('gui', help='Launch interactive web GUI')
    gui_parser.add_argument('--port', type=int, default=8501, help='Port for web interface (default: 8501)')
    gui_parser.add_argument('--host', default='localhost', help='Host for web interface (default: localhost)')
    gui_parser.set_defaults(func=gui_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    args.func(args)


if __name__ == '__main__':
    main()
