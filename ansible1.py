import requests
import yaml
import re
import json

def fetch_raw(repo_url, filename):
    base = repo_url.replace(".git", "").replace("github.com", "raw.githubusercontent.com").rstrip("/")
    for branch in ["main", "master", "develop"]:
        try:
            r = requests.get(f"{base}/{branch}/{filename}", timeout=5) # Added timeout
            if r.status_code == 200: 
                return r.text
        except requests.exceptions.ConnectionError:
            print(f"Warning: DNS/Connection error while checking {filename} on {branch}.")
            return None # Exit early if we can't resolve the host
        except Exception as e:
            print(f"Skipping {filename} on {branch} due to error: {e}")
    return None

def parse_repo(repo_url):
    results = {
        "system": set(),
        "pip": False,
        "conda": False,
        "npm": False,
        "maven": False
    }

    # 1. codemeta.json
    cm = fetch_raw(repo_url, "codemeta.json")
    if cm:
        data = json.loads(cm)
        for field in ["programmingLanguage", "softwareRequirements"]:
            items = data.get(field, [])
            if not isinstance(items, list): items = [items]
            results["system"].update([str(i) for i in items])

    # 2. Check for Manifest Files & Set Flags
    if fetch_raw(repo_url, "pom.xml"):
        results["maven"] = True
        results["system"].update(["maven", "openjdk-11-jdk"])
    
    if fetch_raw(repo_url, "requirements.txt"):
        results["pip"] = True
        results["system"].add("python3-pip")

    if fetch_raw(repo_url, "package.json"):
        results["npm"] = True
        results["system"].add("nodejs")

    return results

def create_ansible(repo_url):
    deps = parse_repo(repo_url)
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    dest_path = f"/opt/{repo_name}"
    
    tasks = []

    # 1. System Prep
    tasks.append({"name": "Update apt cache", "apt": {"update_cache": "yes"}, "when": "ansible_os_family == 'Debian'"})
    tasks.append({"name": "Ensure Git is installed", "package": {"name": "git", "state": "present"}})

    # 2. Clone Repository
    tasks.append({
        "name": f"Clone {repo_name} repository",
        "git": {
            "repo": repo_url,
            "dest": dest_path,
            "clone": "yes",
            "update": "yes"
        }
    })

    # 3. Install Runtimes
    if deps["system"]:
        tasks.append({
            "name": "Install Runtimes and Tools",
            "package": {"name": list(deps["system"]), "state": "present"},
            "ignore_errors": True
        })

    # 4. Build/Install Actions
    if deps["pip"]:
        tasks.append({
            "name": "Install Python requirements",
            "pip": {"requirements": f"{dest_path}/requirements.txt"}
        })

    if deps["maven"]:
        tasks.append({
            "name": "Build Java Project with Maven",
            "command": "mvn clean install",
            "args": {"chdir": dest_path}
        })

    if deps["npm"]:
        tasks.append({
            "name": "Install NPM dependencies",
            "npm": {"path": dest_path, "state": "present"}
        })

    playbook = [{"name": f"End-to-End Deployment for {repo_name}", "hosts": "localhost", "become": True, "tasks": tasks}]
    
    with open('deploy_everything.yml', 'w') as f:
        yaml.dump(playbook, f, sort_keys=False, default_flow_style=False)
    
    print(f"Playbook 'deploy_everything.yml' generated for {repo_name}.")

#create_ansible("https://github.com/firmao/wimu") no codemeta.json
#create_ansible("https://github.com/rug-compling/Alpino")
#create_ansible("https://github.com/odissei-data/ODISSEI-code-library")
#create_ansible("https://github.com/odissei-data/odissei-kg")
if __name__ == "__main__":
    create_ansible("https://github.com/odissei-data/odissei-kg")
