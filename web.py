from flask import Flask, render_template_string, request, Response
import requests
import yaml
import json
import math
import multiprocessing
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import DCTERMS, XSD

app = Flask(__name__)

# Namespaces for RDF
# Manually define the SCHEMA namespace to avoid the ImportError
SCHEMA = Namespace("https://schema.org/")
CODEMETA = Namespace("https://doi.org/10.5063/SCHEMA/CODEMETA-2.0#")

# --- CORE LOGIC ---

def get_analysis(repo_url):
    """Performs deep scan and metadata extraction."""
    repo_url = repo_url.replace(".git", "").rstrip("/")
    parts = repo_url.split("/")
    owner, repo_name = parts[-2], parts[-1]
    
    # 1. Hardware Metrics
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    disk_size, cpu_count, ram_gb = 15, 2, 2
    try:
        r = requests.get(api_url, timeout=5)
        if r.status_code == 200:
            size_gb = r.json().get("size", 0) / (1024 * 1024)
            disk_size = max(15, math.ceil(8 + (size_gb * 4) + 5))
            cpu_count = min(multiprocessing.cpu_count(), max(2, 2 + int(size_gb * 2)))
    except: pass

    # 2. Software Detection (File Scan + CodeMeta)
    mapping = {
        "java": ["openjdk-17-jdk", "maven"],
        "prolog": ["swi-prolog"],
        "python": ["python3", "python3-pip"],
        "node": ["nodejs", "npm"]
    }
    found_sw = {"git"}
    
    # Deep File Scan via GitHub Trees
    tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/main?recursive=1"
    r_tree = requests.get(tree_url, timeout=5)
    if r_tree.status_code != 200: 
        r_tree = requests.get(tree_url.replace("main", "master"), timeout=5)
    
    if r_tree.status_code == 200:
        tree = [f.get("path", "").lower() for f in r_tree.json().get("tree", [])]
        if any(f.endswith(".java") for f in tree): found_sw.update(mapping["java"])
        if any(f.endswith((".pl", ".pro")) for f in tree): found_sw.update(mapping["prolog"])
        if any("package.json" in f for f in tree): found_sw.update(mapping["node"])
        if any("requirements.txt" in f for f in tree): found_sw.update(mapping["python"])

    # RAM Adjustment
    if "maven" in found_sw or "npm" in found_sw: ram_gb = 4

    return {
        "repo_url": repo_url,
        "repo_name": repo_name,
        "software": sorted(list(found_sw)),
        "disk": f"{disk_size}GB",
        "cpu": cpu_count,
        "ram": f"{ram_gb}GB"
    }

def generate_yaml(data):
    playbook = [{
        "hosts": "localhost",
        "become": True,
        "vars": {"infra_disk": data["disk"], "infra_cpu": data["cpu"], "infra_ram": data["ram"]},
        "tasks": [{"name": f"Install {sw}", "package": {"name": sw}} for sw in data["software"]]
    }]
    playbook[0]["tasks"].append({"name": "Clone Repo", "git": {"repo": data["repo_url"], "dest": f"/home/ubuntu/{data['repo_name']}"}})
    return f"# Specs: CPU: {data['cpu']}, RAM: {data['ram']}, Disk: {data['disk']}\n" + yaml.dump(playbook, sort_keys=False)

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

# --- ROUTES ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>DevOps Metadata Generator</title>
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
        <h2>🚀 Infrastructure & Metadata Generator</h2>
        <form method="POST">
            <input type="text" name="repo_url" placeholder="Paste GitHub URL here..." value="{{ repo_url or '' }}" required>
            <button type="submit" class="btn btn-green">Analyze</button>
        </form>

        {% if yaml_content %}
        <pre>{{ yaml_content }}</pre>
        <div class="actions">
            <a href="/download/yaml?url={{ repo_url }}" class="btn btn-blue">Download .yml</a>
            <a href="/download/rdf?url={{ repo_url }}" class="btn btn-orange">Save as RDF (Turtle)</a>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    yaml_content, repo_url = None, None
    if request.method == "POST":
        repo_url = request.form.get("repo_url")
        data = get_analysis(repo_url)
        yaml_content = generate_yaml(data)
    return render_template_string(HTML_TEMPLATE, yaml_content=yaml_content, repo_url=repo_url)

@app.route("/download/<fmt>")
def download(fmt):
    repo_url = request.args.get("url")
    data = get_analysis(repo_url)
    if fmt == "yaml":
        return Response(generate_yaml(data), mimetype="text/yaml", headers={"Content-disposition": "attachment; filename=deploy.yml"})
    else:
        return Response(generate_rdf(data), mimetype="text/turtle", headers={"Content-disposition": "attachment; filename=metadata.ttl"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)