import os
import json
import shutil
import git
import requests
import re
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify

from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD

app = Flask(__name__)

# Namespaces
SCHEMA = Namespace("https://schema.org/")
CODEMETA = Namespace("https://doi.org/10.5063/SCHEMA/CODEMETA-2.0#")

# Configuration
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "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")
API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
TEMP_DIR = "./temp_repo_scan"

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>DevOps Metadata Generator</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background-color: #f4f7f6; }
        .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #333; margin-top: 0; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        input[type="text"] { flex-grow: 1; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 16px; }
        button { padding: 12px 24px; cursor: pointer; border-radius: 6px; border: none; background: #2563eb; color: white; font-weight: bold; transition: background 0.2s; }
        button:hover { background: #1d4ed8; }
        button:disabled { background: #94a3b8; cursor: not-allowed; }
        #downloadBtn { background: #059669; margin-top: 15px; display: none; }
        #downloadBtn:hover { background: #047857; }
        pre { background: #1e293b; color: #f8fafc; padding: 20px; border-radius: 8px; overflow-x: auto; font-size: 14px; line-height: 1.5; border: 1px solid #334155; }
        .status-msg { margin: 10px 0; font-size: 14px; min-height: 20px; }
        .error { color: #dc2626; }
        .success { color: #059669; }
    </style>
</head>
<body>
    <div class="container">
        <h2>DevOps Repository Scanner</h2>
        <div class="input-group">
            <input type="text" id="repoUrl" placeholder="https://github.com/username/repository">
            <button id="genBtn" onclick="generate()">Generate Ansible</button>
        </div>
        
        <div id="status" class="status-msg"></div>
        
        <div id="outputContainer" style="display:none;">
            <h3>Ansible Playbook Preview:</h3>
            <pre id="yamlOutput"></pre>
            <button id="downloadBtn" onclick="downloadRDF()">Download Enhanced RDF (.ttl)</button>
        </div>
    </div>

    <script>
        let lastResponse = {};

        async function generate() {
            const url = document.getElementById('repoUrl').value;
            const btn = document.getElementById('genBtn');
            const status = document.getElementById('status');
            const outputCont = document.getElementById('outputContainer');
            const yamlText = document.getElementById('yamlOutput');
            const dlBtn = document.getElementById('downloadBtn');

            if (!url) return alert("Please enter a GitHub URL");

            btn.disabled = true;
            status.className = "status-msg";
            status.innerText = "⚡ Cloning, scanning, and analyzing with LLM...";
            outputCont.style.display = 'none';

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();

                if (data.error) throw new Error(data.error);

                lastResponse = data; // Store yaml, meta, and url
                yamlText.innerText = data.yaml;
                outputCont.style.display = 'block';
                dlBtn.style.display = 'inline-block';
                status.className = "status-msg success";
                status.innerText = "✓ Analysis complete!";
            } catch (e) {
                status.className = "status-msg error";
                status.innerText = "✗ Error: " + e.message;
            } finally {
                btn.disabled = false;
            }
        }

        async function downloadRDF() {
            try {
                const response = await fetch('/convert-rdf', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        url: lastResponse.url, 
                        meta: lastResponse.meta, 
                        yaml: lastResponse.yaml 
                    })
                });
                const data = await response.json();

                const blob = new Blob([data.rdf], { type: 'text/turtle' });
                const blobUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = "repo-ansible-metadata.ttl";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(blobUrl);
            } catch (e) {
                alert("Download failed: " + e.message);
            }
        }
    </script>
</body>
</html>
"""

def extract_metadata(repo_path):
    metadata = {}
    repo_path = Path(repo_path)
    codemeta_path = repo_path / "codemeta.json"
    if codemeta_path.exists():
        with open(codemeta_path, 'r') as f:
            metadata['codemeta'] = json.load(f)
    
    context = ""
    for f_name in ["requirements.txt", "setup.py", "package.json", "README.md"]:
        target = repo_path / f_name
        if target.exists():
            context += f"\n-- {f_name} --\n{target.read_text(errors='ignore')[:800]}\n"
    metadata['raw_context'] = context
    return metadata

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/generate', methods=['POST'])
def generate():
    repo_url = request.json.get('url')
    try:
        if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR, ignore_errors=True)
        git.Repo.clone_from(repo_url, TEMP_DIR, depth=1)
        meta = extract_metadata(TEMP_DIR)

        prompt = f"Generate a full Ansible YAML playbook for this repo: {repo_url}. Context clues: {meta['raw_context']}. Return ONLY the YAML."
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}", "Content-Type": "application/json"}
        payload = {"model": MODEL_ID, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1}
        
        response = requests.post(API_URL, headers=headers, json=payload)
        gen_text = response.json()['choices'][0]['message']['content']
        clean_yaml = gen_text.replace("```yaml", "").replace("```", "").strip()
        
        return jsonify({"yaml": clean_yaml, "meta": meta, "url": repo_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR, ignore_errors=True)

@app.route('/convert-rdf', methods=['POST'])
def convert_rdf():
    data = request.json
    repo_url = data.get('url')
    meta = data.get('meta', {})
    yaml_content = data.get('yaml', "")

    g = Graph()
    g.bind("schema", SCHEMA)
    g.bind("codemeta", CODEMETA)
    
    software = URIRef(repo_url)
    g.add((software, RDF.type, SCHEMA.SoftwareSourceCode))
    g.add((software, SCHEMA.codeRepository, URIRef(repo_url)))
    
    # 1. Map basic Codemeta info
    cm = meta.get('codemeta', {})
    if isinstance(cm, dict):
        g.add((software, SCHEMA.name, Literal(cm.get('name', 'Repository'))))
        if 'version' in cm: g.add((software, SCHEMA.softwareVersion, Literal(cm['version'])))

    # 2. Extract info from Ansible YAML via regex
    # Find package names (e.g., name: nginx, pkg: python3)
    packages = re.findall(r"(?:name|pkg|package):\s*['\"]?([\w\-\d]+)['\"]?", yaml_content)
    for pkg in set(packages):
        if pkg.lower() not in ['true', 'false', 'yes', 'no', 'present', 'latest']:
            g.add((software, SCHEMA.softwareRequirements, Literal(f"OS Package: {pkg}")))

    # Find ports
    ports = re.findall(r"port:\s*(\d+)", yaml_content)
    for port in set(ports):
        g.add((software, SCHEMA.runtimePlatform, Literal(f"Network Port: {port}")))

    # Store the full Ansible script as a text property
    g.add((software, SCHEMA.description, Literal("Auto-generated Ansible deployment script included in graph.")))
    g.add((software, CODEMETA.contIntegration, Literal(yaml_content)))

    rdf_output = g.serialize(format="turtle")
    if isinstance(rdf_output, bytes): rdf_output = rdf_output.decode("utf-8")

    return jsonify({"rdf": rdf_output})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
