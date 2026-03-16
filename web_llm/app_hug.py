import os
import json
import shutil
import git
import requests
from pathlib import Path
from flask import Flask, render_template, request, jsonify

from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import DCTERMS, XSD

app = Flask(__name__)

# Namespaces for RDF
# Manually define the SCHEMA namespace to avoid the ImportError
SCHEMA = Namespace("https://schema.org/")
CODEMETA = Namespace("https://doi.org/10.5063/SCHEMA/CODEMETA-2.0#")

# Security: Ensure your token is active at huggingface.co/settings/tokens
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "YOR_HUGFACE_API_KEY")

# The unified 2026 Router endpoint
API_URL = "https://router.huggingface.co/v1/chat/completions"

# Use Llama-3.3, as it is currently the most widely supported free model on the router
MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

headers = {
    "Authorization": f"Bearer {HF_API_TOKEN}",
    "Content-Type": "application/json"
}

TEMP_DIR = "./temp_repo_scan"

def extract_metadata(repo_path):
    metadata = {}
    repo_path = Path(repo_path)
    
    codemeta_path = repo_path / "codemeta.json"
    if codemeta_path.exists():
        with open(codemeta_path, 'r') as f:
            metadata['codemeta'] = json.load(f)
    
    discovery_files = ["requirements.txt", "setup.py", "pyproject.toml", "package.json", "README.md"]
    extra_context = ""
    for file_name in discovery_files:
        target = repo_path / file_name
        if target.exists():
            try:
                content = target.read_text(errors='ignore')[:1500]
                extra_context += f"\n--- {file_name} ---\n{content}\n"
            except: continue
                
    metadata['raw_context'] = extra_context
    return metadata

def query_llm(prompt):
    """Queries the router. If Llama-3.3 is busy, it defaults to the next available provider."""
    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": "You are a DevOps automation expert. Output only valid Ansible YAML code."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 2048
    }
    
    response = requests.post(API_URL, headers=headers, json=payload)
    
    if response.status_code != 200:
        # Diagnostic: If the model isn't found, try a different one
        raise Exception(f"Router Error ({response.status_code}): {response.text}")
        
    result = response.json()
    return result['choices'][0]['message']['content']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    repo_url = request.json.get('url')
    if not repo_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        git.Repo.clone_from(repo_url, TEMP_DIR)

        meta = extract_metadata(TEMP_DIR)

        prompt = f"""
        Generate an Ansible YAML playbook to set up a VM for this repo: {repo_url}
        METADATA: {json.dumps(meta.get('codemeta', 'None'))}
        FILE CLUES: {meta.get('raw_context', 'None')}

        INSTRUCTIONS:
        - Return ONLY the YAML. 
        - Do not include '```yaml' or other markdown.
        """

        generated_text = query_llm(prompt)
        
        # Fallback cleaning in case the LLM ignores instructions
        clean_yaml = generated_text.replace("```yaml", "").replace("```", "").strip()
        return jsonify({"yaml": clean_yaml})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)

@app.route('/convert-rdf', methods=['POST'])
def convert_rdf():
    data = request.json
    repo_url = data.get('url', 'http://example.org/repo')
    meta = data.get('meta', {})

    # Initialize RDF Graph
    g = Graph()
    g.bind("schema", SDO)
    g.bind("codemeta", CODEMETA)

    # Create the Software Resource
    software = URIRef(repo_url)
    g.add((software, RDF.type, SDO.SoftwareSourceCode))
    g.add((software, SDO.codeRepository, URIRef(repo_url)))
    
    # Map Metadata from CodeMeta JSON
    cm_data = meta.get('codemeta', {})
    if isinstance(cm_data, dict):
        g.add((software, SDO.name, Literal(cm_data.get('name', 'Unnamed Repository'))))
        if 'license' in cm_data:
            g.add((software, SDO.license, URIRef(cm_data['license'])))
        if 'version' in cm_data:
            g.add((software, SDO.softwareVersion, Literal(cm_data['version'])))

    # Serialize to Turtle format
    rdf_output = g.serialize(format="turtle")
    return jsonify({"rdf": rdf_output})

if __name__ == '__main__':
    app.run(debug=True)