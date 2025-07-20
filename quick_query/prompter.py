from .openapi import TagTypes
from quick_query.formatter import process_streaming_response

def setup_messages(initial_state, mp):
    messages = []
    if initial_state.system_prompt:
        messages.append({"role": "system", "content": initial_state.system_prompt})

    prompt = initial_state.cli_prompt
    if initial_state.stdin_prompt is not None:
        prompt = f"{prompt}\n\n{initial_state.stdin_prompt}".strip()

    messages.append(mp.process_user_prompt(prompt))
    return messages


def run_prompt(
    initial_state,
    server,
    stream_processer,
    formatter,
    message_processor,
    needs_buffering
):

    # Build messages
    messages = setup_messages(initial_state, message_processor)

    while True:
        # Get streaming response
        chunk_stream = server.send_chat_completion(messages)

        # Processes streaming response into cot blocks
        cot_stream = stream_processer.process_stream(chunk_stream)

        # run the streaming results into our formatter for output
        response = dict(process_streaming_response(cot_stream, formatter, needs_buffering))

        # Check if there are tool calls
        if TagTypes.Tool_calls in response:
            tc = response[TagTypes.Tool_calls]
            messages.append(message_processor.process_tool_request(tc))
            response = server.process_tool_call(tc)
            message = message_processor.process_tool_response(response)
            messages.append(message)

            continue

        break
