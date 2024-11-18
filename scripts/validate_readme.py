#!/usr/bin/env python3

import re
import sys
import yaml
import subprocess
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional
import socket

class Step:
    def __init__(self, id: str, commands: List[str], depends_on: Optional[str] = None,
                 background: bool = False, validate_port: Optional[str] = None,
                 expected_output: Optional[str] = None, validate_url: Optional[str] = None,
                 expected_status: Optional[int] = None):
        self.id = id
        self.commands = commands
        self.depends_on = depends_on
        self.background = background
        self.validate_port = validate_port
        self.expected_output = expected_output
        self.validate_url = validate_url
        self.expected_status = expected_status
        self.process = None

class ReadmeValidator:
    def __init__(self, readme_path: str):
        self.readme_path = Path(readme_path)
        self.steps: Dict[str, Step] = {}
        self.requirements = {}
        self.env_vars = {}
        self.cleanup_commands = []
        self.parse_readme()

    def parse_readme(self):
        content = self.readme_path.read_text()
        
        # Parse requirements
        req_match = re.search(r'<!-- validate:requirements\n(.*?)\n-->', content, re.DOTALL)
        if req_match:
            self.requirements = yaml.safe_load(req_match.group(1))

        # Parse environment variables
        env_match = re.search(r'<!-- validate:env_vars\n(.*?)\n-->', content, re.DOTALL)
        if env_match:
            env_vars = yaml.safe_load(env_match.group(1))
            self.env_vars = {k: v for item in env_vars for k, v in item.items()}

        # Parse cleanup commands
        cleanup_matches = re.finditer(r'<!-- validate:cleanup -->\n```bash\n(.*?)\n```', content, re.DOTALL)
        for match in cleanup_matches:
            self.cleanup_commands.extend(match.group(1).strip().split('\n'))

        # Parse steps
        step_matches = re.finditer(
            r'<!-- validate:step id="([^"]+)"'
            r'(?:\s+depends_on="([^"]+)")?'
            r'(?:\s+background=(true|false))?'
            r'(?:\s+validate_port="([^"]+)")?'
            r'(?:\s+expected_output="([^"]+)")?'
            r'(?:\s+validate_url="([^"]+)")?'
            r'(?:\s+expected_status="(\d+)")?\s*-->\n'
            r'```bash\n(.*?)\n```',
            content,
            re.DOTALL
        )

        for match in step_matches:
            step_id = match.group(1)
            commands = match.group(8).strip().split('\n')
            self.steps[step_id] = Step(
                id=step_id,
                commands=commands,
                depends_on=match.group(2),
                background=match.group(3) == 'true',
                validate_port=match.group(4),
                expected_output=match.group(5),
                validate_url=match.group(6),
                expected_status=int(match.group(7)) if match.group(7) else None
            )

    def validate_requirements(self):
        print("Validating requirements...")
        if 'python' in self.requirements:
            python_version = subprocess.check_output(['python', '--version']).decode().strip()
            required_version = self.requirements['python']
            if required_version not in python_version:
                raise Exception(f"Python version mismatch. Required: {required_version}, Found: {python_version}")

        if self.requirements.get('docker'):
            try:
                subprocess.check_call(['docker', '--version'], stdout=subprocess.DEVNULL)
            except:
                raise Exception("Docker is required but not found")

        if self.requirements.get('pip'):
            try:
                subprocess.check_call(['pip', '--version'], stdout=subprocess.DEVNULL)
            except:
                raise Exception("pip is required but not found")

    def wait_for_port(self, port: int, timeout: int = 30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                socket.create_connection(('localhost', port), timeout=1)
                return True
            except (socket.timeout, ConnectionRefusedError):
                time.sleep(1)
        raise Exception(f"Timeout waiting for port {port}")

    def validate_step(self, step: Step) -> None:
        print(f"Executing step: {step.id}")
        
        # Check dependencies
        if step.depends_on and step.depends_on not in self.steps:
            raise Exception(f"Dependency {step.depends_on} not found for step {step.id}")

        # Execute commands
        for cmd in step.commands:
            print(f"  Running: {cmd}")
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if step.background:
                step.process = process
                if step.validate_port:
                    for port in map(int, step.validate_port.split(',')):
                        self.wait_for_port(port)
            else:
                stdout, stderr = process.communicate()
                if process.returncode != 0:
                    raise Exception(f"Command failed: {stderr.decode()}")
                
                if step.expected_output:
                    output = stdout.decode()
                    if step.expected_output not in output:
                        raise Exception(
                            f"Expected output '{step.expected_output}' not found in: {output}"
                        )

        # Validate URL if specified
        if step.validate_url:
            try:
                response = requests.get(step.validate_url)
                if step.expected_status and response.status_code != step.expected_status:
                    raise Exception(
                        f"Expected status {step.expected_status} but got {response.status_code}"
                    )
            except requests.RequestException as e:
                raise Exception(f"Failed to validate URL {step.validate_url}: {e}")

    def cleanup(self):
        print("Cleaning up...")
        for cmd in self.cleanup_commands:
            try:
                subprocess.run(cmd, shell=True, check=False)
            except:
                pass
        
        for step in self.steps.values():
            if step.process:
                try:
                    step.process.terminate()
                    step.process.wait(timeout=5)
                except:
                    try:
                        step.process.kill()
                    except:
                        pass

    def validate_all(self):
        try:
            self.validate_requirements()
            
            # Execute steps in order, respecting dependencies
            executed = set()
            while len(executed) < len(self.steps):
                for step_id, step in self.steps.items():
                    if step_id in executed:
                        continue
                    if step.depends_on and step.depends_on not in executed:
                        continue
                    self.validate_step(step)
                    executed.add(step_id)
                    
            print("All steps validated successfully!")
            return True
            
        except Exception as e:
            print(f"Validation failed: {e}", file=sys.stderr)
            return False
        finally:
            self.cleanup()

if __name__ == '__main__':
    readme_path = Path(__file__).parent.parent / 'README.md'
    validator = ReadmeValidator(readme_path)
    sys.exit(0 if validator.validate_all() else 1)
