import dspy
import os
import json
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()

# Configure DSPy to use Gemini
gemini = dspy.Google(model='models/gemini-2.0-flash', api_key=os.getenv('GEMINI_API_KEY'))
# Increase max output tokens
gemini.kwargs['max_output_tokens'] = 8192
dspy.settings.configure(lm=gemini)

class SolutionGeneratorSignature(dspy.Signature):
    """Generates a solution including necessary files and shell commands to verify it.
    
    The goal is to solve the user's task and VERIFY it.
    
    Output `files` as a dictionary where keys are filenames and values are file contents.
    Output `commands` as a list of shell commands to run to verify the solution.
    
    IMPORTANT: The execution environment is a raw Ubuntu container. 
    You MUST install any necessary dependencies (python3, nodejs, gcc, etc.) using `apt-get` before running your code.
    Always run `apt-get update` before installing.
    
    Example Output:
    Files: {"main.py": "print('hello')"}
    Commands: ["apt-get update", "apt-get install -y python3", "python3 main.py"]
    """
    task = dspy.InputField(desc="The coding task description.")
    reflections = dspy.InputField(desc="Previous reflections and critiques.")
    
    files = dspy.OutputField()
    commands = dspy.OutputField()

class ReflectorSignature(dspy.Signature):
    """Analyzes the execution output and provides a critique and reflection.
    
    Analyze the logs. Did the solution work as expected?
    If there were errors, explain WHY and suggest a fix.
    
    Output `critique` as a string.
    """
    files = dspy.InputField(desc="The files used in the solution.")
    commands = dspy.InputField(desc="The commands executed.")
    execution_logs = dspy.InputField(desc="The verbose execution logs.")
    
    critique = dspy.OutputField()

class SolutionGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.Predict(SolutionGeneratorSignature)

    def _parse_output(self, output, expected_type=None, key_hint=None, validator=None):
        """Parses the output string into a Python object, searching for valid JSON blocks."""
        if not isinstance(output, str):
            return output
            
        import json
        import ast
        import re
        
        # Regex to find code blocks
        # pattern matches ```json ... ``` or ``` ... ```
        # We use dotall to match newlines
        # More permissive regex
        code_blocks = re.findall(r"```\w*\s*(.*?)```", output, re.DOTALL)
        
        candidates = []
        if code_blocks:
            candidates.extend(code_blocks)
        else:
            candidates.append(output) # No blocks, try raw
            
        for block in candidates:
            block = block.strip()
            parsed = None
            try:
                # Try ast first
                parsed = ast.literal_eval(block)
            except:
                try:
                    # Try json
                    block_fixed = block.replace("'", '"')
                    parsed = json.loads(block_fixed)
                except:
                    continue
            
            if parsed is not None:
                # Check constraints
                if expected_type:
                    # If expected_type is a tuple, isinstance works
                    if not isinstance(parsed, expected_type):
                        continue
                
                if key_hint and isinstance(parsed, dict) and key_hint not in parsed:
                    if isinstance(parsed, dict):
                         # Case insensitive check
                         found = False
                         for k in parsed.keys():
                             if k.lower() == key_hint.lower():
                                 found = True
                                 break
                         if expected_type == dict and not found:
                             continue
                    else:
                        continue
                
                if validator:
                    if not validator(parsed):
                        continue
                        
                # If we're here, it's a good candidate
                return parsed
                
        # If nothing matched constraints, try to return something loosely
        # or return the first successful parse
        return None

    def forward(self, task, reflections):
        reflections_str = "\n".join(reflections) if reflections else "None"
        try:
            result = self.generate(task=task, reflections=reflections_str)
            
            # Debug: Log raw output to help diagnose parsing issues
            print(f"DEBUG: Raw Files Output:\n{result.files}\n")
            print(f"DEBUG: Raw Commands Output:\n{result.commands}\n")
            
            files = {}
            commands = []
            
            # Parse files: Expect dict
            files = self._parse_output(result.files, expected_type=dict)
            if not files: 
                 files = {}
            
            # Unnest "files" key if present
            if "files" in files and isinstance(files["files"], dict):
                print("DEBUG: Unnesting 'files' key from parsed files")
                files = files["files"]

            # Parse commands: Expect list OR dict with "commands"
            def command_validator(obj):
                if isinstance(obj, list): return True
                if isinstance(obj, dict):
                    for k in obj.keys():
                        if k.lower() == "commands": return True
                return False

            commands_obj = self._parse_output(result.commands, expected_type=(list, dict), validator=command_validator)
            
            if isinstance(commands_obj, list):
                commands = commands_obj
            elif isinstance(commands_obj, dict):
                 # Search for "commands" key
                 for k, v in commands_obj.items():
                     if k.lower() == "commands" and isinstance(v, list):
                         commands = v
                         break
            
            if not isinstance(commands, list):
                 # Fallback: Try to find commands in result.files
                 commands_obj = self._parse_output(result.files, expected_type=(list, dict), validator=command_validator)
                 
                 if isinstance(commands_obj, list):
                     commands = commands_obj
                 elif isinstance(commands_obj, dict):
                      # Search for "commands" key
                      for k, v in commands_obj.items():
                          if k.lower() == "commands" and isinstance(v, list):
                              commands = v
                              break
            
            if not isinstance(commands, list):
                print(f"WARNING: Parsed commands is not a list: {type(commands_obj)}")
                commands = [] # Fail safe
                
            return dspy.Prediction(files=files, commands=commands)
            
        except Exception as e:
            print(f"Error in SolutionGenerator: {e}")
            return dspy.Prediction(files={}, commands=[])

class Reflector(dspy.Module):
    def __init__(self):
        super().__init__()
        self.reflect = dspy.Predict(ReflectorSignature)

    def forward(self, files, commands, execution_logs):
        files_str = json.dumps(files)
        commands_str = json.dumps(commands)
        logs_str = json.dumps(execution_logs)
        
        try:
            result = self.reflect(files=files_str, commands=commands_str, execution_logs=logs_str)
            return dspy.Prediction(critique=result.critique)
        except Exception as e:
             print(f"Error in Reflector: {e}")
             return dspy.Prediction(critique=f"Error analyzing execution: {e}")

class FinalSummarySignature(dspy.Signature):
    """Generates a concise and professional summary of the completed task and solution.
    
    Describe what files were created and what they do.
    Mention the verification steps taken.
    """
    task = dspy.InputField(desc="The original user task.")
    files = dspy.InputField(desc="The files created to solve the task.")
    execution_logs = dspy.InputField(desc="The logs from the verification execution.")
    
    summary = dspy.OutputField(desc="A markdown summary of the solution.")

class FinalSummarizer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarize = dspy.Predict(FinalSummarySignature)
        
    def forward(self, task, files, execution_logs):
        files_str = json.dumps(files)
        # Simplify logs to avoid token limit issues
        simple_logs = []
        parsed_logs = execution_logs if isinstance(execution_logs, list) else []
        
        for log in parsed_logs:
             if log.get('type') in ['command', 'success', 'error']:
                 simple_logs.append(f"{log.get('type')}: {log.get('content')}")
        
        logs_str = "\n".join(simple_logs)
        
        try:
            result = self.summarize(task=task, files=files_str, execution_logs=logs_str)
            return dspy.Prediction(summary=result.summary)
        except Exception as e:
            print(f"Error in FinalSummarizer: {e}")
            return dspy.Prediction(summary="Task completed successfully.")
