#!/usr/bin/env python3
"""
Simple test runner script
Usage: python run_test_generator.py [config_file]
"""

import sys
import os
from pathlib import Path

def main():
    # Add the scripts directory to the path
    scripts_dir = Path(__file__).parent
    sys.path.insert(0, str(scripts_dir))
    
    # Import the test generator
    try:
        from generate_test import TestGenerator
    except ImportError as e:
        print(f"Error importing TestGenerator: {e}")
        print("Make sure pandas and pyyaml are installed:")
        print("pip install pandas pyyaml")
        sys.exit(1)
    
    # Get config file from command line or use default
    config_file = sys.argv[1] if len(sys.argv) > 1 else "test_config.yaml"
    
    # Change to the scripts directory to run
    original_dir = os.getcwd()
    os.chdir(scripts_dir)
    
    try:
        # Create test generator
        generator = TestGenerator(config_file)
        
        # Generate tests
        print("🔄 Starting test generation...")
        results = generator.generate_test()
        
        print("\n✅ Test generation completed successfully!")
        print("\n📁 Generated files:")
        for file_type, file_path in results.items():
            print(f"   {file_type}: {file_path}")
            
        # Show total questions and points
        generator.load_questions()
        questions = generator.select_questions()
        total_points = sum(q['calculated_points'] for q in questions)
        print(f"\n📊 Test Statistics:")
        print(f"   Total questions: {len(questions)}")
        print(f"   Total points: {total_points}")
        
        # Show difficulty breakdown
        difficulty_counts = {}
        for q in questions:
            diff = q['original_difficulty']
            if diff not in difficulty_counts:
                difficulty_counts[diff] = {'count': 0, 'points': 0}
            difficulty_counts[diff]['count'] += 1
            difficulty_counts[diff]['points'] += q['calculated_points']
        
        print(f"   Difficulty breakdown:")
        for diff, stats in difficulty_counts.items():
            print(f"     {diff}: {stats['count']} questions, {stats['points']} points")
            
    except Exception as e:
        print(f"\n❌ Error generating test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Change back to original directory
        os.chdir(original_dir)

if __name__ == "__main__":
    main()