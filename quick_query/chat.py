import readline
from quick_query.formatter import process_streaming_response

class Command:
    cmd = None

    # Returns: (break the loop, multiline)
    def process(self, user_input, messages, buffer, orig_message_len):
        raise NotImplementedError()

    def help(self):
        return f"/{self.cmd}"

class Reset(Command):
    cmd = "reset"

    def process(self, user_input, messages, buffer, orig_message_len):
        messages[:] = messages[:orig_message_len]
        return True

class Save(Command):
    cmd = "save"

    def process(self, user_input, messages, buffer, orig_message_len):
        path = user_input[6:]
        with open(path, 'w') as out:
            for message in messages:
                print(f"Role: {message['role']}\n{message['content']}\n", file=out)

        print(f"Saved to {path}")
        return True

class Redo(Command):
    cmd = "redo"

    def process(self, user_input, messages, buffer, orig_message_len):
        if len(messages) > 2:
            buffer.append(messages[-2]['content'])
            messages[:] = messages[:-2]
            return False

        return True

class Undo(Command):
    cmd = "undo"

    def process(self, user_input, messages, buffer, orig_message_len):
        if len(messages) > 2:
            messages[:] = messages[:-2]

        return True

class Multiline(Command):
    cmd = "multiline"
    def process(self, user_input, messages, buffer, orig_message_len):
        while True:
            user_input = read_input()
            maybe_command = parse_cmd(user_input)
            if maybe_command == self.cmd:
                return False

            buffer.append(user_input)

def parse_cmd(user_input):
    pieces = user_input.split(None, 1)[0].lower()
    pieces = pieces.split('/', 1)
    if len(pieces) == 2:
        return pieces[1]
    return None

def read_input():
    while True:
        user_input = input("> ").strip()
        if len(user_input) == 0:
            continue

        return user_input

def get_user_input(messages, orig_message_len, commands):
    buffer = []
    while True:
        user_input = read_input()
        print('=' * 10)

        maybe_command = parse_cmd(user_input)

        cmd = commands.get(maybe_command)
        if cmd is not None:
            should_continue = cmd.process(user_input, messages, buffer, orig_message_len) 
            if should_continue:
                continue

            break
        else:
            buffer.append(user_input)
            break

    return '\n'.join(buffer)

def construct_initial_user_prompt(initial_state):
    prompt = []
    if initial_state.cli_prompt:
        prompt.append(initial_state.cli_prompt)

    if initial_state.stdin_prompt:
        prompt.append(initial_state.stdin_prompt)

    if len(prompt) > 0:
        return '\n'.join(prompt)

    return None

def setup_messages(initial_state, message_processor):
    messages = []
    if initial_state.system_prompt:
        messages.append({"role": "system", "content": initial_state.system_prompt})
    
    user_prompt = construct_initial_user_prompt(initial_state)
    if user_prompt is not None:
        message = message_processor.process_user_prompt(user_prompt)
        messages.append(message)

    return messages

COMMANDS = [
    Reset,
    Save,
    Undo,
    Redo,
    Multiline
]
def chat(
    initial_state,
    server,
    stream_processer,
    formatter,
    message_processor,
    needs_buffering
):

    messages = setup_messages(initial_state, message_processor)
    orig_message_len = len(messages)
    commands = {cmd.cmd: cmd() for cmd in COMMANDS}
    try:
        while True:
            if len(messages) == 0 or messages[-1]['role'] != 'user':
                print('Commands:', ', '.join('/' + name for name in commands))
                user_input = get_user_input(messages, orig_message_len, commands)
                message = message_processor.process_user_prompt(user_input)
                messages.append(message)

            # Get streaming response
            chunk_stream = server.send_chat_completion(messages)

            # Processes streaming response into cot blocks
            cot_stream = stream_processer.process_stream(chunk_stream)

            # run the streaming results into our formatter for output
            response = process_streaming_response(cot_stream, formatter, needs_buffering)

            # Add the response message
            messages.append({"role": "assistant", "content": response})
            if not response.endswith('\n'):
                print()

            print('=' * 10)

    except (KeyboardInterrupt, EOFError):
        print("\nExiting chat.")


