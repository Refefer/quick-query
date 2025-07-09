import json
import sys
import os
import importlib.util
import inspect
import typing
import re

# simple mapping from Python types to JSON Schema types
_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}

def _resolve_type(annotation):
    if annotation in _TYPE_MAP:
        return _TYPE_MAP[annotation]

    origin = typing.get_origin(annotation)
    if origin in (list, tuple):
        return "array"

    if origin is dict:
        return "object"

    return "string"


def _parse_param_docs(doc):
    if not doc:
        return {}

    params, in_args, current = {}, False, None
    for line in doc.splitlines():
        s = line.strip()
        if s.startswith(("Args:", "Parameters:")):
            in_args = True
            continue

        if not in_args:
            continue

        if s == "":
            break

        m = re.match(r"(\w+)\s*:\s*(.*)", s)
        if m:
            current, desc = m.groups()
            params[current] = desc.strip()

        elif current:
            params[current] += " " + s

    return params


def make_tool_metadata(func):
    """
    Accepts:
      - plain functions
      - unbound methods:    MyClass.method
      - bound methods:      instance.method
      - classmethods/staticmethods
    and simply drops 'self' or 'cls' if it appears first.
    """
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    desc = doc.splitlines()[0] if doc else ""
    param_docs = _parse_param_docs(doc)

    # get parameter list; if first is 'self' or 'cls', drop it
    params = list(sig.parameters.values())
    if params and params[0].name in ("self", "cls"):
        params = params[1:]

    properties = {}
    required = []
    for p in params:
        # skip *args/**kwargs
        if p.kind in (inspect.Parameter.VAR_POSITIONAL,
                     inspect.Parameter.VAR_KEYWORD):
            continue

        ann = p.annotation if p.annotation is not inspect._empty else str
        t = _resolve_type(ann)
        prop = {"type": t}
        if p.name in param_docs:
            prop["description"] = param_docs[p.name]

        properties[p.name] = prop
        if p.default is inspect._empty:
            required.append(p.name)

    return func.__name__, {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        }
    }

def get_if_loaded(file_path):
    abs_fp = os.path.abspath(file_path)
    for module_name, module in sys.modules.items():
        mod_path = getattr(module, '__file__', None)
        if mod_path is not None and os.path.abspath(mod_path) == abs_fp:
            return module

    return None

def load_module(tool_type: str, path: str):
    match tool_type:
        case "module":
            return importlib.import_module(path)
        case "file":
            module = get_if_loaded(path)
            if module is None:
                module_name = os.path.splitext(os.path.basename(path))[0]
                spec = importlib.util.spec_from_file_location(module_name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

            return module
        case _:
            raise TypeError(f"No tool type {tool_type} known!")

class Tool:
    def __init__(self, entrypoint):
        self.entrypoint = entrypoint
        self.name, self.function_spec = make_tool_metadata(entrypoint)

    def evaluate(self, payload):
        if self.name != payload['name']:
            raise TypeError("Function name doesn't match payload!")

        kwargs = json.loads(payload['arguments'])
        return self.entrypoint(**kwargs)

def load_tools(tools: typing.Dict[str, dict]):
    tools_mapping = {}
    for tool_name, spec in tools.items():
        tool_type  = spec['type']
        path       = spec['path']
        entrypoint = spec['entrypoint']
        init_args = json.loads(spec.get('init_args', '{}').strip())

        # load the module
        module = load_module(tool_type, path)
        ep = getattr(module, entrypoint)
        if isinstance(ep, type):
            ep = ep(**init_args)

        tool = Tool(ep)
        tools_mapping[tool.name] = tool

    return tools_mapping

if __name__ == '__main__':

    def calculate(expr: str, decimal: int) -> float:
        """
        Calculates the following expression and returns the result.

        Args:
          expr: The string representation of the expression (e.g. "3 * 5 / 2")
          decimal: Number of digits to round decimals to.
        """
        pass

    import pprint
    pprint.pprint(make_tool_metadata(calculate))
