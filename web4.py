import os
import yaml
import requests
import re
from flask import Flask, render_template_string, request, flash, Response
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import DCTERMS, XSD

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Namespaces for RDF
# Manually define the SCHEMA namespace to avoid the ImportError
SCHEMA = Namespace("https://schema.org/")
CODEMETA = Namespace("https://doi.org/10.5063/SCHEMA/CODEMETA-2.0#")

# --- EMBEDDED TEMPLATE ---
INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ODISSEI VM YAML Generator</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background: #eceff1; }
        .container { max-width: 900px; margin: auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        input[type="text"] { width: 70%; padding: 12px; border: 2px solid #cfd8dc; border-radius: 6px; font-size: 16px; }
        .btn { padding: 12px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.3s; margin-right: 5px; text-decoration: none; display: inline-block; }
        .btn-green { background: #2e7d32; color: white; }
        .btn-blue { background: #1565c0; color: white; }
        .btn-orange { background: #ef6c00; color: white; }
        pre { background: #263238; color: #ffeb3b; padding: 20px; border-radius: 8px; overflow-x: auto; margin-top: 20px; }
        .actions { margin-top: 20px; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>VM Deployment Generator</h1>
        <p>Extracts Ansible Script from <code>codemeta.json</code> and more....</p>
        <form method="POST">
            <input type="text" name="repo_url" placeholder="https://github.com/odissei-data/your-repo" required>
            <button type="submit">Process Algorithm</button>
        </form>
        {% with messages = get_flashed_messages() %}{% if messages %}<p class="error">{{ messages[0] }}</p>{% endif %}{% endwith %}
        {% if yaml_data %}
            <h3>Generated <code>deployment_vars.yml</code></h3>
            <pre>{{ yaml_data }}</pre>
            <div class="actions">
                <a href="/download/yaml?url={{ repo_url }}" class="btn btn-blue">Download .yml</a>
                <a href="/download/rdf?url={{ repo_url }}" class="btn btn-orange">Save as RDF (Turtle)</a>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

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

import json  # Make sure to add this import at the top of your script!
import math
import multiprocessing

def provision_vm(repo_url):
    print(f"\n--- Analyzing: {repo_url} ---")
    software_list, languages = parse_repo(repo_url)
    disk_size, cpu_count = get_repo_metrics(repo_url)
    ram_gb = 4 if ("java" in languages or "node" in languages) else 2
    
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    target_dir = f"/home/ubuntu/{repo_name}"

    # Prepare the data structure
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

    for sw in software_list:
        playbook[0]["tasks"].append({
            "name": f"Ensure system software is installed: {sw}",
            "package": {"name": sw, "state": "present"},
            "ignore_errors": True
        })

    playbook[0]["tasks"].append({"name": f"Clone {repo_name}", "git": {"repo": repo_url, "dest": target_dir}})

    # --- THE FIX STARTS HERE ---
    # 1. Generate the YAML as a string variable
    header = f"# Specs: CPU: {cpu_count}, RAM: {ram_gb}G, Disk: {disk_size}G\n"
    yaml_string = header + yaml.dump(playbook, sort_keys=False, default_flow_style=False)
    
    # 2. (Optional) Still save it to a file if you want
    with open("deploy.yml", "w") as f:
        f.write(yaml_string)

    # 3. Return the STRING, not the 'yaml' module
    return yaml_string

def generate_rdf(data):
    g = Graph()
    s = URIRef(data["repo_url"])
    
    g.add((s, RDF.type, SCHEMA.SoftwareSourceCode))
    g.add((s, SCHEMA.name, Literal(data["repo_name"])))
    g.add((s, SCHEMA.codeRepository, URIRef(data["repo_url"])))
    
    for sw in data["software"]:
        g.add((s, SCHEMA.softwareRequirements, Literal(sw)))
        
    # Infrastructure as Custom CodeMeta Properties
    g.add((s, CODEMETA.operatingSystem, Literal("Ubuntu 22.04")))
    g.add((s, CODEMETA.memoryRequirements, Literal(data["ram"])))
    g.add((s, CODEMETA.processorRequirements, Literal(f"{data['cpu']} Cores")))
    g.add((s, CODEMETA.storageRequirements, Literal(data["disk"])))
    
    return g.serialize(format="turtle")

# --- FLASK ROUTES ---
@app.route('/', methods=['GET', 'POST'])
def index():
    yaml_data = None
    repo_url = None # Initialize so it exists for the template
    if request.method == 'POST':
        repo_url = request.form.get('repo_url')
        yaml_data = provision_vm(repo_url)
        if not yaml_data:
            flash("The algorithm could not find valid metadata at that URL.")
            
    # Pass repo_url back to the template so the download buttons can use it
    return render_template_string(INDEX_HTML, yaml_data=yaml_data, repo_url=repo_url)

@app.route("/download/<fmt>")
def download(fmt):
    repo_url = request.args.get("url")
    if not repo_url:
        return "No URL provided", 400
        
    # Get the YAML string
    yaml_content = provision_vm(repo_url)
    
    if fmt == "yaml":
        return Response(
            yaml_content, 
            mimetype="text/yaml", 
            headers={"Content-disposition": "attachment; filename=deploy.yml"}
        )
    else:
        # For RDF, we need to re-parse the data or structure it for generate_rdf
        # Since provision_vm returns a string, we extract details for the RDF
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        software_list, _ = parse_repo(repo_url)
        disk, cpus = get_repo_metrics(repo_url)
        
        rdf_data = {
            "repo_url": repo_url,
            "repo_name": repo_name,
            "software": software_list,
            "ram": "4GB", # Matches logic in provision_vm
            "cpu": cpus,
            "disk": f"{disk}GB"
        }
        
        rdf_content = generate_rdf(rdf_data)
        return Response(
            rdf_content, 
            mimetype="text/turtle", 
            headers={"Content-disposition": "attachment; filename=metadata.ttl"}
        )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
