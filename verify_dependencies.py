import os
import sys

# Ensure the current directory is in the python path
sys.path.append(os.getcwd())

from src.graph import app as workflow
from src.state import AgentState

def test_dependency_agent():
    print("Testing Ouroboros Architect with a task requiring dependencies...")
    
    # Task that requires numpy (not in python:3.9-slim by default)
    task = "Write a python function using numpy to calculate the mean of a list of numbers. The function should be named `calculate_mean`."
    
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
    print(f"Dependencies: {final_state.get('dependencies', [])}")
    
    if final_state['is_solved']:
        print("SUCCESS: The agent generated correct code and installed dependencies.")
        print(f"Code Solution:\n{final_state['code_solution']}")
    else:
        print("FAILURE: The agent failed.")
        print(f"Last Execution Result:\n{final_state['execution_result']}")

if __name__ == "__main__":
    test_dependency_agent()
