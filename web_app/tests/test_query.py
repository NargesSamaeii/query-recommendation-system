"""Quick test to execute a SPARQL query and count results."""

from nl2sparql.sparql_executor import SPARQLExecutor
from nl2sparql.config import Config

# Load config
config = Config()

# Initialize executor with endpoint URL from config
endpoint_url = config.get("sparql.endpoint_url")
default_graph = config.get("sparql.default_graph")
executor = SPARQLExecutor(endpoint_url, default_graph=default_graph)

# The query to test
query = """
PREFIX prod_vocab: <http://ld.company.org/prod-vocab/>

SELECT ?supplier ?id ?addressCountry ?addressCountryCode ?addressLocality 
WHERE {
    ?supplier a prod_vocab:Supplier ;
              prod_vocab:id ?id .
    OPTIONAL { ?supplier prod_vocab:addressCountry ?addressCountry . }
    OPTIONAL { ?supplier prod_vocab:addressCountryCode ?addressCountryCode . }
    OPTIONAL { ?supplier prod_vocab:addressLocality ?addressLocality . }
}
ORDER BY ?id
"""

# Execute without limit
results = executor.execute(query, limit=None)

# Count results
if results and "results" in results and "bindings" in results["results"]:
    count = len(results["results"]["bindings"])
    print(f"\nTotal results returned: {count}")
    
    # Show first 3 and last 3 results
    bindings = results["results"]["bindings"]
    print(f"\nFirst 3 results:")
    for i, row in enumerate(bindings[:3], 1):
        supplier_id = row.get("id", {}).get("value", "N/A")
        locality = row.get("addressLocality", {}).get("value", "NULL")
        print(f"  {i}. ID: {supplier_id}, Locality: {locality}")
    
    if count > 3:
        print(f"\nLast 3 results:")
        for i, row in enumerate(bindings[-3:], count-2):
            supplier_id = row.get("id", {}).get("value", "N/A")
            locality = row.get("addressLocality", {}).get("value", "NULL")
            print(f"  {i}. ID: {supplier_id}, Locality: {locality}")
else:
    print("No results or unexpected format")
    print(results)
