import json

RE2_PROMPT = "{message}\nRead the question again:\n{message}"
class MessageProcessor:
    def __init__(self, re2=False):
        self.re2 = re2

    def process_user_prompt(self, prompt):
        if self.re2:
            prompt = RE2_PROMPT.format(message=prompt)

        return {"role": "user", "content": prompt}

    def process_tool_response(self, payload):
        if not all(k in payload for k in ('id', 'content', 'name')):
            raise TypeError("Tool processed payload incorrectly!")

        return {"role": "tool",  
                "name": payload['name'],
                "tool_call_id": payload['id'],
                "content": json.dumps(payload['content'])
                }

    def process_tool_request(self, payload):
        if not all(k in payload for k in ('id', 'name', 'arguments')):
            raise TypeError("Tool processed payload incorrectly!")

        return {
            "role": "assistant", 
            "content": None, 
            "tool_calls": [{
                "id": payload['id'],
                "type": "function",
                "function": {
                    "name": payload['name'],
                    "arguments": payload['arguments']
                }
            }]
        }

