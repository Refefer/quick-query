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
    def __init__(self, entrypoint, method=None, name=None, enabled=False):
        self.entrypoint = entrypoint
        self.method = method
        if self.method is None:
            self.name, self.function_spec = make_tool_metadata(entrypoint)
        else:
            method = getattr(self.entrypoint, self.method)
            self.name, self.function_spec = make_tool_metadata(method)

        # We override names from the spec if provided.
        if name is not None:
            self.name = name

        self.enabled = enabled

    def evaluate(self, payload):
        if self.name != payload['name']:
            raise TypeError("Function name doesn't match payload!")

        kwargs = json.loads(payload['arguments'])
        if self.method is None:
            return self.entrypoint(**kwargs)
        else:
            return getattr(self.entrypoint, self.method)(**kwargs)

    def __repr__(self):
        return f"Tool(name={self.name}, enabled={self.enabled})"

    __str__ = __repr__

def load_tools(tools_mapping: typing.Mapping, tools: typing.Dict[str, dict]):
    for spec in tools['tool']:
        tool_type  = spec['type']
        path       = spec['path']
        entrypoints = spec['entrypoints']
        enabled = spec.get('enabled', True)
        
        # load the module
        module = load_module(tool_type, path)

        for entrypoint in entrypoints:
            tool_name = entrypoint['name']
            if tool_name in tools_mapping:
                print(f"Tool '{tool_name}' has is overriden by new definition")

            # Check if we're accessing a class method
            method = entrypoint['method']
            if '.' in method:
                cls, method = method.split('.', 1)
                ep = getattr(module, cls)
                init_args = entrypoint.get('args', {})
                if isinstance(init_args, str):
                    init_args = json.loads(init_args)
                elif isinstance(init_args, dict):
                    pass
                else:
                    raise TypeError(f"Bad 'arguments' passed in for tool {tool_name}!")

                ep = ep(**init_args)

                tool = Tool(ep, method=method, name=tool_name, enabled=enabled)
            else:
                ep = getattr(module, method)
                tool = Tool(ep, name=tool_name, enabled=enabled)

            print(f"Loaded: {tool}'")
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
