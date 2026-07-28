"""
SPARQL Executor Module

Executes SPARQL queries against endpoints.
"""

from SPARQLWrapper import SPARQLWrapper, JSON
import json
import re


class SPARQLExecutor:
    """Executes SPARQL queries against RDF endpoints."""
    
    def __init__(self, endpoint_url, timeout=30, default_graph=None):
        """
        Initialize executor with endpoint configuration.
        
        Args:
            endpoint_url: SPARQL endpoint URL
            timeout: Query timeout in seconds
            default_graph: Optional default named graph URI
        """
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        self.default_graph = default_graph
    
    def execute(self, query, limit=None):
        """
        Execute SPARQL query against the endpoint.
        
        Args:
            query: SPARQL query string
            limit: Optional result limit
            
        Returns:
            Query results as dictionary
        """
        original_query = query
        
        # Inject GRAPH clause for named graph if configured (Virtuoso-compatible)
        if self.default_graph and "FROM" not in query.upper() and "GRAPH" not in query.upper():
            # Simply wrap WHERE clause content in GRAPH pattern
            query_upper = query.upper()
            where_pos = query_upper.find("WHERE")
            
            if where_pos != -1:
                # Split at WHERE keyword
                before_where = query[:where_pos + 5]  # Include "WHERE"
                after_where = query[where_pos + 5:].lstrip()
                
                # Find the opening brace and extract content
                if after_where.startswith("{"):
                    # Extract content between braces, counting nested braces
                    brace_count = 0
                    end_pos = -1
                    for i, char in enumerate(after_where):
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i
                                break
                    
                    if end_pos != -1:
                        where_content = after_where[1:end_pos].strip()  # Content between braces
                        after_braces = after_where[end_pos+1:]  # Everything after WHERE clause
                        # Create clean GRAPH pattern without extra whitespace
                        query = f"{before_where} {{\nGRAPH <{self.default_graph}> {{\n{where_content}\n}}\n}}{after_braces}"
        
        # Add LIMIT if specified and not already in query
        # Note: LIMIT only applies to SELECT queries, not ASK/CONSTRUCT/DESCRIBE
        query_upper = query.upper()
        # Check if this is a non-SELECT query type (ASK/CONSTRUCT/DESCRIBE can't have LIMIT)
        # Match query keyword at start or after whitespace (spaces, newlines, etc.)
        import re
        is_ask_query = bool(re.search(r'(?:^|\s)ASK\s', query_upper))
        is_construct_query = bool(re.search(r'(?:^|\s)CONSTRUCT\s', query_upper))
        is_describe_query = bool(re.search(r'(?:^|\s)DESCRIBE\s', query_upper))
        
        if limit and "LIMIT" not in query.upper() and not (is_ask_query or is_construct_query or is_describe_query):
            query = f"{query}\nLIMIT {limit}"
        
        print(f"\n{'='*60}")
        print("Executing SPARQL Query:")
        print(f"{'='*60}")
        print(f"Endpoint: {self.endpoint_url}")
        if self.default_graph:
            print(f"Named Graph: {self.default_graph}")
        print(query)
        print(f"{'='*60}\n")
        
        try:
            return self._execute_once(query)
        except Exception as e:
            error_text = str(e)
            print(f"Error executing query: {e}")

            if not self._looks_like_syntax_error(error_text):
                return {"error": error_text}

            repaired_result = self._attempt_auto_repair(query, error_text)
            if repaired_result is not None:
                return repaired_result

            return {"error": error_text}

    def _execute_once(self, query):
        """Execute query once without retry/repair logic."""
        sparql = SPARQLWrapper(self.endpoint_url)
        sparql.setTimeout(self.timeout)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)

        results = sparql.query().convert()

        if not isinstance(results, dict):
            if isinstance(results, bytes):
                try:
                    error_text = results.decode('utf-8')[:800]
                    title_match = re.search(r'<title>([^<]+)</title>', error_text)
                    title = title_match.group(1) if title_match else "Unknown"
                    error_msg = f"Virtuoso returned HTML/error page instead of JSON.\nEndpoint: {self.endpoint_url}\nPage Title: {title}\n\nResponse preview:\n{error_text}"
                except Exception:
                    error_msg = f"Unexpected response type: {type(results).__name__} (likely HTML error page)\nEndpoint: {self.endpoint_url}"
            else:
                error_msg = f"Unexpected response type: {type(results).__name__}\nEndpoint: {self.endpoint_url}"
            raise RuntimeError(error_msg)

        if "boolean" in results:
            print(f"Query executed successfully. Result: {results['boolean']}\n")
            return results

        if "results" not in results or "bindings" not in results.get("results", {}):
            raise RuntimeError("Invalid SPARQL response structure")

        result_count = len(results.get("results", {}).get("bindings", []))
        print(f"Query executed successfully. Found {result_count} results.\n")
        return results

    def _looks_like_syntax_error(self, error_text):
        text = (error_text or "").lower()
        markers = [
            "querybadformed",
            "sparql compiler",
            "syntax error",
            "bad request has been sent",
            "sp03",
            "parse",
            "not mentioned in group by",
        ]
        return any(m in text for m in markers)

    def _attempt_auto_repair(self, query, error_text):
        candidates = self._generate_repair_candidates(query, error_text)
        if not candidates:
            return None

        for idx, candidate in enumerate(candidates, 1):
            if not candidate or candidate.strip() == query.strip():
                continue
            print(f"Attempting auto-repair {idx}/{len(candidates)}...")
            print(f"{'='*60}")
            print("Auto-fixed SPARQL Query:")
            print(f"{'='*60}")
            print(candidate)
            print(f"{'='*60}\n")
            try:
                result = self._execute_once(candidate)
                if isinstance(result, dict):
                    result["_auto_fixed_query"] = candidate
                return result
            except Exception as retry_error:
                print(f"Auto-repair attempt {idx} failed: {retry_error}")

        return {
            "error": str(error_text),
            "auto_repair_attempted": True,
            "auto_repair_candidates": len(candidates),
        }

    def _generate_repair_candidates(self, query, error_text):
        candidates = []

        def add_candidate(q):
            if not q:
                return
            normalized = q.strip()
            if normalized and normalized not in candidates and normalized != query.strip():
                candidates.append(normalized)

        # Highest priority: fix missing <> around PREFIX URIs first, then run other repairs
        bracket_fixed = self._fix_prefix_brackets(query)
        add_candidate(bracket_fixed)

        add_candidate(self._auto_fix_group_by_projection_error(query, error_text))

        cleaned = self._sanitize_query_for_execution(query)
        add_candidate(cleaned)
        bracket_cleaned = self._fix_prefix_brackets(cleaned)
        add_candidate(bracket_cleaned)
        add_candidate(self._ensure_common_prefixes(bracket_cleaned))
        add_candidate(self._balance_braces(bracket_cleaned))
        add_candidate(self._balance_braces(self._ensure_common_prefixes(bracket_cleaned)))

        return candidates

    def _fix_prefix_brackets(self, query):
        """Fix PREFIX declarations missing angle brackets around the URI.

        Converts:  PREFIX foo: http://example.org/
        Into:      PREFIX foo: <http://example.org/>
        """
        if not query:
            return query
        return re.sub(
            r'(PREFIX\s+[\w-]*:\s*)(https?://[^\s<>"{}|\\^`]+)',
            r'\1<\2>',
            query,
            flags=re.IGNORECASE,
        )

    def _auto_fix_group_by_projection_error(self, query, error_text):
        match = re.search(
            r'Variable\s+(\?[A-Za-z_][A-Za-z0-9_]*)\s+is used in the result set outside aggregate and not mentioned in GROUP BY clause',
            error_text or "",
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        missing_var = match.group(1)
        query_upper = query.upper()
        group_by_match = re.search(r'\bGROUP\s+BY\b', query_upper)

        if group_by_match:
            tail_match = re.search(r'\b(HAVING|ORDER\s+BY|LIMIT|OFFSET)\b', query_upper[group_by_match.end():])
            if tail_match:
                gb_start = group_by_match.start()
                gb_end = group_by_match.end() + tail_match.start()
                group_by_clause = query[gb_start:gb_end]
                if re.search(rf'(?<![\w]){re.escape(missing_var)}(?![\w])', group_by_clause):
                    return None
                new_group_by_clause = f"{group_by_clause} {missing_var}"
                return query[:gb_start] + new_group_by_clause + query[gb_end:]
            group_by_clause = query[group_by_match.start():]
            if re.search(rf'(?<![\w]){re.escape(missing_var)}(?![\w])', group_by_clause):
                return None
            return query + f" {missing_var}"

        insertion_match = re.search(r'\b(HAVING|ORDER\s+BY|LIMIT|OFFSET)\b', query_upper)
        if insertion_match:
            idx = insertion_match.start()
            return query[:idx] + f"GROUP BY {missing_var}\n" + query[idx:]

        return query + f"\nGROUP BY {missing_var}"

    def _sanitize_query_for_execution(self, query):
        if not query:
            return query

        sanitized = query
        sanitized = re.sub(r'```\s*sparql\s*', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'```', '', sanitized)

        lines = []
        for line in sanitized.split('\n'):
            if re.fullmatch(r'[=\-_*]{8,}', line.strip()):
                continue
            lines.append(line)
        sanitized = '\n'.join(lines)

        start_match = re.search(r'\b(PREFIX|BASE|SELECT|ASK|CONSTRUCT|DESCRIBE)\b', sanitized, flags=re.IGNORECASE)
        if start_match:
            sanitized = sanitized[start_match.start():]

        return sanitized.strip()

    def _ensure_common_prefixes(self, query):
        if not query:
            return query

        upper = query.upper()
        prefix_block = []

        def has_prefix(name):
            return re.search(rf'\bPREFIX\s+{name}:', upper) is not None

        if re.search(r'\brdf\s*:', query, flags=re.IGNORECASE) and not has_prefix("RDF"):
            prefix_block.append("PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>")
        if re.search(r'\brdfs\s*:', query, flags=re.IGNORECASE) and not has_prefix("RDFS"):
            prefix_block.append("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>")
        if re.search(r'\bxsd\s*:', query, flags=re.IGNORECASE) and not has_prefix("XSD"):
            prefix_block.append("PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>")

        if not prefix_block:
            return query

        return "\n".join(prefix_block) + "\n" + query

    def _balance_braces(self, query):
        if not query:
            return query

        open_count = query.count('{')
        close_count = query.count('}')
        if open_count <= close_count:
            return query

        missing = open_count - close_count
        return query.rstrip() + ("\n" + "}\n" * missing).rstrip() + "\n"
    
    def format_results(self, results, output_format="table"):
        """
        Format query results for display.
        
        Args:
            results: Query results dictionary
            output_format: Output format (table, json, csv)
            
        Returns:
            Formatted results string
        """
        if "error" in results:
            return f"Error: {results['error']}"
        
        # Handle ASK query results
        if "boolean" in results:
            return f"Result: {results['boolean']}"
        
        bindings = results.get("results", {}).get("bindings", [])
        
        if not bindings:
            return "No results found."
        
        if output_format == "json":
            return json.dumps(bindings, indent=2)
        
        elif output_format == "csv":
            if not bindings:
                return ""
            
            # Get headers
            headers = list(bindings[0].keys())
            lines = [",".join(headers)]
            
            # Add rows
            for binding in bindings:
                row = [binding.get(h, {}).get("value", "") for h in headers]
                lines.append(",".join(row))
            
            return "\n".join(lines)
        
        else:  # table format
            if not bindings:
                return "No results found."
            
            # Get headers
            headers = list(bindings[0].keys())
            
            # Calculate column widths
            col_widths = {h: len(h) for h in headers}
            for binding in bindings:
                for h in headers:
                    value = str(binding.get(h, {}).get("value", ""))
                    col_widths[h] = max(col_widths[h], len(value))
            
            # Build table
            lines = []
            
            # Header
            header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
            lines.append(header_line)
            lines.append("-" * len(header_line))
            
            # Rows
            for binding in bindings:
                row = []
                for h in headers:
                    value = str(binding.get(h, {}).get("value", ""))
                    row.append(value.ljust(col_widths[h]))
                lines.append(" | ".join(row))
            
            return "\n".join(lines)
