import yaml
import subprocess
import sys
import os

def run_command(command):
    """Executes a shell command and prints the output."""
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e.stderr}")
        sys.exit(1)

def launch_vm(config_path):
    # Load YAML configuration
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        return

    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)

    vm = config['vm_settings']
    
    print(f"--- Launching VM: {vm['name']} ---")
    
    # Construct the Multipass launch command
    launch_cmd = [
        "multipass", "launch",
        "--name", vm['name'],
        "--cpus", str(vm['cpus']),
        "--memory", vm['memory'],
        "--disk", vm['disk'],
        vm['image']
    ]

    # Optional: Add cloud-init if provided for auto-configuration
    if 'cloud_init' in vm:
        with open("temp_cloud_init.yaml", "w") as f:
            f.write(vm['cloud_init'])
        launch_cmd.extend(["--cloud-init", "temp_cloud_init.yaml"])

    run_command(launch_cmd)
    
    # Clean up temp file
    if os.path.exists("temp_cloud_init.yaml"):
        os.remove("temp_cloud_init.yaml")

    print(f"--- VM {vm['name']} is now running! ---")
    print("To enter the VM, run: multipass shell " + vm['name'])

if __name__ == "__main__":
    launch_vm("config.yaml")
