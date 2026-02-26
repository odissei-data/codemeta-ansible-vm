import json
import yaml
import subprocess
import os

def generate_ro_crate(codemeta_path, output_yaml):
    """Converts Codemeta to RO-Crate YAML and extracts VM specs."""
    if not os.path.exists(codemeta_path):
        print(f"❌ Error: {codemeta_path} not found.")
        return None

    with open(codemeta_path, 'r') as f:
        cm = json.load(f)

    # Map Codemeta softwareRequirements to a list for Cloud-init
    # Handles both strings and lists from Codemeta
    deps = cm.get("softwareRequirements", [])
    if isinstance(deps, str):
        deps = [deps]

    # Structure the RO-Crate YAML
    ro_crate_data = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.yaml",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"}
            },
            {
                "@id": "./",
                "@type": "Dataset",
                "name": cm.get("name", "software-vm"),
                "description": cm.get("description", "Auto-generated VM environment"),
                "author": cm.get("author", "Unknown"),
                "license": cm.get("license", "Unspecified"),
                # Store VM hardware requirements here
                "virtualization": {
                    "cpus": cm.get("runtimePlatform", {}).get("cpus", 2),
                    "memory": cm.get("runtimePlatform", {}).get("memory", "2G"),
                    "disk": cm.get("runtimePlatform", {}).get("disk", "10G"),
                    "os": cm.get("operatingSystem", "22.04")
                },
                "dependencies": deps
            }
        ]
    }

    # Write the actual RO-Crate YAML file
    with open(output_yaml, 'w') as f:
        yaml.dump(ro_crate_data, f, sort_keys=False, default_flow_style=False)
    
    print(f"✅ Generated RO-Crate file: {output_yaml}")
    return ro_crate_data

def launch_vm_with_deps(crate_data):
    """Creates a Cloud-init config and launches the Multipass VM."""
    # Extract data from the dataset node (the './' entry)
    main_node = next(n for n in crate_data["@graph"] if n["@id"] == "./")
    specs = main_node["virtualization"]
    deps = main_node["dependencies"]
    vm_name = main_node["name"].lower().replace(" ", "-")

    # Generate Cloud-init to install dependencies automatically
    cloud_init = {
        "package_update": True,
        "packages": deps
    }
    
    with open("init.yaml", "w") as f:
        yaml.dump(cloud_init, f)

    print(f"🚀 Provisioning VM '{vm_name}' with dependencies: {', '.join(deps)}...")

    cmd = [
        "multipass", "launch",
        "--name", vm_name,
        "--cpus", str(specs["cpus"]),
        "--memory", specs["memory"],
        "--disk", specs["disk"],
        "--cloud-init", "init.yaml",
        specs["os"]
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✨ Success! VM '{vm_name}' is live.")
        print(f"👉 Enter with: multipass shell {vm_name}")
    finally:
        if os.path.exists("init.yaml"):
            os.remove("init.yaml")

if __name__ == "__main__":
    # Define file paths
    SOURCE = "codemeta.json"
    TARGET = "ro-crate-metadata.yaml"

    # Execution
    crate_config = generate_ro_crate(SOURCE, TARGET)
    if crate_config:
        launch_vm_with_deps(crate_config)
