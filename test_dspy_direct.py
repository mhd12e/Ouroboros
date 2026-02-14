import os
import sys

# Ensure the current directory is in the python path
sys.path.append(os.getcwd())

from src.dspy_modules import SolutionGenerator

def test_direct():
    print("Testing SolutionGenerator directly...")
    
    generator = SolutionGenerator()
    task = "Write a python script `hello.py` that prints 'Hello, World!' and run it."
    
    try:
        result = generator(task=task, reflections=[])
        print("\n--- Result ---")
        print(f"Files: {result.files}")
        print(f"Commands: {result.commands}")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_direct()
