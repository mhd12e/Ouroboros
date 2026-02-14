import os
import sys

# Ensure the current directory is in the python path
sys.path.append(os.getcwd())

from src.graph import app as workflow
from src.state import AgentState

def test_fibonacci_agent():
    print("Testing Ouroboros Architect with a Fibonacci task...")
    
    # We ask for a relatively simple task but valid python code
    task = "Write a python function `fib(n)` that returns the n-th Fibonacci number. Ensure it handles n=0 and n=1 correctly."
    
    initial_state = AgentState(
        task=task,
        code_solution="",
        test_cases="",
        execution_result="",
        reflections=[],
        iteration=0,
        is_solved=False
    )
    
    # Run the workflow
    final_state = workflow.invoke(initial_state)
    
    print("\n--- Final State ---")
    print(f"Iterations: {final_state['iteration']}")
    print(f"Solved: {final_state['is_solved']}")
    print(f"Reflections: {len(final_state['reflections'])}")
    
    if final_state['is_solved']:
        print("SUCCESS: The agent generated correct code.")
        print(f"Code Solution:\n{final_state['code_solution']}")
    else:
        print("FAILURE: The agent failed to generate correct code.")
        print(f"Last Execution Result:\n{final_state['execution_result']}")
        print(f"Reflections:\n{final_state['reflections']}")

if __name__ == "__main__":
    test_fibonacci_agent()
