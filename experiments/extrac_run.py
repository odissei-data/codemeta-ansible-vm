import requests
import yaml
import json
import subprocess
import os
import sys
import math

def get_repo_size(repo_url):
    """Consulta a API do GitHub para obter o tamanho do repositório em GB."""
    parts = repo_url.replace(".git", "").split("/")
    owner, repo = parts[-2], parts[-1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    try:
        r = requests.get(api_url, timeout=5)
        if r.status_code == 200:
            size_kb = r.json().get("size", 0)
            size_gb = size_kb / (1024 * 1024)
            # Base de 8GB (OS) + Repo * 3 (Compilação/Deps) + 2GB margem
            recommended_disk = math.ceil(8 + (size_gb * 3) + 2)
            return max(10, recommended_disk) # Mínimo de 10GB
    except:
        pass
    return 15 # Valor padrão caso a API falhe

def fetch_raw(repo_url, filename):
    base = repo_url.replace(".git", "").replace("github.com", "raw.githubusercontent.com").rstrip("/")
    for branch in ["main", "master", "develop"]:
        try:
            r = requests.get(f"{base}/{branch}/{filename}", timeout=5)
            if r.status_code == 200: return r.text
        except: continue
    return None

def parse_repo(repo_url):
    mapping = {
        "java": ["openjdk-17-jdk", "maven"],
        "python": ["python3", "python3-pip"],
        "node": ["nodejs", "npm"],
        "javascript": ["nodejs", "npm"],
        "git": ["git"]
    }
    found_software = set()
    
    cm_text = fetch_raw(repo_url, "codemeta.json")
    if cm_text:
        try:
            data = json.loads(cm_text)
            for field in ["programmingLanguage", "softwareRequirements", "runtimePlatform"]:
                val = data.get(field, [])
                items = val if isinstance(val, list) else [val]
                for item in items:
                    name = item.get("name", str(item)) if isinstance(item, dict) else str(item)
                    name_lower = name.lower()
                    if name_lower in mapping: found_software.update(mapping[name_lower])
                    else: found_software.add(name_lower)
        except: pass

    if fetch_raw(repo_url, "pom.xml"): found_software.update(mapping["java"])
    if fetch_raw(repo_url, "package.json"): found_software.update(mapping["node"])
    if fetch_raw(repo_url, "requirements.txt"): found_software.update(mapping["python"])
        
    return sorted(list(found_software))

def provision_vm(repo_url):
    print(f"\n--- 🔍 Analisando Repositório: {repo_url} ---")
    
    # Cálculo Dinâmico de Disco
    disk_size = get_repo_size(repo_url)
    software_list = parse_repo(repo_url)
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    target_dir = f"/home/ubuntu/{repo_name}"
    
    # Atualização de Metadados
    updated_meta = {"name": repo_name, "softwareRequirements": software_list, "allocated_disk": f"{disk_size}G"}
    with open("codemeta_updated.json", "w") as f:
        json.dump(updated_meta, f, indent=4)

    # Geração do Playbook
    tasks = [
        {"name": "Atualizar APT", "apt": {"update_cache": "yes"}},
        {"name": "Clonar Repositório", "git": {"repo": repo_url, "dest": target_dir}}
    ]
    for sw in software_list:
        tasks.append({"name": f"Instalar {sw}", "package": {"name": sw, "state": "present"}, "ignore_errors": True})

    tasks.append({
        "name": "Configurar entrada na pasta",
        "lineinfile": {"path": "/home/ubuntu/.bashrc", "line": f"cd {target_dir}", "state": "present"}
    })

    with open("deploy.yml", "w") as f:
        yaml.dump([{"hosts": "localhost", "become": True, "tasks": tasks}], f, sort_keys=False)

    # Multipass
    vm_name = "build-box"
    subprocess.run(["multipass", "delete", vm_name, "--purge"], capture_output=True)

    print(f"--- 🚀 Lançando VM com Disco Dinâmico: {disk_size}G ---")
    subprocess.run(["multipass", "launch", "--name", vm_name, "--mem", "2G", "--disk", f"{disk_size}G", "22.04"], check=True)

    print("--- 🛠️  Configurando Ansible ---")
    subprocess.run(["multipass", "exec", vm_name, "--", "sudo", "apt-get", "update"], capture_output=True)
    subprocess.run(["multipass", "exec", vm_name, "--", "sudo", "apt-get", "install", "-y", "ansible"], capture_output=True)

    print("--- 📦 Executando Playbook ---")
    subprocess.run(["multipass", "transfer", "deploy.yml", f"{vm_name}:/home/ubuntu/playbook.yml"], check=True)
    subprocess.run(["multipass", "exec", vm_name, "--", "sudo", "/usr/bin/ansible-playbook", "/home/ubuntu/playbook.yml", "-c", "local"], check=True)

    # Relatório Final
    print("\n" + "="*50)
    print(f"📊 RELATÓRIO FINAL (Disco Alocado: {disk_size}G)")
    print("="*50)
    res_disk = subprocess.run(["multipass", "exec", vm_name, "--", "df", "-h", "/"], capture_output=True, text=True)
    print("Uso de Disco Atual:")
    print(res_disk.stdout.split('\n')[1])
    print("="*50)

    os.execvp("multipass", ["multipass", "shell", vm_name])

if __name__ == "__main__":
    provision_vm("https://github.com/odissei-data/ODISSEI-code-library")