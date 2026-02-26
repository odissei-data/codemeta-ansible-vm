import requests
import pandas as pd

def find_values(data, github_list, orcid_list):
    """Recursively crawls JSON to find specific GitHub .git links and ORCIDs."""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                # Check for GitHub link
                if "github.com" in value:
                    # Clean the URL and ensure it ends with .git
                    clean_url = value.strip().rstrip('/')
                    if not clean_url.endswith('.git'):
                        clean_url += ".git"
                    github_list.add(clean_url)
                
                # Check for ORCID
                if "orcid.org" in value:
                    orcid_list.add(value)
            else:
                find_values(value, github_list, orcid_list)
    elif isinstance(data, list):
        for item in data:
            find_values(item, github_list, orcid_list)

def generate_git_csv_report(url, output_filename="codemeta_git_report.csv"):
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        github_repos = set()
        orcids = set()
        find_values(data, github_repos, orcids)

        if not github_repos and not orcids:
            print("No matching data found.")
            return

        # Prepare lists for the CSV
        max_len = max(len(github_repos), len(orcids))
        repo_list = list(github_repos) + [""] * (max_len - len(github_repos))
        orcid_list = list(orcids) + [""] * (max_len - len(orcids))

        df = pd.DataFrame({
            "GitHub Repository": repo_list,
            "ORCID": orcid_list
        })

        # Save to CSV
        df.to_csv(output_filename, index=False)
        print(f"File created: {output_filename}")
        print(f"Total .git repositories identified: {len(github_repos)}")
        
        return df

    except Exception as e:
        print(f"An error occurred: {e}")

# Configuration
TARGET_URL = "https://github.com/firmao/codemeta-ro-crate-vm/raw/refs/heads/main/clariah_codemeta_final.json"
generate_git_csv_report(TARGET_URL)