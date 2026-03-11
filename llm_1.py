import os
import json
import git
import shutil
from pathlib import Path
from google import genai
from google.genai import types

# Initialize the modern Client
# It will look for GEMINI_API_KEY in your environment variables
client = genai.Client(api_key="AIzaSyAEOfo6k4pntmRwJv-lQeOpjMYjVlUz11U")
#client = genai.Client()

def clone_repo(repo_url, temp_dir):
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    print(f"Cloning {repo_url}...")
    git.Repo.clone_from(repo_url, temp_dir)

def extract_metadata(repo_path):
    metadata = {}
    repo_path = Path(repo_path)
    
    # Check for codemeta.json
    codemeta_path = repo_path / "codemeta.json"
    if codemeta_path.exists():
        with open(codemeta_path, 'r') as f:
            metadata['codemeta'] = json.load(f)
    
    # Gather snippets from dependency files
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

def generate_ansible_playbook(repo_url, metadata):
    prompt = f"""
    Generate an Ansible YAML playbook to set up a VM for this repo: {repo_url}
    
    METADATA: {json.dumps(metadata.get('codemeta', 'None'))}
    FILE CLUES: {metadata.get('raw_context', 'None')}

    INSTRUCTIONS:
    - Include Author/License/ORCID as comments.
    - Install all system and language dependencies.
    - Clone the repo and run install commands.
    - Return ONLY the YAML.
    """

    # We use gemini-3-flash-preview as it's the current "Vibe Coding" workhorse
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1)
        )
    except Exception as e:
        print(f"Flash failed, trying 3.1 Pro... Error: {e}")
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt
        )
        
    return response.text

def main(repo_url):
    temp_dir = "./temp_repo_scan"
    try:
        clone_repo(repo_url, temp_dir)
        meta = extract_metadata(temp_dir)
        ansible_yaml = generate_ansible_playbook(repo_url, meta)
        
        # Clean output
        clean_yaml = ansible_yaml.replace("```yaml", "").replace("```", "").strip()
        
        with open("llm_deploy_vm.yml", "w") as f:
            f.write(clean_yaml)
        print("\nSuccessfully generated llm_deploy_vm.yml")
        
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    url = input("GitHub URL: ").strip()
    if url: main(url)