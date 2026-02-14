import docker
import os
import tempfile
import tarfile
import time
from typing import List, Dict, Any

class DockerSandbox:
    def __init__(self, image="python:3.12-slim"):
        self.client = docker.from_env()
        self.image = image
        try:
            self.client.images.get(self.image)
        except docker.errors.ImageNotFound:
            print(f"Pulling image {self.image}...")
            self.client.images.pull(self.image)

    def _filter_apt_noise(self, text):
        """Filter out verbose apt-get output lines that clutter the terminal."""
        if not text:
            return text
        noise_prefixes = (
            'Reading package', 'Building dependency', 'Get:', 'Fetched',
            'Selecting previously', 'Preparing to unpack', 'Unpacking',
            'Setting up', 'Processing triggers', '(Reading database',
            'Adding \'diversion', 'Preconfiguring', 'Need to get',
            'After this operation', 'The following', 'Suggested packages',
            'update-alternatives', 'done.', 'Running hooks',
            'Updating certificates', '0 added', '146 added',
            'Current default', 'Local time', 'Universal Time', 'Run \'dpkg',
            'Hit:', 'Ign:',
        )
        lines = text.split('\n')
        filtered = [l for l in lines if not l.strip().startswith(noise_prefixes)]
        # Also filter lines that are just whitespace or package list spam
        filtered = [l for l in filtered if l.strip() and not l.strip().startswith(('  ', 'libc', 'lib', 'python3-', 'adduser', 'binutils'))]
        result = '\n'.join(filtered).strip()
        return result if result else None

    def execute_batch(self, files: Dict[str, str], commands: List[str], on_log: Any = None) -> Dict[str, Any]:
        """
        Executes a batch of commands in a Docker container with the provided files.
        Returns a dict with 'logs' and 'artifacts'.
        """
        logs = []
        artifacts = {}
        
        def log(type: str, content: str):
            entry = {"timestamp": time.time(), "type": type, "content": content}
            logs.append(entry)
            if on_log:
                on_log(entry)

        log("system", f"Initializing sandbox ({self.image})...")
        
        # Filter out redundant commands
        skip_prefixes = ('apt-get update', 'apt-get install', 'pip install decimal', 'pip3 install decimal')
        filtered_commands = []
        for cmd in commands:
            cmd_stripped = cmd.strip()
            if any(cmd_stripped.startswith(p) for p in skip_prefixes):
                log("system", f"Skipped (pre-installed): {cmd_stripped}")
                continue
            if 'pip install' in cmd_stripped or 'pip3 install' in cmd_stripped:
                if '--break-system-packages' not in cmd_stripped:
                    cmd = cmd_stripped + ' --break-system-packages'
            filtered_commands.append(cmd)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write files to temp directory
            for filename, content in files.items():
                file_path = os.path.join(temp_dir, filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w") as f:
                    f.write(content)
                log("file", f"Created: {filename}")

            # Create tar archive
            tar_path = os.path.join(temp_dir, "archive.tar")
            with tarfile.open(tar_path, "w") as tar:
                for filename in files.keys():
                    tar.add(os.path.join(temp_dir, filename), arcname=filename)
            
            container = None
            try:
                log("system", "Starting container...")
                container = self.client.containers.run(
                    self.image,
                    command="tail -f /dev/null",
                    detach=True,
                    working_dir="/app",
                    tty=True,
                    network_mode="host",
                    user="root",
                    environment={
                        "DEBIAN_FRONTEND": "noninteractive",
                        "TZ": "UTC",
                        "PYTHONDONTWRITEBYTECODE": "1",
                    },
                    mem_limit="512m",
                    cpu_period=100000,
                    cpu_quota=50000
                )
                
                # Copy files to container
                with open(tar_path, "rb") as f:
                    container.put_archive("/app", f.read())
                log("system", f"Deployed {len(files)} files to /app")

                # Bootstrap: install mpmath
                container.exec_run(
                    "sh -c 'pip install mpmath --break-system-packages -q 2>/dev/null'",
                    workdir="/app", demux=True
                )

                # Execute commands
                for cmd in filtered_commands:
                    log("command", f"$ {cmd}")
                    exec_result = container.exec_run(
                        f"sh -c '{cmd}'",
                        workdir="/app",
                        demux=True
                    )
                    
                    exit_code = exec_result.exit_code
                    stdout_bytes, stderr_bytes = exec_result.output
                    
                    if stdout_bytes:
                        stdout_text = stdout_bytes.decode("utf-8", errors='replace')
                        filtered = self._filter_apt_noise(stdout_text) if 'apt' in cmd.lower() else stdout_text
                        if filtered:
                            log("stdout", filtered)
                    
                    if stderr_bytes:
                        stderr_text = stderr_bytes.decode("utf-8", errors='replace')
                        filtered = self._filter_apt_noise(stderr_text) if 'apt' in cmd.lower() else stderr_text
                        if filtered:
                            log("stderr", filtered)
                    
                    if exit_code != 0:
                        log("error", f"Exit code {exit_code}")
                    else:
                        log("success", "OK")

                # --- ARTIFACT RETRIEVAL ---
                log("system", "Checking for artifacts...")
                # List all files in /app
                list_res = container.exec_run("find . -maxdepth 1 -not -type d", workdir="/app")
                if list_res.exit_code == 0:
                    found_files = list_res.output.decode().splitlines()
                    for f_raw in found_files:
                        fname = f_raw.strip().lstrip("./")
                        if not fname or fname == "archive.tar":
                            continue
                        # If it wasn't one of the input files, it's an artifact!
                        if fname not in files:
                            log("system", f"Retrieving artifact: {fname}")
                            try:
                                bits, stat = container.get_archive(f"/app/{fname}")
                                artifact_dir = "/root/self-improving-ai/sandbox_artifacts"
                                if not os.path.exists(artifact_dir):
                                    os.makedirs(artifact_dir)
                                
                                # Extract single file from tar bits
                                stream = b"".join(bits)
                                import io
                                with tarfile.open(fileobj=io.BytesIO(stream)) as tar:
                                    tar.extractall(path=artifact_dir)
                                
                                artifacts[fname] = os.path.join(artifact_dir, fname)
                            except Exception as ae:
                                log("error", f"Failed to retrieve {fname}: {ae}")

            except Exception as e:
                log("error", f"Sandbox error: {str(e)}")
            finally:
                if container:
                    log("system", "Cleaning up...")
                    try:
                        container.stop(timeout=1)
                        container.remove()
                    except:
                        pass
        
        return {"logs": logs, "artifacts": artifacts}
