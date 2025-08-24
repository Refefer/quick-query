from typing import Optional, Dict, List, Any, Generator
import json
import requests
from itertools import groupby

from .tools import Tool

class TagTypes:
    ReasoningContent = "reasoning_content"
    Reasoning = "reasoning"
    Content = "content"
    Tool_calls = "tool_calls"
    Role = "role"
    ReasoningDetails = "reasoning_details"

def build_headers(
    api_key: str
) -> Dict[str, str]:
    """
    Build standard HTTP headers for API requests.

    Args:
        api_key: Authentication key

    Returns:
        Dictionary of HTTP headers
    """
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

def api_request(
    method: str,
    url: str,
    api_key: str,
    json_payload: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Perform a generic API request.

    Args:
        method: HTTP method, "GET" or "POST"
        url: Full request URL
        api_key: Authentication token
        json_payload: JSON data for POST requests

    Returns:
        Parsed JSON response or None on failure
    """
    headers = build_headers(api_key)
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        else:
            response = requests.post(url, headers=headers, json=json_payload)

        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        print(f"API Error: {e}")
        return None

def get_model_id(
    api_url: str,
    api_key: str
) -> Optional[str]:
    """
    Retrieve the first available model ID from the API.

    Args:
        api_url: Base API URL
        api_key: Authentication key

    Returns:
        Model ID string or None if not found
    """
    result = api_request("GET", f"{api_url}/models", api_key)
    if not result:
        return None

    data = result.get("data", [])
    if data and isinstance(data, list):
        return data[0].get("id")

    return None

def send_chat_completion(
    host: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    tools: Optional[Dict[str, Tool]] = None,
    stream: bool = True,
    parameters: Optional[Dict[str, Any]] = None,
) -> Generator[str, None, None]:
    """
    Streams responses from an OpenAI-compatible chat/completions endpoint in real-time.
    Streams part of the data to stderr until a substring is found, then switches to stdout.

    Parameters:
    host (str): The API host endpoint of the server, including http(s).
    model (str): The model name to use for the request
    api_key (str): The API key for authentication.
    messages (List[Dict[str, str]]): Messages to send to the completion api
    tools (Optional[Dict[str, Tool]]): Optional tool specifications
    stream (bool): Whether to request streaming responses
    parameters (Optional[Dict[str, Any]]): Additional server parameters (e.g., temperature, top_p)

    Yields:
        Requests.Response
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": messages,
        "stream": stream
    }

    if tools is not None:
        enabled_tools = [tool.function_spec for tool in tools.values() if tool.enabled]
        if len(enabled_tools) > 0:
            data['tools'] = enabled_tools

    # Merge any additional parameters into the request payload
    if parameters:
        data.update(parameters)

    with open('/tmp/log', 'w') as out:
        import json
        out.write(json.dumps(data))

    url = f"{host}/chat/completions"
    return requests.post(url, headers=headers, json=data, stream=stream)

def stream_deltas(response, stream):
    """
    Takes a streaming response and converts it into a generator yield the raw stream.
    """
    stop = False
    for line in response.iter_lines():
        if stop or not line:
            continue

        line_data = line.decode('utf-8')
        if stream and line_data.startswith('data: '):
            content = line_data[6:]
            if content == '[DONE]':
                stop = True
                continue

            json_data = try_json(content)
            choices = json_data['choices']
            if len(choices) > 0:
                yield choices[0]['delta']

        elif not stream:
            json_data = try_json(line_data)

            for choice in json_data['choices']:
                yield choice['message']

def try_json(content):
    try:
        return json.loads(content)
    except Exception as e:
        print(f"Error parsing line: {e}")
        sys.exit(1)

def stream_response_chunks(response, stream):
    """
    Takes a streaming response and converts it into a generator yield the raw stream.
    """
    for delta in stream_deltas(response, stream):
        for stream_type, value in delta.items():
            if value is None:
                continue

            match stream_type:
                case TagTypes.Tool_calls:
                    tool_call = {}
                    for tool_call_chunk in value:
                        # Get the function id if available
                        if 'id' in tool_call_chunk:
                            tool_call['id'] = tool_call_chunk['id']

                        func = tool_call_chunk['function']
                        if 'name' in func:
                            tool_call['name'] = func['name']

                        if 'arguments' in func:
                            tool_call['arguments'] = func['arguments']

                    yield TagTypes.Tool_calls, json.dumps(tool_call)
                        
                case TagTypes.Reasoning:
                    if len(value) > 0:
                        yield stream_type, value

                case TagTypes.Content:
                    if len(value) > 0:
                        yield stream_type, value

                case TagTypes.ReasoningContent:
                    yield TagTypes.Reasoning, value

                case TagTypes.Role | TagTypes.ReasoningDetails:
                    pass

                case _:
                    raise TypeError(f"Unknown stream type: '{stream_type}'")

class OpenAIServer:
    def __init__(
        self,
        host: str,
        api_key: str,
        model: str,
        think_tag: str,
        structured_stream: bool,
        tools: Optional[Dict[str, Tool]],
        parameters: Optional[Dict[str, Any]] = None,
    ):
        self.host = host
        self.api_key = api_key
        self.model = model
        self.think_tag = think_tag
        self.structured_stream = structured_stream
        self.tools = tools
        self.parameters = parameters or {}

    def send_chat_completion(self, messages):
        stream = not self.tools or self.structured_stream
        response = send_chat_completion(self.host, self.api_key, self.model, messages, self.tools, stream, self.parameters)
        return stream_response_chunks(response, stream)
 
    def process_tool_call(self, payload):
        evaluation = self.tools[payload['name']].evaluate(payload)
        payload['content'] = evaluation
        payload['tool_call_id'] = payload['id']
        return payload
