from .openapi import TagTypes

def create_prefixes(think_tag):
    start_tag = f'<{think_tag}>'
    end_tag = f'</{think_tag}>'
    prefixes = set()
    for tag in (start_tag, end_tag):
        for i in range(1, len(tag) - 1):
            prefixes.add(tag[:i])

    return tuple(prefixes)

def join_buffer(buffer):
    return buffer[0] if len(buffer) == 1 else ''.join(buffer)

def stream_min_chunks(
    chunk_stream,
    min_chunk_size=0
):
    last_tag = None
    buffer = []
    buff_len = 0
    for tag_type, chunk in chunk_stream:
        if last_tag is None:
            last_tag = tag_type

        elif last_tag != tag_type or buff_len >= min_chunk_size:
            yield last_tag, join_buffer(buffer)
            buffer.clear()
            buffer_len = 0
            last_tag = tag_type

        if chunk is not None:
            buffer.append(chunk)
            buff_len += len(chunk)

    if buff_len > 0:
        yield last_tag, join_buffer(buffer)

def split_cot_to_reasoning(chunk_stream, cot_tag):
    start, end = f'<{cot_tag}>', f'</{cot_tag}>'
    prefixes = create_prefixes(cot_tag)
    b = ''
    in_reasoning = False
    for st, chunk in chunk_stream:
        if st == TagTypes.Content:
            b += chunk
            if not in_reasoning and start in b:
                in_reasoning = True
                left, right = b.split(start, 1)
                if left:
                    yield TagTypes.Content, left

                if right:
                    yield TagTypes.Reasoning, right

                b = ''

            elif in_reasoning and end in b:
                in_reasoning = False
                left, right = b.split(end, 1)
                if left:
                    yield TagTypes.Reasoning, left

                if right:
                    yield TagTypes.Content, right

                b = ''

            elif not b.endswith(prefixes):
                new_st = TagTypes.Reasoning if in_reasoning else TagTypes.Content
                yield new_st, b
                b = ''

        else:
            yield st, chunk

    if b:
        new_st = TagTypes.Reasoning if in_reasoning else TagTypes.Content
        yield new_st, b

class StreamProcesser:
    def __init__(self, think_tag, min_chunk_size=0):
        self.think_tag = think_tag
        self.min_chunk_size = min_chunk_size

    def process_stream(self, chunk_stream):
        if self.think_tag is not None:
            chunk_stream = split_cot_to_reasoning(chunk_stream, self.think_tag)

        # Minimum chunk size
        return stream_min_chunks(chunk_stream)
