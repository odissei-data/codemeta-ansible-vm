import os
import requests
from flask import Flask, render_template_string, request, jsonify
from SPARQLWrapper import SPARQLWrapper, JSON

app = Flask(__name__)

# --- CONFIGURATION ---
# Replace with your actual Hugging Face API Token (found in HF Settings -> Access Tokens)
HF_TOKEN = "YOUR_HUGFACE_API_KEY"

API_URL = "https://router.huggingface.co/v1/chat/completions"
MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

SPARQL_ENDPOINT = "https://api.kg.odissei.nl/datasets/odissei/odissei-kg-acceptance/services/odissei-kg-acceptance-virtuoso/sparql"

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ODISSEI NL to SPARQL (HuggingFace)</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { background-color: #f4f7f6; padding: 40px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container { max-width: 950px; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }
        .header-box { border-bottom: 2px solid #eee; margin-bottom: 30px; padding-bottom: 10px; }
        pre { background: #272822; color: #f8f8f2; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 0.9rem; }
        .btn-query { background-color: #1a73e8; color: white; font-weight: 600; transition: 0.3s; }
        .btn-query:hover { background-color: #1557b0; color: white; }
        .status-badge { font-size: 0.8rem; margin-top: 10px; display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-box">
            <h2 class="text-primary">ODISSEI Semantic Explorer</h2>
            <p class="text-muted">Powered by Llama-3.3 & ODISSEI Knowledge Graph</p>
        </div>
        
        <div class="mb-4">
            <label for="nlQuery" class="form-label fw-bold">Ask the Knowledge Graph:</label>
            <textarea class="form-control" id="nlQuery" rows="2" placeholder="e.g. Find all datasets that mention 'poverty' in their description"></textarea>
            <span class="status-badge text-muted" id="statusMsg">Ready</span>
        </div>
        
        <button id="submitBtn" class="btn btn-query px-4">Generate & Execute</button>

        <div id="outputSection" class="mt-5" style="display:none;">
            <h5><span class="badge bg-secondary">Generated SPARQL</span></h5>
            <pre id="sparqlCode"></pre>

            <h5 class="mt-4"><span class="badge bg-success">Results</span></h5>
            <div id="resultsArea" class="table-responsive"></div>
        </div>
    </div>

    <script>
        const submitBtn = document.getElementById('submitBtn');
        const statusMsg = document.getElementById('statusMsg');
        
        submitBtn.addEventListener('click', async () => {
            const query = document.getElementById('nlQuery').value.trim();
            const output = document.getElementById('outputSection');
            const sparqlCode = document.getElementById('sparqlCode');
            const resultsArea = document.getElementById('resultsArea');

            if (!query) return;

            submitBtn.disabled = true;
            statusMsg.innerText = "Querying Llama-3.3 and executing SPARQL...";
            output.style.display = 'none';

            try {
                const response = await fetch('/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ nl_query: query })
                });

                const data = await response.json();
                
                if (data.error) {
                    alert("Error: " + data.error);
                    statusMsg.innerText = "Error encountered.";
                } else {
                    output.style.display = 'block';
                    sparqlCode.textContent = data.sparql;
                    
                    if (data.results && data.results.length > 0) {
                        let html = '<table class="table table-hover table-bordered mt-2"><thead class="table-light"><tr>';
                        Object.keys(data.results[0]).forEach(key => html += `<th>${key}</th>`);
                        html += '</tr></thead><tbody>';
                        
                        data.results.forEach(row => {
                            html += '<tr>';
                            Object.values(row).forEach(val => {
                                let displayVal = val.value.length > 100 ? val.value.substring(0, 100) + '...' : val.value;
                                html += `<td>${displayVal}</td>`;
                            });
                            html += '</tr>';
                        });
                        html += '</tbody></table>';
                        resultsArea.innerHTML = html;
                    } else {
                        resultsArea.innerHTML = '<div class="alert alert-info">Query successful, but returned 0 results.</div>';
                    }
                    statusMsg.innerText = "Process complete.";
                }
            } catch (err) {
                console.error(err);
                statusMsg.innerText = "Critical error occurred.";
            } finally {
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""

# --- LOGIC ---

def translate_to_sparql_hf(nl_query):
    """Uses Hugging Face Router (Llama-3.3) to convert natural language to SPARQL."""
    
    # System prompt helps the model understand the specific ODISSEI context
    system_prompt = (
        "You are a SPARQL expert for the ODISSEI Knowledge Graph. "
        "Convert the user's question into a valid SPARQL query. "
        "Use the following prefixes if needed:\n"
        "PREFIX dcat: <http://www.w3.org/ns/dcat#>\n"
        "PREFIX dct: <http://purl.org/dc/terms/>\n"
        "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
        "PREFIX odissei: <https://data.kg.odissei.nl/ontology/>\n"
        "Return ONLY the raw SPARQL code. Do not include markdown code blocks (```) or any conversational text."
    )

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": nl_query}
        ],
        "max_tokens": 500,
        "temperature": 0.1  # Low temperature for precise code generation
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    
    if response.status_code != 200:
        raise Exception(f"HF API Error: {response.status_code} - {response.text}")
    
    result = response.json()
    return result['choices'][0]['message']['content'].strip()

def execute_sparql(sparql_query):
    """Executes the query against the ODISSEI Virtuoso endpoint."""
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery(sparql_query)
    sparql.setReturnFormat(JSON)
    try:
        results = sparql.query().convert()
        return results["results"]["bindings"]
    except Exception as e:
        raise Exception(f"SPARQL Execution Error: {str(e)}")

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/query', methods=['POST'])
def handle_query():
    data = request.json
    nl_query = data.get('nl_query')
    
    try:
        # 1. Translate via Llama-3.3 on HF
        generated_sparql = translate_to_sparql_hf(nl_query)
        
        # Simple cleanup in case model ignores system prompt and uses backticks
        clean_sparql = generated_sparql.replace('```sparql', '').replace('```', '').strip()
        
        # 2. Execute on ODISSEI Endpoint
        results = execute_sparql(clean_sparql)
        
        return jsonify({
            'sparql': clean_sparql,
            'results': results
        })
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Make sure you have the requests and SPARQLWrapper packages installed
    app.run(debug=True, port=5000)