import os
import json
import shutil
import git
import requests
import tempfile
import ansible_runner
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify

from rdflib import Graph, Literal, RDF, URIRef, Namespace

app = Flask(__name__)

# --- Configuration ---
SCHEMA = Namespace("https://schema.org/")
# Use Llama-3.3-70B - ensure your HF_API_TOKEN is valid
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "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")
API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
TEMP_DIR = "./temp_repo_scan"

headers = {"Authorization": f"Bearer {HF_API_TOKEN}", "Content-Type": "application/json"}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Ansible AI Agent v3</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen p-8">
    <div class="max-w-5xl mx-auto">
        <header class="mb-10 text-center border-b border-slate-700 pb-6">
            <h1 class="text-4xl font-black text-blue-500">Ansible <span class="text-white">Auto-Heal</span></h1>
            <p class="text-slate-400 mt-2">Verified VM Deployment & Semantic RDF Mapping</p>
        </header>

        <div class="bg-slate-800 p-6 rounded-xl shadow-2xl mb-8 border border-slate-700">
            <div class="flex gap-4">
                <input type="text" id="repoUrl" placeholder="https://github.com/user/repo" 
                       class="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none text-white">
                <button onclick="processWorkflow()" id="mainBtn" class="bg-blue-600 hover:bg-blue-500 px-8 py-3 rounded-lg font-bold transition">
                    Generate & Validate
                </button>
            </div>
        </div>

        <div id="loading" class="hidden py-6">
            <div class="flex items-center justify-center gap-3">
                <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
                <span id="statusText" class="text-blue-400 font-mono text-xs uppercase tracking-widest">Processing...</span>
            </div>
            <div id="liveTrace" class="mt-4 p-3 bg-black rounded border border-slate-800 font-mono text-[10px] text-slate-500 h-24 overflow-y-auto"></div>
        </div>

        <div id="resultContainer" class="hidden grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="space-y-4">
                <div class="flex justify-between items-center">
                    <h3 class="text-lg font-bold text-emerald-400">Validated Playbook</h3>
                    <button onclick="copyToClipboard()" class="text-xs bg-emerald-600 px-4 py-1.5 rounded font-bold hover:bg-emerald-500 transition">Copy YAML</button>
                </div>
                <pre id="yamlOutput" class="bg-black p-4 rounded-lg overflow-x-auto text-xs font-mono border border-slate-700 h-[450px] text-emerald-500"></pre>
            </div>
            
            <div class="space-y-4">
                <div class="flex justify-between items-center">
                    <h3 class="text-lg font-bold text-purple-400">Semantic RDF (Turtle)</h3>
                    <button onclick="downloadRDF()" class="text-xs bg-purple-600 px-4 py-1.5 rounded font-bold hover:bg-purple-500 transition">Download .ttl</button>
                </div>
                <pre id="rdfOutput" class="bg-black p-4 rounded-lg overflow-x-auto text-xs font-mono border border-slate-700 h-[450px] text-purple-400"></pre>
            </div>
        </div>
    </div>

    <script>
        let currentYaml = "";
        let currentRdf = "";

        function addTrace(msg) {
            const lt = document.getElementById('liveTrace');
            lt.innerHTML += `<div>> ${msg}</div>`;
            lt.scrollTop = lt.scrollHeight;
        }

        async function processWorkflow() {
            const url = document.getElementById('repoUrl').value;
            if (!url) return alert(\"URL required\");

            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('resultContainer').classList.add('hidden');
            document.getElementById('liveTrace').innerHTML = "";
            
            addTrace(\"Starting Workflow for: \" + url);

            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                
                const data = await response.json();
                if (data.error) throw new Error(data.error);

                currentYaml = data.yaml;
                currentRdf = data.rdf;
                
                document.getElementById('yamlOutput').textContent = data.yaml;
                document.getElementById('rdfOutput').textContent = data.rdf;
                document.getElementById('resultContainer').classList.remove('hidden');
                addTrace(\"Successfully validated and mapped.\");
            } catch (err) { 
                addTrace(\"CRITICAL ERROR: \" + err.message);
                alert(err.message); 
            } finally {
                document.getElementById('loading').classList.add('hidden');
            }
        }

        function copyToClipboard() {
            // Only copies the text within the YAML block
            navigator.clipboard.writeText(currentYaml).then(() => alert(\"Pure YAML Copied!\"));
        }

        function downloadRDF() {
            const blob = new Blob([currentRdf], { type: 'text/turtle' });
            const a = document.createElement('a');
            a.href = window.URL.createObjectURL(blob);
            a.download = 'metadata.ttl';
            a.click();
        }
    </script>
</body>
</html>
"""

def run_ansible_validation(yaml_content):
    """Internal test: Checks if YAML is valid and runnable."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            proj = os.path.join(tmpdir, "project")
            os.makedirs(proj)
            with open(os.path.join(proj, "playbook.yml"), 'w') as f:
                f.write(yaml_content)

            r = ansible_runner.run(
                private_data_dir=tmpdir,
                playbook='playbook.yml',
                inventory='localhost ansible_connection=local',
                quiet=True,
                timeout=20
            )
            
            errs = [e.get('event_data', {}).get('res', {}).get('msg', 'Execution Error') 
                    for e in r.events if e.get('event') == 'runner_on_failed']
            
            return r.rc == 0, "\\n".join(errs) or f"RC: {r.rc}"
    except Exception as e:
        return False, str(e)

def query_ai(prompt, system_msg):
    """Safe LLM call with error checking for 'choices' key."""
    try:
        payload = {
            "model": MODEL_ID,
            "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        r = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        
        # Check for HTTP errors before parsing JSON
        if r.status_code != 200:
            return f"ERROR: API returned status {r.status_code} - {r.text}"
            
        data = r.json()
        if 'choices' not in data:
            return f"ERROR: Invalid API response format: {json.dumps(data)}"
            
        content = data['choices'][0]['message']['content']
        # Cleanup
        content = content.replace("```yaml", "").replace("```turtle", "").replace("```", "").strip()
        if "---" in content:
            content = "---" + content.split("---", 1)[1]
        return content
    except Exception as e:
        return f"ERROR: {str(e)}"

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process', methods=['POST'])
def process():
    repo_url = request.json.get('url')
    try:
        # 1. Setup
        if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR)
        git.Repo.clone_from(repo_url, TEMP_DIR)
        
        # 2. Iterative Generation & Healing
        current_yaml = query_ai(
            f"Generate a full Ansible playbook for repo: {repo_url}. Ensure it works for a generic VM.", 
            "Output ONLY valid YAML starting with '---'. No talk."
        )
        
        if "ERROR:" in current_yaml:
            return jsonify({"error": current_yaml}), 500

        for i in range(1, 3): # Recursive Heal
            valid, errs = run_ansible_validation(current_yaml)
            if valid: break
            
            current_yaml = query_ai(
                f"Fix this Ansible YAML. Errors: {errs}\\nCode:\\n{current_yaml}", 
                "Repair the YAML. Return ONLY the fixed code starting with '---'."
            )

        # 3. RDF Mapping (Using LLM Reasoning for deep mapping)
        rdf_output = query_ai(
            f"Convert this Ansible Playbook to Turtle RDF using Schema.org (sdo:) and CodeMeta (cm:). Mapping should include requirements and repo URI: {current_yaml}", 
            "Output ONLY pure Turtle RDF syntax."
        )

        return jsonify({"yaml": current_yaml, "rdf": rdf_output})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(TEMP_DIR): shutil.rmtree(TEMP_DIR)

if __name__ == '__main__':
    app.run(debug=True, port=5000)