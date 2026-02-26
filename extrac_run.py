import requests
import yaml
import json
import subprocess
import os
import math
import multiprocessing
import webbrowser

def get_repo_metrics(repo_url):
    parts = repo_url.replace(".git", "").split("/")
    owner, repo = parts[-2], parts[-1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        r = requests.get(api_url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            size_gb = data.get("size", 0) / (1024 * 1024)
            disk = math.ceil(8 + (size_gb * 4) + 5)
            host_cpus = multiprocessing.cpu_count()
            cpus = min(host_cpus, max(2, 2 + int(size_gb * 2)))
            return max(15, disk), cpus
    except: pass
    return 20, 2

def fetch_raw(repo_url, filename):
    base = repo_url.replace(".git", "").replace("github.com", "raw.githubusercontent.com").rstrip("/")
    for branch in ["main", "master", "develop"]:
        try:
            r = requests.get(f"{base}/{branch}/{filename}", timeout=5)
            if r.status_code == 200: return r.text
        except: continue
    return None

def scan_repo_files(repo_url):
    """Deep scan for file extensions (Java, Prolog, etc.)"""
    parts = repo_url.replace(".git", "").split("/")
    owner, repo = parts[-2], parts[-1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
    detected = set()
    try:
        r = requests.get(api_url, timeout=5)
        if r.status_code != 200:
            r = requests.get(api_url.replace("main", "master"), timeout=5)
        if r.status_code == 200:
            tree = r.json().get("tree", [])
            for file in tree:
                path = file.get("path", "").lower()
                if path.endswith(".java"): detected.add("java")
                if path.endswith(".pl") or path.endswith(".pro"): detected.add("prolog")
                if "pom.xml" in path: detected.add("java")
                if "package.json" in path: detected.add("node")
    except: pass
    return detected

def parse_repo(repo_url):
    mapping = {
        "java": ["openjdk-17-jdk", "maven", "default-jre"],
        "prolog": ["swi-prolog", "swi-prolog-nox"],
        "python": ["python3", "python3-pip"],
        "node": ["nodejs", "npm"],
        "javascript": ["nodejs", "npm"],
        "git": ["git"]
    }
    
    found_software = set()
    
    # 1. Scrape CodeMeta.json (The explicit request)
    cm_text = fetch_raw(repo_url, "codemeta.json")
    if cm_text:
        try:
            data = json.loads(cm_text)
            for field in ["programmingLanguage", "softwareRequirements", "runtimePlatform"]:
                val = data.get(field, [])
                items = val if isinstance(val, list) else [val]
                for item in items:
                    name = item.get("name", str(item)) if isinstance(item, dict) else str(item)
                    name_clean = name.lower()
                    if name_clean in mapping:
                        found_software.update(mapping[name_clean])
                    else:
                        found_software.add(name_clean)
        except: pass

    # 2. Deep File Scan (The fallback/safety net)
    languages = scan_repo_files(repo_url)
    for lang in languages:
        if lang in mapping:
            found_software.update(mapping[lang])

    return sorted(list(found_software)), languages

def provision_vm(repo_url):
    print(f"\n--- Analyzing: {repo_url} ---")
    software_list, languages = parse_repo(repo_url)
    disk_size, cpu_count = get_repo_metrics(repo_url)
    ram_gb = 4 if ("java" in languages or "node" in languages) else 2
    
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    target_dir = f"/home/ubuntu/{repo_name}"

    # Prepare deploy.yml
    playbook = [{
        "hosts": "localhost",
        "become": True,
        "vars": {
            "infra_disk": f"{disk_size}GB",
            "infra_mem": f"{ram_gb}GB",
            "infra_cpu": cpu_count
        },
        "tasks": [
            {"name": "Update system cache", "apt": {"update_cache": "yes"}},
            {"name": "Install git", "package": {"name": "git", "state": "present"}}
        ]
    }]

    # Add every detected software as an explicit English task
    for sw in software_list:
        playbook[0]["tasks"].append({
            "name": f"Ensure system software is installed: {sw}",
            "package": {"name": sw, "state": "present"},
            "ignore_errors": True
        })

    playbook[0]["tasks"].append({"name": f"Clone {repo_name}", "git": {"repo": repo_url, "dest": target_dir}})

    with open("deploy.yml", "w") as f:
        f.write(f"# Specs: CPU: {cpu_count}, RAM: {ram_gb}G, Disk: {disk_size}G\n")
        yaml.dump(playbook, f, sort_keys=False)

    # VM Orchestration
    vm_name = "build-box"
    subprocess.run(["multipass", "delete", vm_name, "--purge"], capture_output=True)
    print(f"--- Launching VM ({cpu_count} CPUs, {ram_gb}G RAM, {disk_size}G Disk) ---")
    subprocess.run(["multipass", "launch", "--name", vm_name, "--cpus", str(cpu_count), "--mem", f"{ram_gb}G", "--disk", f"{disk_size}G", "22.04"], check=True)

    # Provisioning
    subprocess.run(["multipass", "exec", vm_name, "--", "sudo", "apt-get", "update"], capture_output=True)
    subprocess.run(["multipass", "exec", vm_name, "--", "sudo", "apt-get", "install", "-y", "ansible"], capture_output=True)
    subprocess.run(["multipass", "transfer", "deploy.yml", f"{vm_name}:/home/ubuntu/playbook.yml"], check=True)
    subprocess.run(["multipass", "exec", vm_name, "--", "sudo", "/usr/bin/ansible-playbook", "/home/ubuntu/playbook.yml", "-c", "local"], check=True)

    print(f"\n✅ Ready. Dropping into shell...")
    os.execvp("multipass", ["multipass", "shell", vm_name])

if __name__ == "__main__":
    provision_vm("https://github.com/odissei-data/odissei-kg")