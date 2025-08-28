#!/usr/bin/env python3
"""
Test runner for hashwrap test suite.
Runs all tests and provides a summary.
"""

import sys
import os
import unittest
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_all_tests():
    """Run all tests in the tests directory."""
    print("="*70)
    print("HASHWRAP TEST SUITE")
    print("="*70)
    print()
    
    # Get test directory
    test_dir = Path(__file__).parent / "tests"
    
    # Discover and load tests
    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir), pattern="test_*.py")
    
    # Count tests
    test_count = suite.countTestCases()
    print(f"Found {test_count} tests")
    print()
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()
    
    # Print summary
    print()
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Time: {end_time - start_time:.2f} seconds")
    print()
    
    # Print failures and errors if any
    if result.failures:
        print("FAILURES:")
        for test, traceback in result.failures:
            print(f"\n{test}:")
            print(traceback)
    
    if result.errors:
        print("ERRORS:")
        for test, traceback in result.errors:
            print(f"\n{test}:")
            print(traceback)
    
    # Return success/failure
    return len(result.failures) + len(result.errors) == 0


def run_specific_test(test_module):
    """Run a specific test module."""
    print(f"Running tests from: {test_module}")
    print("="*70)
    
    # Import and run
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f"tests.{test_module}")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test module
        test_module = sys.argv[1]
        if not test_module.startswith("test_"):
            test_module = f"test_{test_module}"
        if test_module.endswith(".py"):
            test_module = test_module[:-3]
        
        success = run_specific_test(test_module)
    else:
        # Run all tests
        success = run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)