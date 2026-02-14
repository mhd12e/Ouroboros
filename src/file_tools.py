"""Host-safe file system tools for the agent to read/edit/run code."""
import os
import subprocess
import glob

def read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Read a file from the host filesystem. Optional line range (1-indexed)."""
    try:
        if not os.path.exists(path):
            return f"Error: File '{path}' not found."
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        start = (start_line - 1) if start_line else 0
        end = end_line if end_line else total_lines
        
        # Clamp ranges
        start = max(0, min(start, total_lines))
        end = max(start, min(end, total_lines))
        
        content = "".join(lines[start:end])
        
        if start_line or end_line:
            return f"--- {path} ({start+1}-{end}/{total_lines}) ---\n{content}"
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file (overwrites). Creates directories if needed."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} chars to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace an exact block of text in a file with new text."""
    try:
        if not os.path.exists(path):
            return f"Error: File '{path}' not found."
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if old_text not in content:
            # Try stripping whitespace if exact match fails
            if old_text.strip() not in content:
                return f"Error: 'old_text' not found in {path}. Please check indentation/whitespace exact match."
            # If strip matches, warn but maybe don't apply automatically to be safe?
            # Or use count=1 replace on full text?
            return f"Error: Exact 'old_text' match failed. Be precise with whitespace."
            
        new_content = content.replace(old_text, new_text, 1) # Only replace first occurrence to be safe
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return f"Successfully edited {path}"
    except Exception as e:
        return f"Error editing file: {e}"


def list_files(path: str = ".", max_depth: int = 2) -> str:
    """List files in directory (recursive up to depth)."""
    try:
        if not os.path.isdir(path):
            return f"Error: '{path}' is not a directory."
            
        results = []
        for root, dirs, files in os.walk(path):
            depth = root[len(path):].count(os.sep)
            if depth >= max_depth:
                del dirs[:] # Don't recurse deeper
                continue
                
            for name in files:
                if name.startswith('.'): continue # Skip hidden
                rel_path = os.path.relpath(os.path.join(root, name), path)
                results.append(rel_path)
                
        return "\n".join(sorted(results))
    except Exception as e:
        return f"Error listing files: {e}"


def run_command(command: str, cwd: str = None) -> str:
    """Run a shell command on the host system."""
    try:
        # Security check? 
        # The user has authorized "prod ready coding tools".
        # We assume the agent is trusted.
        
        result = subprocess.run(
            command, 
            shell=True, 
            cwd=cwd, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        output = f"Exit Code: {result.returncode}\n"
        output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
            
        return output
    except Exception as e:
        return f"Error running command: {e}"
