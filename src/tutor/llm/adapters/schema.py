"""Provider-neutral JSON-schema rewriting for native structured output. No SDK import here, so an
adapter can use it without loading another provider's SDK."""

import copy


def strict_schema(schema: dict) -> dict:
    """Rewrite a pydantic JSON schema into the form OpenAI's strict mode accepts.

    OpenAI's documented strict-mode rules: every object sets `additionalProperties: false` and
    lists all of its properties in `required`. `default` is dropped (with every field required
    it means nothing), and a `$ref` that has sibling keys is inlined, because strict mode
    rejects siblings next to `$ref`. The input is not modified.
    """
    root = copy.deepcopy(schema)
    defs = root.get("$defs", {})

    def walk(node):
        if isinstance(node, list):
            return [walk(n) for n in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node and len(node) > 1:
            target = defs.get(node["$ref"].rsplit("/", 1)[-1], {})
            node = {**copy.deepcopy(target), **{k: v for k, v in node.items() if k != "$ref"}}
        node.pop("default", None)
        out = {}
        for k, v in node.items():
            if k in ("properties", "$defs", "definitions"):
                out[k] = {name: walk(sub) for name, sub in v.items()}
            else:
                out[k] = walk(v)
        if out.get("type") == "object" or "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}))
        return out

    return walk(root)
