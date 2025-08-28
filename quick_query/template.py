from itertools import islice
import sys
import json
import concurrent.futures
from contextlib import contextmanager
from functools import lru_cache
from functools import lru_cache
from .openapi import TagTypes
from quick_query.formatter import process_streaming_response, NullFormatter

import jinja2 

class VariableStreamer:
    def stream(self):
        raise NotImplementedError()

class JsonArrayStreamer(VariableStreamer):
    def __init__(self, value):
        self.value = value

    def stream(self):
        payload = json.loads(self.value)
        if isinstance(payload, dict):
            payload = [payload]

        for p in payload:
            yield p

class JsonlStreamer(VariableStreamer):
    def __init__(self, fname):
        self.fname = fname

    def stream(self):
        if self.fname == '-':
            for line in sys.stdin:
                yield json.loads(line)
        else:
            with open(self.fname) as f:
                for line in f:
                    yield json.loads(line)

class TemplateExtractor:
    @staticmethod
    @lru_cache(maxsize=128)
    def compile_template(template_string):
        return jinja2.Template(template_string)

    def render(self, variables):
        raise NotImplementedError()

class TemplateFileExtractor(TemplateExtractor):
    def __init__(self, fname):
        with open(fname) as f:
            self.template = self.compile_template(f.read())

    def render(self, variables):
        return self.template.render(**variables)

class TemplaterFromField(TemplateExtractor):
    def __init__(self, field_name):
        self.field_name = field_name
    
    def render(self, variables):
        template_str = variables[self.field_name]
        template = self.compile_template(template_str)
        return template.render(**variables)

def setup_messages(initial_state):
    content = initial_state.system_prompt if initial_state.system_prompt else "You are a helpful AI assistant."
    return [{"role": "system", "content": content}]

class Templater:
    def __init__(self, output, concurrency=1):
        self.output = output
        self.concurrency = concurrency

    @contextmanager
    def get_output(self):
        if self.output == None:
            yield sys.stdout
        else:
            with open(self.output, 'w') as out:
                yield out

    def stream_prompts(self, template_renderer, variable_streamer):
        for variables in variable_streamer.stream():
            yield variables, template_renderer.render(variables)

    def evaluate_prompt(self, server, messages, mp, stream_processor, prompt):
        variables, prompt = prompt
        messages = messages + [mp.process_user_prompt(prompt)]
        while True:
            chunk_stream = server.send_chat_completion(messages)
            cot_stream = stream_processor.process_stream(chunk_stream)
            response = dict(
                process_streaming_response(
                    cot_stream,
                    NullFormatter(),
                    False
                )
            )

            if TagTypes.Tool_calls in response:
                tc = response[TagTypes.Tool_calls]
                messages.append(
                    mp.process_tool_request(tc)
                )
                tool_resp = server.process_tool_call(tc)
                messages.append(
                    mp.process_tool_response(tool_resp)
                )

            elif TagTypes.Content in response:
                return variables, response[TagTypes.Content]

            else:
                return variables, None

    def run(self, initial_state, server, stream_processor, message_processor, template_renderer, variable_streamer):
        responses = self.stream_results(initial_state, server, stream_processor, message_processor, template_renderer, variable_streamer)
        with self.get_output() as out:
            for vs, response in responses:
                vs['response'] = response
                print(json.dumps(vs), file=out)

    def stream_results(self, initial_state, server, stream_processor, message_processor, template_renderer, variable_streamer):
        prompt_stream = self.stream_prompts(template_renderer, variable_streamer)

        messages = setup_messages(initial_state)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            def execute(prompt):
                return executor.submit(self.evaluate_prompt, 
                                server, messages, 
                                message_processor, stream_processor, 
                                prompt)

            # Build the original batch of documents
            futures = []
            for prompt in islice(prompt_stream, self.concurrency * 2):
                futures.append(execute(prompt))

            while futures:
                done, not_done = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
                futures = list(not_done)
                for future in done:
                    yield future.result()

                    try:
                        futures.append(execute(next(prompt_stream)))
                    except StopIteration:
                        pass

