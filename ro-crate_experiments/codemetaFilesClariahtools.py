import requests
import json
import time

# The official data dump URL for CLARIAH tools
DATA_URL = "https://tools.clariah.nl/data.json"

def get_repos_from_clariah_data():
    """Fetches the official data.json and extracts GitHub repositories."""
    print(f"Downloading tool metadata from {DATA_URL}...")
    try:
        # We add a header to specifically ask for JSON-LD, though data.json should be direct
        headers = {"Accept": "application/ld+json"}
        response = requests.get(DATA_URL, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

    github_repos = set()
    
    # CLARIAH data is usually in a '@graph' list
    items = data.get('@graph', [])
    if not items and isinstance(data, list):
        items = data
    
    for item in items:
        # We are looking for 'codeRepository'
        # In JSON-LD, keys might be prefixed (e.g., 'schema:codeRepository')
        repo_url = item.get('codeRepository') or item.get('schema:codeRepository')
        
        if repo_url and "github.com" in str(repo_url):
            # Clean up the URL to get 'owner/repo'
            url_str = str(repo_url).strip().rstrip('/')
            parts = url_str.split('/')
            if len(parts) >= 2:
                # Get the last two parts: owner/repo
                clean_path = f"{parts[-2]}/{parts[-1]}".replace(".git", "")
                github_repos.add(clean_path)

    return list(github_repos)

def fetch_codemeta(repo_path):
    """Fetches the codemeta.json file from GitHub."""
    # We check the most common branches
    branches = ['main', 'master', 'develop']
    
    for branch in branches:
        raw_url = f"https://raw.githubusercontent.com/{repo_path}/{branch}/codemeta.json"
        try:
            res = requests.get(raw_url, timeout=5)
            if res.status_code == 200:
                print(f"[FOUND] {repo_path}")
                return res.json()
        except:
            continue
            
    print(f"[MISSING] {repo_path}")
    return None

def main():
    repos = get_repos_from_clariah_data()
    print(f"Successfully identified {len(repos)} GitHub repositories.\n")
    
    results = {}
    
    for i, repo in enumerate(repos):
        # Progress indicator
        if i % 10 == 0 and i > 0:
            print(f"--- Processed {i}/{len(repos)} repositories ---")
            
        data = fetch_codemeta(repo)
        if data:
            results[repo] = data
        
        # Polite delay to prevent GitHub rate limiting
        time.sleep(0.3)

    # Output to file
    output_file = "clariah_codemeta_final.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)
    
    print(f"\nFinished! Extracted {len(results)} files to {output_file}.")

if __name__ == "__main__":
    main()