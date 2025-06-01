from typing import Optional, Dict, List, Any, Generator
import json

import requests

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
    messages: List[Dict[str, str]]
) -> Generator[str, None, None]:
    """
    Streams responses from an OpenAI-compatible chat/completions endpoint in real-time.
    Streams part of the data to stderr until a substring is found, then switches to stdout.

    Parameters:
    host (str): The API host endpoint of the server, including http(s).
    model (str): The model name to use for the request
    api_key (str): The API key for authentication.
    messages (List[Dict[str, str]]): Messages to send to the completion api

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
        "stream": True
    }
    url = f"{host}/chat/completions"
    return requests.post(url, headers=headers, json=data, stream=True)

def stream_response_chunks(response):
    """
    Takes a streaming response and converts it into a generator yield the raw stream.
    """
    buffer = ''
    for line in response.iter_lines():
        if not line:
            continue

        line_data = line.decode('utf-8')
        if line_data.startswith('data: '):
            content = line_data[6:]
            if content == '[DONE]':
                break

            try:
                json_data = json.loads(content)
                chunk = json_data['choices'][0]['delta'].get('content', '')
            except Exception as e:
                print(f"Error parsing line: {e}")
                sys.exit(1)

            yield chunk

class OpenAIServer:
    def __init__(
        self,
        host: str,
        api_key: str,
        model: str
    ):
        self.host = host
        self.api_key = api_key
        self.model = model

    def send_chat_completion(
        self, 
        messages
    ):
        response = send_chat_completion(self.host, self.api_key, self.model, messages)
        return stream_response_chunks(response)
 
