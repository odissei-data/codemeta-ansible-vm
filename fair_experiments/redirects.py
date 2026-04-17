import pandas as pd
import requests

# Configuration
INPUT_FILE = 'experiments - Sheet4.csv'  # Ensure your file name matches this
OUTPUT_REPORT = 'redirect_report.csv'
REQUIRED_PREFIX = 'https://dataverse.nl/dataset'

def get_final_destination(url):
    """Follows redirects and returns the final landing page URL."""
    try:
        # Browser-like headers often help avoid being blocked by servers
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # allow_redirects=True follows the chain to the final destination
        response = requests.get(url, allow_redirects=True, timeout=20, headers=headers)
        return response.url, None
    except Exception as e:
        return None, str(e)

def main():
    try:
        # Load the CSV (Assuming no header row based on file inspection)
        df = pd.read_csv(INPUT_FILE, header=None)
    except FileNotFoundError:
        print(f"Error: The file '{INPUT_FILE}' was not found.")
        return

    report_data = []

    print(f"Processing {len(df)} rows. This may take a moment...")

    for index, row in df.iterrows():
        # Clean URLs: handle cases with extra quotes or newlines
        url1 = str(row[0]).strip().strip('"').strip()
        url2 = str(row[1]).strip().strip('"').strip()
        
        print(f"Checking row {index + 1}...")

        final1, err1 = get_final_destination(url1)
        final2, err2 = get_final_destination(url2)

        # Validation Logic
        valid_prefix1 = final1.startswith(REQUIRED_PREFIX) if final1 else False
        valid_prefix2 = final2.startswith(REQUIRED_PREFIX) if final2 else False
        match = (final1 == final2) if (final1 and final2) else False

        # Determine overall status
        if err1 or err2:
            status = "Connection Error"
        elif not match:
            status = "Mismatch"
        elif not valid_prefix1 or not valid_prefix2:
            status = "Invalid Destination Prefix"
        else:
            status = "Correct"

        report_data.append({
            "Row": index + 1,
            "Source URL 1": url1,
            "Source URL 2": url2,
            "Final Landing 1": final1,
            "Final Landing 2": final2,
            "Error Log": f"URL1: {err1} | URL2: {err2}" if (err1 or err2) else "None",
            "Redirects to Same Place": match,
            "Valid Dataverse Prefix (URL 1)": valid_prefix1,
            "Valid Dataverse Prefix (URL 2)": valid_prefix2,
            "Result": status
        })

    # Create and export the report
    report_df = pd.DataFrame(report_data)
    report_df.to_csv(OUTPUT_REPORT, index=False)
    
    # Print summary of issues to terminal
    issues = report_df[report_df['Result'] != "Correct"]
    if not issues.empty:
        print("\n--- ISSUES FOUND ---")
        print(issues[['Row', 'Result', 'Final Landing 1', 'Final Landing 2']])
    else:
        print("\nSuccess: All URLs redirect correctly to Dataverse!")

    print(f"\nDetailed report saved to: {OUTPUT_REPORT}")

if __name__ == "__main__":
    main()