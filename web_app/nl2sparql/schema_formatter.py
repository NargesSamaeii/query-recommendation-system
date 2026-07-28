"""
Schema Formatter Module

Formats parsed SHACL schema for LLM consumption.
"""

import re


class SchemaFormatter:
    """Formats schema for natural language processing."""
    
    def __init__(self, schema, label_source_schema=None):
        """
        Initialize formatter with parsed schema.
        
        Args:
            schema: Dictionary containing prefixes and classes
            label_source_schema: Optional schema used for class label lookup.
                Useful when `schema` is a filtered subset but labels should be
                resolved against the full schema.
        """
        self.schema = schema
        self.prefixes = schema.get("prefixes", {})
        self.classes = schema.get("classes", {})
        self.reverse_prefixes = {uri: pfx for pfx, uri in self.prefixes.items()}
        self.class_label_lookup = {}

        lookup_schema = label_source_schema if isinstance(label_source_schema, dict) else schema
        lookup_classes = lookup_schema.get("classes", {}) if isinstance(lookup_schema, dict) else {}

        for class_prefixed, class_data in lookup_classes.items():
            class_label = class_data.get("class_label") or class_prefixed.split(":")[-1]
            expanded = self.expand_prefixed_iri(class_prefixed)
            compact = self.compact_iri(expanded)
            self.class_label_lookup[class_prefixed] = class_label
            self.class_label_lookup[expanded] = class_label
            self.class_label_lookup[compact] = class_label
    
    def expand_prefixed_iri(self, value):
        """Expand prefixed IRI if it uses a known prefix."""
        if not isinstance(value, str) or ":" not in value:
            return value
        prefix, local = value.split(":", 1)
        if prefix in self.prefixes:
            return self.prefixes[prefix] + local
        return value

    def compact_iri(self, full_iri):
        """Convert full IRIs back to prefix form if possible."""
        if not isinstance(full_iri, str):
            return full_iri
        for uri, pfx in self.reverse_prefixes.items():
            if full_iri.startswith(uri):
                return f"{pfx}:{full_iri[len(uri):]}"
        return full_iri

    def format_range_value(self, datatype):
        """Format a datatype/range value with both compact form and label."""
        compact = self.compact_iri(datatype)
        if not isinstance(compact, str):
            return str(compact)

        label = (
            self.class_label_lookup.get(datatype)
            or self.class_label_lookup.get(compact)
            or self.class_label_lookup.get(self.expand_prefixed_iri(compact))
        )

        if label:
            return f"{compact} ({label.strip()})"

        if not label:
            label = compact
            if compact.startswith(("http://", "https://")):
                if "#" in compact:
                    label = compact.rsplit("#", 1)[-1]
                elif "/" in compact:
                    label = compact.rstrip("/").rsplit("/", 1)[-1]
            elif ":" in compact:
                label = compact.split(":", 1)[1]
            elif "#" in compact:
                label = compact.rsplit("#", 1)[-1]
            elif "/" in compact:
                label = compact.rstrip("/").rsplit("/", 1)[-1]

        label = label.strip()
        if label and label != compact:
            return f"{compact} ({label})"
        return compact

    def compact_example_text(self, example_text):
        """Compact the leading IRI token in examples while preserving labels/values."""
        text = str(example_text or "").strip()
        if not text:
            return text

        # <full-IRI> trailing text
        match = re.match(r'^<(https?://[^>]+)>\s*(.*)$', text)
        if match:
            iri = match.group(1).strip()
            tail = match.group(2).strip()
            if tail:
                tail = re.sub(r'^-\s*', '', tail)
            compact = self.compact_iri(iri)
            return f"{compact} - {tail}".strip(" -") if tail else compact

        # full IRI without brackets
        match = re.match(r'^(https?://\S+)\s*(.*)$', text)
        if match:
            iri = match.group(1).strip()
            tail = match.group(2).strip()
            if tail:
                tail = re.sub(r'^-\s*', '', tail)
            compact = self.compact_iri(iri)
            return f"{compact} - {tail}".strip(" -") if tail else compact

        # prefixed IRI like prod_inst:dept-22183 trailing text
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*:[^\s]+)\s*(.*)$', text)
        if match:
            token = match.group(1)
            tail = match.group(2).strip()
            if tail:
                tail = re.sub(r'^-\s*', '', tail)
            # Expand then re-compact to normalize
            expanded = self.expand_prefixed_iri(token)
            compact = self.compact_iri(expanded)
            return f"{compact} - {tail}".strip(" -") if tail else compact

        # Plain literal — return as-is
        return text

    def format_class_example(self, example_text):
        """Format class example and append explicit no-label marker when missing."""
        compact = self.compact_example_text(example_text)
        if " - " in compact:
            return compact

        token = compact.strip().split(maxsplit=1)[0] if compact.strip() else ""
        if token and (
            token.startswith("http://")
            or token.startswith("https://")
            or re.match(r'^[A-Za-z_][A-Za-z0-9_\-]*:.+$', token)
        ):
            return f"{compact} - no label"

        return compact

    def format_clean(self, include_examples=True, include_descriptions=True):
        """
        Format parsed SHACL schema while keeping prefix notation everywhere.
        
        Args:
            include_examples: Whether to include class and property examples (default: True)
            include_descriptions: Whether to include property descriptions (default: True)
        
        Returns:
            Formatted string representation of the schema
        """
        out = []

        # Print prefixes section
        out.append("Prefixes:")
        for pfx, uri in self.prefixes.items():
            out.append(f"  {pfx}: <{uri}>")
        out.append("")

        # Process classes
        for class_prefixed, class_data in self.classes.items():
            out.append(f"Class IRI: {class_prefixed}")

            local_name = class_prefixed.split(":")[-1]
            class_label = class_data.get("class_label", local_name)
            out.append(f"Class Label: {class_label}")

            out.append("Properties:")

            props = class_data.get("properties", [])
            if not props:
                out.append("  (No properties available)")

            for prop in props:
                prop_prefixed = prop.get("property_name", "")
                prop_label = prop.get("property_label", "")
                prop_description = prop.get("description", "")

                datatypes = prop.get("datatype", [])
                dtype_str = ""
                if datatypes:
                    dtype_compact = [self.format_range_value(dt) for dt in datatypes]
                    dtype_str = f" | Range: {', '.join(dtype_compact)}"

                description_str = (
                    f" | Description: {prop_description}"
                    if include_descriptions and prop_description
                    else ""
                )

                if include_examples:
                    examples = prop.get("examples", [])
                    if examples:
                        ex_out = [self.compact_example_text(e) for e in examples[:2]]
                        ex_str = ", ".join(ex_out)
                    else:
                        ex_str = "(none)"
                    out.append(
                        f"  - Property: {prop_prefixed} | Label: {prop_label}{dtype_str}{description_str} | Examples of values: {ex_str}"
                    )
                else:
                    out.append(
                        f"  - Property: {prop_prefixed} | Label: {prop_label}{dtype_str}{description_str}"
                    )

            if include_examples:
                out.append("Example Instances of this class and their labels:")
                examples = class_data.get("class_examples", [])
                if examples:
                    for ex in examples[:2]:
                        out.append(f"  - {self.format_class_example(ex)}")
                else:
                    out.append("  (No examples available)")
                out.append("")
            out.append("")

        return "\n".join(out)