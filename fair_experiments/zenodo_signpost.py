import requests
from rdflib import Graph

# Replace with your specific Zenodo Record ID
record_id = "18456775" # Example ID
url = f"https://zenodo.org/api/records/{record_id}"

# 1. Fetch the metadata
# We request 'application/ld+json' to get the structured JSON-LD
response = requests.get(url, headers={"Accept": "application/ld+json"})

# FIX: Changed 'status_status' to 'status_code'
if response.status_code == 200:
    # 2. Load the JSON-LD into an RDF Graph
    g = Graph()
    
    # We pass the response text and explicitly tell rdflib it is json-ld
    try:
        g.parse(data=response.text, format="json-ld")
        
        # 3. Serialize (convert) to Turtle (TTL)
        turtle_data = g.serialize(format="turtle")
        
        print(turtle_data)
        
        # Save to file
        filename = f"zenodo_{record_id}.ttl"
        with open(filename, "w") as f:
            f.write(turtle_data)
            
        print(f"\n--- Success! Saved to {filename} ---")
        
    except Exception as e:
        print(f"Error parsing JSON-LD: {e}")
else:
    print(f"Failed to fetch record. Status: {response.status_code}")
    print(f"Response: {response.text}")