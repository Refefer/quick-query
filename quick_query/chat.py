import readline
from quick_query.formatter import process_streaming_response

def get_user_input(messages, orig_message_len):
    multiline = False
    buffer = []
    while True:
        user_input = input("> ").strip()
        if not multiline:
            print('=' * 10)
        
        if len(user_input) == 0:
            continue
        
        maybe_command = user_input.split(None, 1)[0].lower()
        match maybe_command:
            case "/reset":
                messages[:] = messages[:orig_message_len]

            case "/save":
                path = user_input[6:]
                with open(path, 'w') as out:
                    for message in messages:
                        print(f"Role: {message['role']}\n{message['content']}\n", file=out)

                print(f"Saved to {path}")

            case "/undo":
                if len(messages) > 2:
                    messages[:] = messages[:-2]

            case "/redo":
                if len(messages) > 2:
                    buffer.append(messages[-2]['content'])
                    messages[:] = messages[:-2]
                    break

            case "/m":
                if multiline:
                    break

                multiline = not multiline

            case _:
                buffer.append(user_input)
                if not multiline:
                    break

    return '\n'.join(buffer)

def construct_initial_user_prompt(initial_state):
    prompt = []
    if initial_state.user_prompt:
        prompt.append(initial_state.user_prompt)

    if initial_state.cli_prompt:
        prompt.append(initial_state.cli_prompt)

    if initial_state.stdin_prompt:
        prompt.append(initial_state.stdin_prompt)

    if len(prompt) > 0:
        return '\n'.join(prompt)

    return None

def setup_messages(initial_state):
    messages = []
    if initial_state.system_prompt:
        messages.append({"role": "system", "content": initial_state.system_prompt})
    
    user_prompt = construct_initial_user_prompt(initial_state)
    if user_prompt is not None:
        messages.append({"role": "user", "content": user_prompt})

    return messages

def chat(
    initial_state,
    server,
    stream_processer,
    formatter,
    needs_buffering
):
    messages = setup_messages(initial_state)
    orig_message_len = len(messages)
    try:
        while True:
            if len(messages) == 0 or messages[-1]['role'] != 'user':
                user_input = get_user_input(messages, orig_message_len)
                messages.append({"role": "user", "content": user_input})

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


