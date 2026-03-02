import requests
import csv
import time
import re

BASE_URL = "https://www.f-uji.net/"
API_URL = "https://www.f-uji.net/inc_result.php"

pids = [
    "https://zenodo.org/records/17457075",
    "https://zenodo.org/records/13860149",
    "https://zenodo.org/records/18246267"
]

def evaluate_pid(session, pid):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": BASE_URL,
        "X-Requested-With": "XMLHttpRequest"
    }
    params = {"pid": pid, "service_url": "https://zenodo.org/oai2d", "service_type": "oai_pmh", "use_datacite": "true", "enable_cache": "true", "metric_id": "metrics_v0.8"}

    print(f"Scanning: {pid}...")
    try:
        session.get(BASE_URL, headers=headers, timeout=30)
        response = session.get(API_URL, params=params, headers=headers, timeout=240)
        if response.status_code == 200:
            html = response.text
            result = {"URL": pid, "Status": "Success"}
            for m in ["Findability", "Accessibility", "Interoperability", "Reusability"]:
                match = re.search(rf"{m}.*?(\d+/\d+)", html, re.DOTALL | re.IGNORECASE)
                result[m] = match.group(1) if match else "0/0"
            fsf_matches = re.findall(r"(FsF-[A-Z0-9\.-]+).*?(\d+/\d+)", html, re.DOTALL)
            for metric_id, score in fsf_matches:
                result[metric_id.strip()] = score
            return result
        return {"URL": pid, "Status": f"Error {response.status_code}"}
    except Exception as e:
        return {"URL": pid, "Status": "Exception", "Error": str(e)}

def calculate_average(results):
    valid_results = [r for r in results if r.get("Status") == "Success"]
    if not valid_results: return None
    
    avg_row = {"URL": "AVERAGE", "Status": "Calculated"}
    metrics = ["Findability", "Accessibility", "Interoperability", "Reusability"]
    
    for m in metrics:
        scores = [int(r[m].split('/')[0]) for r in valid_results]
        avg_row[m] = f"{sum(scores)/len(scores):.2f}"
    return avg_row

def save_and_print(results):
    avg = calculate_average(results)
    if avg: results.append(avg)
    
    # Save CSV
    all_keys = set().union(*(r.keys() for r in results))
    base_cols = ["URL", "Status", "Findability", "Accessibility", "Interoperability", "Reusability"]
    fsf_cols = sorted([k for k in all_keys if "FSF" in k.upper()])
    
    with open("fair_metrics_full.csv", 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=base_cols + fsf_cols, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)

    # Print LaTeX Output
    print("\n" + "="*50 + "\nLATEX COORDINATES FOR OVERLEAF\n" + "="*50)
    for r in results:
        f = r["Findability"].split('/')[0]
        a = r["Accessibility"].split('/')[0]
        i = r["Interoperability"].split('/')[0]
        re_ = r["Reusability"].split('/')[0]
        print(f"\\addplot coordinates {{(Findability, {f}) (Accessibility, {a}) (Interoperability, {i}) (Reusability, {re_})}} % {r['URL']}")

if __name__ == "__main__":
    with requests.Session() as session:
        all_data = []
        for url in pids:
            all_data.append(evaluate_pid(session, url))
            time.sleep(5)
        save_and_print(all_data)