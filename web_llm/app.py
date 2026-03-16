import os
import json
import shutil
import git
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

# Security: Use an environment variable for the key in production
# os.environ["GEMINI_API_KEY"] = "YOUR_KEY_HERE"
client = genai.Client(api_key="AIzaSyAiz8OCCYIY78Xwlus2vupilOVGVJOt2Vk")

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    repo_url = request.json.get('url')
    if not repo_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # 1. Clean and Clone
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        git.Repo.clone_from(repo_url, TEMP_DIR)

        # 2. Extract
        meta = extract_metadata(TEMP_DIR)

        # 3. AI Generation
        prompt = f"""
        Generate an Ansible YAML playbook to set up a VM for this repo: {repo_url}
        METADATA: {json.dumps(meta.get('codemeta', 'None'))}
        FILE CLUES: {meta.get('raw_context', 'None')}

        INSTRUCTIONS:
        - Include Author/License/ORCID as comments.
        - Install all system and language dependencies.
        - Clone the repo and run install commands.
        - Return ONLY the YAML.
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash", # Updated to stable flash
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        # Clean the output
        clean_yaml = response.text.replace("```yaml", "").replace("```", "").strip()
        return jsonify({"yaml": clean_yaml})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)

if __name__ == '__main__':
    app.run(debug=True)