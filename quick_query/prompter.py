from quick_query.formatter import process_streaming_response

def setup_messages(initial_state):
    messages = []
    if initial_state.system_prompt:
        messages.append({"role": "system", "content": initial_state.system_prompt})

    prompt = initial_state.cli_prompt
    if initial_state.stdin_prompt is not None:
        prompt = f"{prompt}\n\n{initial_state.stdin_prompt}".strip()

    if initial_state.user_prompt:
        prompt = f"{initial_state.user_prompt}\n{prompt}"

    messages.append({"role": "user", "content": prompt})
    return messages


def run_prompt(
    initial_state,
    server,
    stream_processer,
    formatter,
    needs_buffering
):

    # Build messages
    messages = setup_messages(initial_state)

    # Get streaming response
    chunk_stream = server.send_chat_completion(messages)

    # Processes streaming response into cot blocks
    cot_stream = stream_processer.process_stream(chunk_stream)

    # run the streaming results into our formatter for output
    response = process_streaming_response(cot_stream, formatter, needs_buffering)

