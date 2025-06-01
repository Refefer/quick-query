
def create_prefixes(think_tag):
    start_tag = f'<{think_tag}>'
    end_tag = f'</{think_tag}>'
    prefixes = set()
    for tag in (start_tag, end_tag):
        for i in range(1, len(tag) - 1):
            prefixes.add(tag[:i])

    return tuple(prefixes)

def stream_cot_tokens(chunk_streamer, think_tag):
    if think_tag is None:
        yield from chunk_streamer 
    else:
        prefixes = create_prefixes(think_tag)
        buffer = ''
        for chunk in chunk_streamer:
            buffer = chunk if len(buffer) == 0 else buffer + chunk
            if not buffer.endswith(prefixes):
                yield buffer
                buffer = ''

        if len(buffer) > 0:
            yield buffer

def stream_cot_blocks(token_streamer, think_tag):
    if think_tag is None:
        for c in token_stream:
            yield False, c
    else:
        start_block, end_block = f'<{think_tag}>', f'</{think_tag}>'
        in_block = False
        for chunk in token_streamer:
            buffer = chunk
            while buffer:
                if start_block in buffer:
                    before, after = chunk.split(start_block, 1)
                    yield in_block, before
                    in_block = True
                    yield in_block, start_block
                    buffer = after
                    continue

                if end_block in buffer:
                    before, after = chunk.split(end_block, 1)
                    yield in_block, before
                    yield in_block, end_block
                    yield in_block, '\n'

                    in_block = False
                    buffer = after
                    continue

                yield in_block, buffer
                buffer = ''

def join_buffer(buffer):
    return buffer[0] if len(buffer) == 1 else ''.join(buffer)

def stream_min_chunks(
    chunk_stream,
    min_chunk_size=0
):
    buffer = []
    buff_len = 0
    for chunk in chunk_stream:
        buffer.append(chunk)
        buff_len += len(chunk)
        if buff_len >= min_chunk_size:
            yield join_buffer(buffer)
            buffer.clear()
            buff_len = 0

    if buff_len > 0:
        yield join_buffer(buffer)

class StreamProcesser:
    def __init__(self, think_tag, min_chunk_size=0):
        self.think_tag = think_tag
        self.min_chunk_size = min_chunk_size

    def process_stream(self, chunk_stream):
        # Minimum chunk size
        chunk_stream = stream_min_chunks(chunk_stream)

        # Make sure that if we have cot tokens, start or stop tag is within a full buffer
        cot_chunk_stream = stream_cot_tokens(chunk_stream, self.think_tag)

        # Streams chunks while recording whether we are in or outside of a think block
        return stream_cot_blocks(cot_chunk_stream, self.think_tag)
