import os
import sys

# Ensure the current directory is in the python path
sys.path.append(os.getcwd())

from src.graph import app as workflow
from src.state import AgentState

def test_import_fix():
    print("Testing Ouroboros Architect with general import fix...")
    
    # Task that implies a module name, but should be handled by 'solution' import
    task = "Write a python function `fib(n)` that returns the n-th Fibonacci number."
    
    initial_state = AgentState(
        task=task,
        code_solution="",
        test_cases="",
        execution_result="",
        reflections=[],
        iteration=0,
        is_solved=False,
        dependencies=[]
    )
    
    # Run the workflow
    final_state = workflow.invoke(initial_state)
    
    print("\n--- Final State ---")
    print(f"Iterations: {final_state['iteration']}")
    print(f"Solved: {final_state['is_solved']}")
    
    if final_state['is_solved']:
        print("SUCCESS: The agent generated correct code and tests used 'solution' import.")
        print(f"Code Solution:\n{final_state['code_solution']}")
        print(f"Test Cases:\n{final_state['test_cases']}")
    else:
        print("FAILURE: The agent failed.")
        print(f"Last Execution Result:\n{final_state['execution_result']}")

if __name__ == "__main__":
    test_import_fix()
