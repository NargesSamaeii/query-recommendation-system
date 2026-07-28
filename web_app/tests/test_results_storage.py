#!/usr/bin/env python3
"""
Test script for NL2SPARQL Results Storage System

Validates that results are stored correctly in JSON format.
"""

import json
import os
import sys
from pathlib import Path


def test_import_modules():
    """Test that all new modules can be imported."""
    print("Testing module imports...")
    try:
        from nl2sparql.results_manager import ResultsManager
        print("  ✓ ResultsManager imported successfully")
    except Exception as e:
        print(f"  ✗ Failed to import ResultsManager: {e}")
        return False
    
    try:
        from nl2sparql.results_viewer import (
            list_all_results, 
            get_latest_result, 
            format_result_for_display
        )
        print("  ✓ Results viewer utilities imported successfully")
    except Exception as e:
        print(f"  ✗ Failed to import results viewer: {e}")
        return False
    
    return True


def test_create_sample_result():
    """Test creating and saving a sample result."""
    print("\nTesting result creation and storage...")
    try:
        from nl2sparql.results_manager import ResultsManager
        
        rm = ResultsManager("test_results")
        
        # Create a sample result
        result = rm.create_result_entry("Who is our Sensor expert?")
        
        # Verify structure
        assert "metadata" in result
        assert "pipeline" in result
        assert "prompts" in result
        assert "statistics" in result
        
        print("  ✓ Result structure created successfully")
        
        # Update with sample data
        result["pipeline"]["class_extraction"]["extracted_classes"] = [
            "prod_vocab:Employee",
            "prod_vocab:ProductCategory"
        ]
        result["pipeline"]["class_extraction"]["class_count"] = 2
        
        print("  ✓ Result data updated")
        
        # Save result
        filepath = rm.save_result(result, "test_sample")
        
        if os.path.exists(filepath):
            print(f"  ✓ Result saved successfully to {filepath}")
        else:
            print(f"  ✗ Result file not created at {filepath}")
            return False
        
        # Verify file is valid JSON
        with open(filepath, 'r') as f:
            loaded = json.load(f)
        print("  ✓ Result file is valid JSON")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_results_viewer():
    """Test results viewer functionality."""
    print("\nTesting results viewer...")
    try:
        from nl2sparql.results_viewer import (
            list_all_results,
            get_latest_result,
            format_result_for_display
        )
        
        # List results
        results = list_all_results("test_results", limit=5)
        print(f"  ✓ Found {len(results)} result(s)")
        
        if results:
            # Get latest
            latest = get_latest_result("test_results")
            if latest:
                print("  ✓ Retrieved latest result")
                
                # Format for display
                formatted = format_result_for_display(latest)
                if formatted and len(formatted) > 100:
                    print("  ✓ Result formatted for display")
                else:
                    print("  ✗ Formatted result too short")
                    return False
            else:
                print("  ✗ Failed to get latest result")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_json_validation():
    """Test that all saved results are valid JSON."""
    print("\nValidating JSON results...")
    try:
        results_dir = "test_results"
        if not os.path.exists(results_dir):
            print("  - No test_results directory found (skipping)")
            return True
        
        valid_count = 0
        for filename in os.listdir(results_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(results_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        json.load(f)
                    valid_count += 1
                except json.JSONDecodeError as e:
                    print(f"  ✗ Invalid JSON in {filename}: {e}")
                    return False
        
        print(f"  ✓ All {valid_count} result files are valid JSON")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_result_structure():
    """Test that result structure matches expected schema."""
    print("\nValidating result structure...")
    try:
        from nl2sparql.results_manager import ResultsManager
        
        rm = ResultsManager("test_results")
        result = rm.create_result_entry("Test question")
        
        # Check all required sections exist
        required_sections = {
            "metadata": ["timestamp", "question"],
            "pipeline": [
                "class_extraction",
                "property_extraction", 
                "missing_id_extraction",
                "query_generation",
                "query_execution"
            ],
            "prompts": [
                "class_extraction_prompts",
                "property_extraction_prompts",
                "missing_id_query_prompt",
                "final_query_generation_prompt"
            ],
            "statistics": ["stages_completed", "total_time_ms", "errors"]
        }
        
        for section, fields in required_sections.items():
            if section not in result:
                print(f"  ✗ Missing section: {section}")
                return False
            
            for field in fields:
                if section == "metadata" or section == "statistics":
                    if field not in result[section]:
                        print(f"  ✗ Missing field in {section}: {field}")
                        return False
                elif section == "pipeline":
                    if field not in result[section]:
                        print(f"  ✗ Missing pipeline stage: {field}")
                        return False
                    # Check stage has required fields
                    stage = result[section][field]
                    if "config" not in stage:
                        print(f"  ✗ Missing 'config' in {field}")
                        return False
                elif section == "prompts":
                    if field not in result[section]:
                        print(f"  ✗ Missing prompt field: {field}")
                        return False
        
        print("  ✓ All required sections and fields present")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def cleanup_test_results():
    """Clean up test results directory."""
    print("\nCleaning up test files...")
    try:
        import shutil
        if os.path.exists("test_results"):
            shutil.rmtree("test_results")
            print("  ✓ Test directory cleaned up")
        return True
    except Exception as e:
        print(f"  ✗ Error cleaning up: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("NL2SPARQL Results Storage System - Test Suite")
    print("=" * 70)
    
    tests = [
        ("Module Imports", test_import_modules),
        ("Result Creation", test_create_sample_result),
        ("Result Structure", test_result_structure),
        ("Results Viewer", test_results_viewer),
        ("JSON Validation", test_json_validation),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results[test_name] = "PASS" if passed else "FAIL"
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            results[test_name] = "ERROR"
    
    # Cleanup
    cleanup_test_results()
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results.values() if r == "PASS")
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓" if result == "PASS" else "✗"
        print(f"{status} {test_name}: {result}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Results storage system is working correctly.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
