"""
TOON Formatter for Schemas

Converts JSON schemas to/from a compact, human-readable schema table layout
optimized for prompts.

The emitted format uses a simple schema block:

Cardinality key:  1 = exactly one  |  0-1 = at most one  |  1+ = at least one  |  0+ = multiple allowed

--- prod_vocab:Hardware ---
| Property IRI | Label | Range | Card |
| prod_vocab:name | name | xsd:string | 0-1 |
Instances: prod_inst:hw-A509-5571891 (A509-5571891 - Multiplexer Inductor)

The parser remains backward compatible with the older YAML-like TOON layout.
"""

import json
import re
import yaml
from typing import Any, Dict, List


class TOONFormatter:
    """Convert between JSON and TOON formats optimized for schema data."""
    
    @staticmethod
    def encode(
        data: Dict[str, Any],
        include_examples: bool = True,
        include_descriptions: bool = True,
        max_examples: int = 2,
    ) -> str:
        """
        Encode a JSON object to TOON format.
        
        Args:
            data: Dictionary to encode
            include_examples: Whether to include example values (default: True)
            include_descriptions: Whether to include property descriptions (default: True)
            max_examples: Maximum number of examples to include per class/property (default: 2)
            
        Returns:
            TOON-formatted string
        """
        schema = TOONFormatter._normalize_schema_root(data)
        lines: List[str] = [
            "Cardinality key:  1 = exactly one  |  0-1 = at most one  |  1+ = at least one  |  0+ = multiple allowed",
        ]

        prefixes = schema.get("prefixes", {}) or {}
        classes = schema.get("classes", {}) or {}

        if prefixes:
            lines.append("")
            lines.append("Prefixes:")
            for prefix, uri in prefixes.items():
                lines.append(f"PREFIX {prefix}: <{uri}>")

        if classes:
            for class_name, class_data in classes.items():
                lines.extend(
                    TOONFormatter._format_class_block(
                        class_name,
                        class_data,
                        prefixes,
                        include_examples,
                        include_descriptions,
                        max_examples,
                    )
                )
        else:
            lines.append("")
            lines.append("--- No classes ---")

        return "\n".join(lines).rstrip()
    
    @staticmethod
    def _encode_uniform_array(key: str, items: List[Dict]) -> str:
        """Encode a uniform array of dicts as TOON tabular format."""
        if not items:
            return f"{key}[0]:"
        
        # Get field names from first item and check if all items have same structure
        field_names = list(items[0].keys())
        
        # Verify all items have same keys (uniform)
        for item in items[1:]:
            if set(item.keys()) != set(field_names):
                return ""  # Non-uniform, cannot encode as tabular
        
        # Encode header: key[count]{fields}:
        header = f"{key}[{len(items)}]{{{','.join(field_names)}}}:"
        
        # Encode rows
        rows = []
        for item in items:
            # Extract values in field order, quote if needed
            values = []
            for field in field_names:
                val = item.get(field, "")
                if isinstance(val, bool):
                    values.append("true" if val else "false")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                elif val is None:
                    values.append("")
                elif isinstance(val, str):
                    # For CSV-like format, quote strings that contain commas or quotes
                    if "," in val or '"' in val or "\n" in val:
                        values.append('"' + val.replace('"', '""') + '"')
                    else:
                        values.append(val)
                else:
                    # Complex type, use JSON
                    values.append(json.dumps(val))
            rows.append(",".join(values))
        
        # Combine header and rows with indentation
        return header + "\n  " + "\n  ".join(rows)

    @staticmethod
    def _encode_value(lines: List[str], key: str, value: Any, indent: int = 0) -> None:
        """Recursively encode a value in a readable YAML-like TOON layout."""
        pad = "  " * indent
        key_text = TOONFormatter._format_key(key)
        if isinstance(value, dict):
            lines.append(f"{pad}{key_text}:")
            for subkey, subvalue in value.items():
                TOONFormatter._encode_value(lines, subkey, subvalue, indent + 1)
            return

        if isinstance(value, list):
            if not value:
                lines.append(f"{pad}{key_text}: []")
                return

            lines.append(f"{pad}{key_text}:")
            for item in value:
                if isinstance(item, dict):
                    # Emit each item as a nested block for readability.
                    first = True
                    for subkey, subvalue in item.items():
                        if first:
                            if isinstance(subvalue, (dict, list)):
                                lines.append(f"{pad}  - {TOONFormatter._format_key(subkey)}:")
                                TOONFormatter._encode_nested_value(lines, subvalue, indent + 3)
                            else:
                                lines.append(f"{pad}  - {TOONFormatter._format_key(subkey)}: {TOONFormatter._format_scalar(subvalue)}")
                            first = False
                        else:
                            TOONFormatter._encode_value(lines, subkey, subvalue, indent + 2)
                else:
                    lines.append(f"{pad}  - {TOONFormatter._format_scalar(item)}")
            return

        lines.append(f"{pad}{key_text}: {TOONFormatter._format_scalar(value)}")

    @staticmethod
    def _encode_nested_value(lines: List[str], value: Any, indent: int) -> None:
        """Encode nested dict/list values after a list item header."""
        pad = "  " * indent
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                TOONFormatter._encode_value(lines, subkey, subvalue, indent)
        elif isinstance(value, list):
            if not value:
                lines.append(f"{pad}[]")
            else:
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{pad}-")
                        for subkey, subvalue in item.items():
                            TOONFormatter._encode_value(lines, subkey, subvalue, indent + 1)
                    else:
                        lines.append(f"{pad}- {TOONFormatter._format_scalar(item)}")
        else:
            lines.append(f"{pad}{TOONFormatter._format_scalar(value)}")
    
    @staticmethod
    def decode(toon_str: str) -> Dict[str, Any]:
        """
        Decode a TOON-formatted string back to JSON.
        
        Args:
            toon_str: TOON-formatted string
            
        Returns:
            Dictionary decoded from TOON
        """
        lines = toon_str.strip().split("\n")

        structured = TOONFormatter._parse_structured_schema(lines)
        if structured is not None:
            return structured

        try:
            loaded = yaml.safe_load(toon_str)
            if isinstance(loaded, dict):
                if "schema" in loaded and isinstance(loaded.get("schema"), dict):
                    return loaded["schema"]
                return loaded
        except Exception:
            pass

        result = {}
        i = 0
        
        while i < len(lines):
            line = lines[i].rstrip()
            
            # Skip empty lines
            if not line.strip():
                i += 1
                continue
            
            # Check for tabular array: key[N]{fields}:
            match_tabular = TOONFormatter._parse_tabular_header(line)
            if match_tabular:
                key, field_names = match_tabular
                i += 1
                rows_data = []
                
                # Collect rows (indented lines following the header)
                while i < len(lines):
                    row_line = lines[i]
                    if not row_line.startswith("  "):
                        break
                    row_str = row_line.strip()
                    if row_str:
                        # Parse CSV-style row
                        row_dict = TOONFormatter._parse_csv_row(row_str, field_names)
                        rows_data.append(row_dict)
                    i += 1
                
                result[key] = rows_data
                continue
            
            # Check for simple array: key[N]: item1,item2,...
            match_simple_array = TOONFormatter._parse_simple_array_header(line)
            if match_simple_array:
                key, items = match_simple_array
                result[key] = items
                i += 1
                continue
            
            # Check for nested object: key:
            if line.endswith(":") and "[" not in line and "{" not in line:
                key = line[:-1].strip()
                i += 1
                obj = {}
                
                # Collect indented key-value pairs (including prefixed IRIs like owl:AnnotationProperty)
                while i < len(lines):
                    obj_line = lines[i]
                    if not obj_line.startswith("  ") or obj_line.startswith("   "):
                        break
                    if ":" in obj_line:
                        kv = obj_line.strip()
                        
                        # For classes dict, keys are prefixed IRIs (e.g., "owl:AnnotationProperty")
                        # The value is typically JSON starting with { 
                        # Find where the JSON value starts
                        json_start = kv.find(" {")
                        if json_start > 0:
                            # Key is everything before the JSON (strip trailing colon if present)
                            k = kv[:json_start].strip()
                            if k.endswith(":"):
                                k = k[:-1].strip()
                            v = kv[json_start:].strip()
                        else:
                            # Fallback: split on first colon
                            k, v = kv.split(":", 1)
                            k = k.strip()
                            v = v.strip()
                        
                        # Try to parse value
                        try:
                            if v.startswith("[") or v.startswith("{"):
                                obj[k] = json.loads(v)
                            elif v.lower() in ("true", "false"):
                                obj[k] = v.lower() == "true"
                            elif v.isdigit():
                                obj[k] = int(v)
                            else:
                                obj[k] = TOONFormatter._unquote(v)
                        except Exception:
                            obj[k] = TOONFormatter._unquote(v)
                    i += 1
                
                result[key] = obj
                continue
            
            # Scalar key-value: key: value
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                
                # Try to parse value
                try:
                    if v.startswith("[") or v.startswith("{"):
                        result[k] = json.loads(v)
                    elif v.lower() in ("true", "false"):
                        result[k] = v.lower() == "true"
                    elif v.isdigit():
                        result[k] = int(v)
                    else:
                        result[k] = TOONFormatter._unquote(v)
                except Exception:
                    result[k] = TOONFormatter._unquote(v)
            
            i += 1
        
        return result

    @staticmethod
    def _parse_structured_schema(lines: List[str]) -> Dict[str, Any] | None:
        """Parse the structured schema layout produced by encode()."""
        if not lines:
            return None

        non_empty = [line.rstrip("\n") for line in lines if line.strip()]
        if not non_empty:
            return None

        # Support the older YAML-like schema layout as well as the new
        # human-readable class table layout.
        if non_empty[0].strip() == "schema:":
            return TOONFormatter._parse_legacy_structured_schema(lines)

        if not any(line.strip().startswith("--- ") and line.strip().endswith(" ---") for line in non_empty):
            return None

        result: Dict[str, Any] = {"prefixes": {}, "classes": {}}
        i = 0
        current_class_name: str | None = None
        current_class_data: Dict[str, Any] | None = None

        def finalize_current_class() -> None:
            nonlocal current_class_name, current_class_data
            if current_class_name is not None and current_class_data is not None:
                result["classes"][current_class_name] = current_class_data
            current_class_name = None
            current_class_data = None

        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            if stripped.startswith("PREFIX "):
                prefix_match = re.match(r"^PREFIX\s+([A-Za-z_][A-Za-z0-9_-]*):\s*<([^>]+)>\s*$", stripped)
                if prefix_match:
                    result["prefixes"][prefix_match.group(1)] = prefix_match.group(2)
                i += 1
                continue

            if stripped.startswith("Cardinality key:"):
                i += 1
                continue

            class_match = re.match(r"^---\s+(.+?)\s+---$", stripped)
            if class_match:
                finalize_current_class()
                current_class_name = class_match.group(1).strip()
                current_class_data = {
                    "class_label": TOONFormatter._local_name(current_class_name),
                    "class_examples": [],
                    "properties": [],
                }
                i += 1
                continue

            if current_class_data is None:
                i += 1
                continue

            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                # Header row: property table titles.
                if len(cells) >= 4 and cells[0].lower() == "property iri":
                    i += 1
                    continue
                if len(cells) >= 4:
                    prop_name, prop_label, range_text, card_text = cells[:4]
                    prop: Dict[str, Any] = {
                        "property_name": prop_name,
                        "property_label": prop_label,
                    }
                    card = card_text.strip()
                    if card == "1":
                        prop["min_count"] = 1
                        prop["max_count"] = 1
                    elif card in {"+", "1+"}:
                        prop["min_count"] = 1
                        prop["max_count"] = None
                    elif card in {"?", "0-1"}:
                        prop["min_count"] = 0
                        prop["max_count"] = 1
                    elif card in {"*", "0+"}:
                        prop["min_count"] = 0
                        prop["max_count"] = None
                    if range_text in {"str", "string", "xsd:string"}:
                        prop["datatype"] = ["xsd:string"]
                        prop["node_kind"] = "http://www.w3.org/ns/shacl#Literal"
                    elif range_text == "IRI":
                        prop["node_kind"] = "http://www.w3.org/ns/shacl#IRI"
                    elif range_text:
                        prop["or_classes"] = [range_text]
                        prop["node_kind"] = "http://www.w3.org/ns/shacl#IRI"
                    current_class_data["properties"].append(prop)
                i += 1
                continue

            if stripped.startswith("Instances:"):
                instances_text = stripped.split(":", 1)[1].strip()
                current_class_data["class_examples"].extend(TOONFormatter._parse_example_list(instances_text))
                i += 1
                continue

            i += 1

        finalize_current_class()
        return result

    @staticmethod
    def _parse_legacy_structured_schema(lines: List[str]) -> Dict[str, Any] | None:
        """Parse the older YAML-like schema layout produced by previous encode()."""
        result: Dict[str, Any] = {"prefixes": {}, "classes": {}}
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            if stripped == "schema:":
                i += 1
                continue

            if stripped == "prefixes:" and line.startswith("  "):
                i += 1
                while i < len(lines):
                    prefix_line = lines[i].rstrip()
                    if not prefix_line.startswith("    ") or prefix_line.startswith("      "):
                        break
                    prefix_stripped = prefix_line.strip()
                    if not prefix_stripped or prefix_stripped.startswith("#"):
                        i += 1
                        continue
                    if ":" in prefix_stripped:
                        pfx, uri = prefix_stripped.split(":", 1)
                        result["prefixes"][pfx.strip()] = TOONFormatter._strip_angle_brackets(uri.strip())
                    i += 1
                continue

            if stripped == "classes:" and line.startswith("  "):
                i += 1
                while i < len(lines):
                    class_line = lines[i].rstrip()
                    if not class_line.strip():
                        i += 1
                        continue
                    if class_line.startswith("  notation:") or class_line.startswith("  prefixes:"):
                        break
                    if not class_line.startswith("    ") or class_line.startswith("     "):
                        i += 1
                        continue

                    class_match = re.match(r'^\s{4}(.+?):\s*$', class_line)
                    if not class_match:
                        i += 1
                        continue

                    class_name = class_match.group(1).strip()
                    class_label = class_name
                    class_data: Dict[str, Any] = {
                        "class_label": class_label,
                        "class_examples": [],
                        "properties": [],
                    }

                    i += 1
                    in_properties_section = False
                    while i < len(lines):
                        inner_line = lines[i].rstrip()
                        inner_stripped = inner_line.strip()
                        if not inner_stripped:
                            i += 1
                            continue
                        if not inner_line.startswith("      "):
                            break

                        if inner_stripped.startswith("class label:"):
                            class_data["class_label"] = inner_stripped.split(":", 1)[1].strip()
                            i += 1
                            continue

                        if inner_stripped == "properties:":
                            in_properties_section = True
                            i += 1
                            continue

                        if inner_stripped.startswith("Example Instances"):
                            i += 1
                            while i < len(lines) and lines[i].startswith("        "):
                                ex_line = lines[i].rstrip().strip()
                                if ex_line.startswith("-"):
                                    ex_value = ex_line[1:].strip()
                                    class_data["class_examples"].append(ex_value)
                                i += 1
                            in_properties_section = False
                            continue

                        if in_properties_section and inner_line.startswith("        ") and not inner_line.startswith("         "):
                            prop_match = re.match(r'^\s{8}(.+?):\s*$', inner_line)
                            if prop_match:
                                prop_name = prop_match.group(1).strip()
                                prop: Dict[str, Any] = {
                                    "property_name": prop_name,
                                    "property_label": prop_name,
                                }

                                i += 1
                                while i < len(lines) and lines[i].startswith("          "):
                                    attr_line = lines[i].rstrip()
                                    attr_stripped = attr_line.strip()

                                    if attr_stripped.startswith("property label:"):
                                        prop["property_label"] = attr_stripped.split(":", 1)[1].strip()
                                    elif attr_stripped.startswith("range:"):
                                        range_text = attr_stripped.split(":", 1)[1].strip()
                                        if range_text in {"str", "string", "xsd:string"}:
                                            prop["datatype"] = ["xsd:string"]
                                            prop["node_kind"] = "http://www.w3.org/ns/shacl#Literal"
                                        elif range_text == "IRI":
                                            prop["node_kind"] = "http://www.w3.org/ns/shacl#IRI"
                                        else:
                                            prop["or_classes"] = [range_text]
                                            prop["node_kind"] = "http://www.w3.org/ns/shacl#IRI"
                                    elif attr_stripped.startswith("min:"):
                                        prop["min_count"] = int(attr_stripped.split(":", 1)[1].strip())
                                    elif attr_stripped.startswith("max:"):
                                        prop["max_count"] = int(attr_stripped.split(":", 1)[1].strip())
                                    elif attr_stripped.startswith("description:"):
                                        prop["description"] = attr_stripped.split(":", 1)[1].strip()
                                    elif attr_stripped.startswith("Examples of values:"):
                                        i += 1
                                        examples = []
                                        while i < len(lines) and lines[i].startswith("            "):
                                            ex_line = lines[i].rstrip().strip()
                                            if ex_line.startswith("-"):
                                                ex_value = ex_line[1:].strip().strip('"')
                                                examples.append(ex_value)
                                            i += 1
                                        prop["examples"] = examples
                                        continue
                                    else:
                                        i += 1
                                        continue
                                    i += 1

                                class_data["properties"].append(prop)
                                continue
                            else:
                                i += 1
                                continue
                        else:
                            i += 1
                            continue

                    result["classes"][class_name] = class_data
                continue

            if stripped == "notation:" and line.startswith("  "):
                i += 1
                while i < len(lines) and lines[i].startswith("    "):
                    i += 1
                continue

            i += 1

        return result

    @staticmethod
    def _parse_example_list(text: str) -> List[str]:
        """Parse a comma-separated example list with quoted values."""
        if not text:
            return []

        import csv

        try:
            values = next(csv.reader([text], skipinitialspace=True))
        except Exception:
            values = [text]

        cleaned: List[str] = []
        for value in values:
            item = value.strip()
            if not item:
                continue
            if item.startswith('"') and item.endswith('"'):
                item = item[1:-1].replace('\\"', '"')
            if "-" in item and not item.startswith(("http://", "https://")):
                # Preserve compact IRI-label syntax as a readable string.
                cleaned.append(item)
            else:
                cleaned.append(item)
        return cleaned

    @staticmethod
    def _strip_angle_brackets(value: str) -> str:
        text = value.strip()
        if text.startswith("<") and text.endswith(">"):
            return text[1:-1].strip()
        return text

    @staticmethod
    def _normalize_schema_root(data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {"prefixes": {}, "classes": {}}

        if isinstance(data.get("schema"), dict):
            return data["schema"]

        if "prefixes" in data or "classes" in data:
            return data

        return {"prefixes": {}, "classes": data}

    @staticmethod
    def _format_class_block(
        class_name: str,
        class_data: Any,
        prefixes: Dict[str, str],
        include_examples: bool = True,
        include_descriptions: bool = True,
        max_examples: int = 2,
    ) -> List[str]:
        lines: List[str] = []
        class_dict = class_data if isinstance(class_data, dict) else {}
        compact_class_name = TOONFormatter._compact_iri(class_name, prefixes)

        examples = class_dict.get("class_examples", []) or []
        properties = class_dict.get("properties", []) or []

        lines.append("")
        lines.append(f"--- {compact_class_name} ---")

        prop_rows: List[List[str]] = []
        if properties:
            for prop in properties:
                prop_name = prop.get("property_name") or prop.get("name") or "property"
                compact_prop_name = TOONFormatter._compact_iri(prop_name, prefixes)
                prop_label = prop.get("property_label") or TOONFormatter._local_name(prop_name)
                range_text = TOONFormatter._format_range(prop)
                cardinality = TOONFormatter._format_cardinality(prop)
                prop_rows.append([compact_prop_name, prop_label, range_text, cardinality])
        else:
            prop_rows.append(["(none)", "-", "-", "-"])

        col1 = max(len("Property IRI"), *(len(row[0]) for row in prop_rows))
        col2 = max(len("Label"), *(len(row[1]) for row in prop_rows))
        col3 = max(len("Range"), *(len(row[2]) for row in prop_rows))
        col4 = max(len("Card"), *(len(row[3]) for row in prop_rows))

        lines.append(f"| {'Property IRI':<{col1}} | {'Label':<{col2}} | {'Range':<{col3}} | {'Card':<{col4}} |")
        for row in prop_rows:
            lines.append(f"| {row[0]:<{col1}} | {row[1]:<{col2}} | {row[2]:<{col3}} | {row[3]:<{col4}} |")

        if include_examples and examples:
            example_strs = [TOONFormatter._format_example_value(ex) for ex in examples[:max_examples]]
            lines.append(f"Instances: {', '.join(example_strs)}")

        return lines

    @staticmethod
    def _format_property_line(prop: Dict[str, Any], prefixes: Dict[str, str]) -> str:
        prop_name = prop.get("property_name") or prop.get("name") or "property"
        prop_label = prop.get("property_label") or TOONFormatter._local_name(prop_name)
        compact_prop_name = TOONFormatter._compact_iri(prop_name, prefixes)
        cardinality = TOONFormatter._format_cardinality(prop)
        range_text = TOONFormatter._format_range(prop)
        examples = prop.get("examples", []) or []
        example_text = ", ".join(TOONFormatter._format_example_value(v) for v in examples[:2])

        line = f"      {compact_prop_name}({range_text},{cardinality}):"
        if example_text:
            line += f" {example_text}"

        description = prop.get("description")
        if description:
            line += f"  # {description}"
        return line

    @staticmethod
    def _format_property_line_with_labels(prop: Dict[str, Any], prefixes: Dict[str, str]) -> str:
        """Format property line with inline labels in parentheses and example values."""
        prop_name = prop.get("property_name") or prop.get("name") or "property"
        prop_label = prop.get("property_label") or TOONFormatter._local_name(prop_name)
        compact_prop_name = TOONFormatter._compact_iri(prop_name, prefixes)
        cardinality = TOONFormatter._format_cardinality(prop)
        range_text = TOONFormatter._format_range(prop)
        examples = prop.get("examples", []) or []
        
        # Format example values (already handles quoting)
        example_parts = []
        for ex in examples[:2]:
            ex_str = TOONFormatter._format_example_value(ex)
            example_parts.append(ex_str)
        example_text = ", ".join(example_parts) if example_parts else ""

        line = f"      {compact_prop_name}({range_text},{cardinality}): {example_text}" if example_text else f"      {compact_prop_name}({range_text},{cardinality}):"
        
        description = prop.get("description")
        if description:
            line += f"  # {description}"
        return line

    @staticmethod
    def _format_cardinality(prop: Dict[str, Any]) -> str:
        min_count = prop.get("min_count")
        max_count = prop.get("max_count")

        if min_count == 1 and max_count == 1:
            return "1"
        if min_count in (1, "1") and max_count in (None, "", 0):
            return "1+"
        if max_count == 1 and (min_count in (None, 0, "", "0")):
            return "0-1"
        if min_count in (0, None, "", "0") and max_count in (None, "", 0):
            return "0+"
        if min_count is not None and max_count is None:
            return "1+"
        return "0-1"

    @staticmethod
    def _format_range(prop: Dict[str, Any]) -> str:
        node_kind = prop.get("node_kind")
        if isinstance(node_kind, str) and node_kind.strip():
            if node_kind.endswith("#Literal"):
                datatypes = prop.get("datatype", []) or []
                if datatypes:
                    return TOONFormatter._compact_type_name(datatypes[0])
                return "str"
            if node_kind.endswith("#IRI"):
                or_classes = prop.get("or_classes", []) or []
                if or_classes:
                    return TOONFormatter._compact_type_name(or_classes[0])
                datatypes = prop.get("datatype", []) or []
                if datatypes:
                    return TOONFormatter._compact_type_name(datatypes[0])
                return "IRI"

        datatypes = prop.get("datatype", []) or []
        if datatypes:
            return TOONFormatter._compact_type_name(datatypes[0])

        or_classes = prop.get("or_classes", []) or []
        if or_classes:
            return TOONFormatter._compact_type_name(or_classes[0])

        return "str"

    @staticmethod
    def _compact_type_name(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "str"
        if text.startswith(("http://", "https://")):
            if "#" in text:
                return text.rsplit("#", 1)[-1]
            return text.rstrip("/").rsplit("/", 1)[-1]
        return text.split(":", 1)[-1] if ":" in text else text

    @staticmethod
    def _format_example_value(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)

        text = str(value).strip()
        if not text:
            return '""'

        if text.startswith("<") and text.endswith(">"):
            return text[1:-1].strip()
        if text.startswith(("http://", "https://")):
            return text
        if "(" in text and text.endswith(")"):
            return text
        match = re.match(r"^(.+?)\s+-\s+(.+)$", text)
        if match and (":" in match.group(1) or match.group(1).startswith(("http://", "https://"))):
            iri = match.group(1).strip()
            label = match.group(2).strip()
            return f"{iri} ({label})"
        # Leave prefixed IRIs (e.g. pv:LocalName) unquoted as well.
        # Match common prefix:name patterns but avoid accidental matches
        # for strings that contain colons in other contexts.
        if ":" in text and not text.startswith(('"', '<')) and re.match(r'^[A-Za-z_][-A-Za-z0-9_.]*:.+$', text):
            return text
        return TOONFormatter._quote_text(text)

    @staticmethod
    def _quote_text(value: str) -> str:
        escaped = value.replace('"', '""')
        return f'"{escaped}"'

    @staticmethod
    def _compact_iri(value: Any, prefixes: Dict[str, str]) -> str:
        """Compact full IRIs to prefix form when possible; keep compact names unchanged."""
        text = str(value or "").strip()
        if not text:
            return "item"
        if text.startswith("<") and text.endswith(">"):
            text = text[1:-1].strip()
        if ":" in text and not text.startswith(("http://", "https://")):
            return text

        if text.startswith(("http://", "https://")) and prefixes:
            for prefix, uri in sorted(prefixes.items(), key=lambda item: len(str(item[1])), reverse=True):
                uri_text = str(uri or "")
                if uri_text and text.startswith(uri_text):
                    local = text[len(uri_text):]
                    if local:
                        return f"{prefix}:{local}"

        return text

    @staticmethod
    def _local_name(value: str) -> str:
        text = str(value or "").strip()
        if ":" in text:
            return text.split(":", 1)[1]
        if "#" in text:
            return text.rsplit("#", 1)[-1]
        if "/" in text:
            return text.rstrip("/").rsplit("/", 1)[-1]
        return text or "item"
    
    @staticmethod
    def _parse_tabular_header(line: str):
        """Parse 'key[N]{fields}:' header. Returns (key, field_names) or None."""
        import re
        match = re.match(r'^(\w+)\[\d+\]\{([^}]+)\}:\s*$', line)
        if match:
            key = match.group(1)
            fields = [f.strip() for f in match.group(2).split(",")]
            return (key, fields)
        return None
    
    @staticmethod
    def _parse_simple_array_header(line: str):
        """Parse 'key[N]: item1,item2,...' header. Returns (key, items) or None."""
        import re
        match = re.match(r'^(\w+)\[\d+\]:\s*(.*)$', line)
        if match:
            key = match.group(1)
            items_str = match.group(2).strip()
            if items_str:
                items = [i.strip() for i in items_str.split(",")]
            else:
                items = []
            return (key, items)
        return None
    
    @staticmethod
    def _parse_csv_row(row_str: str, fields: List[str]) -> Dict[str, Any]:
        """Parse a CSV-style row string into a dict."""
        # Simple CSV parsing (handles quoted values)
        values = []
        current = ""
        in_quotes = False
        for char in row_str:
            if char == '"':
                in_quotes = not in_quotes
            elif char == "," and not in_quotes:
                values.append(current.strip())
                current = ""
                continue
            current += char
        values.append(current.strip())
        
        # Unescape quotes and convert types
        result = {}
        for field, value in zip(fields, values):
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('""', '"')
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value and value.lstrip("-").isdigit():
                value = int(value)
            elif value and "." in value and value.replace(".", "", 1).lstrip("-").isdigit():
                value = float(value)
            elif value == "":
                value = None
            result[field] = value
        
        return result
    
    @staticmethod
    def _quote_if_needed(value: Any) -> str:
        """Quote a value if it's a string that needs quoting."""
        if isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif value is None:
            return ""
        elif isinstance(value, str):
            return TOONFormatter._format_scalar(value)
        else:
            return json.dumps(value)

    @staticmethod
    def _format_scalar(value: Any) -> str:
        """Format a scalar for readable TOON output with minimal quoting."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if value is None:
            return ""
        if not isinstance(value, str):
            return json.dumps(value)

        text = value.strip()
        if text == "":
            return '""'
        if text.startswith((" ", "\t")) or text.endswith((" ", "\t")):
            return json.dumps(text)
        if any(ch in text for ch in ["\n", "\r"]):
            return json.dumps(text)
        # Leave URIs, prefixed IRIs, labels, and human-readable text unquoted.
        return text

    @staticmethod
    def _format_key(key: Any) -> str:
        """Format mapping keys safely for YAML-like output."""
        if not isinstance(key, str):
            return str(key)
        text = key.strip()
        if text == "":
            return '""'
        if any(ch in text for ch in ["\n", "\r", "\t", "#", "{", "}"]):
            return json.dumps(text)
        if text.startswith(("-", "?", ":")):
            return json.dumps(text)
        if ":" in text or " " in text:
            return json.dumps(text)
        return text

    @staticmethod
    def _unquote(v: str) -> str:
        """Remove surrounding quotes from a TOON value and unescape CSV quotes."""
        if not isinstance(v, str):
            return v
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            inner = v[1:-1]
            return inner.replace('""', '"')
        return v
