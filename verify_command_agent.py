import os
import sys

# Ensure the current directory is in the python path
sys.path.append(os.getcwd())

print("Starting imports...")
from src.graph import app as workflow
print("Imports done.")
from src.state import AgentState

def test_command_agent():
    print("Testing Ouroboros Architect with Refined State...")
    
    # Task that implies a file and a command to run it
    task = "Write a python script `hello.py` that prints 'Hello, World!' and run it."
    
    initial_state = AgentState(
        task=task,
        files={},
        commands=[],
        execution_logs=[],
        execution_result="",
        execution_error="",
        reflections=[],
        iteration=0,
        is_solved=False
    )
    
    # Run the workflow
    print("Streaming workflow execution...")
    final_state = initial_state.copy()
    for event in workflow.stream(initial_state):
        for key, value in event.items():
            print(f"Node completed: {key}")
            # print(value) # Debug
            if key == "generate":
                print(f"Generated commands: {value.get('commands')}")
            elif key == "execute":
                print(f"Execution logs count: {len(value.get('execution_logs', []))}")
                print(f"Execution Result (Summary): {value.get('execution_result')[:50]}...")
                
            # Update final state with the latest values
            final_state.update(value)
    
    print("\n--- Final State ---")
    print(f"Iterations: {final_state['iteration']}")
    print(f"Solved: {final_state['is_solved']}")
    
    print("\n--- Files Generated ---")
    for fname, content in final_state.get('files', {}).items():
        print(f"File: {fname}")
        print(f"Content:\n{content}\n")
        
    print("\n--- Execution Summary ---")
    print(f"Result: {final_state.get('execution_result')}")
    print(f"Error: {final_state.get('execution_error')}")

if __name__ == "__main__":
    test_command_agent()
