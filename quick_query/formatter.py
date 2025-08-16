import json
from itertools import groupby
import sys

from .openapi import TagTypes

class MessageFormatter:
    def __init__(self, in_block, out_block):
        if isinstance(in_block, str):
            in_block = open(in_block, 'w')

        self.in_block = in_block
        if isinstance(in_block, str):
            out_block = open(out_block, 'w')

        self.out_block = out_block

    def print_in_block(self, message: str):
        """Takes a message, formats it for terminal output, and prints it."""
        raise NotImplementedError()

    def print_out_block(self, message: str):
        """Takes a message, formats it for terminal output, and prints it."""
        raise NotImplementedError()


class RawTextFormatter(MessageFormatter):
    """Formats messages as raw text."""
    def print_in_block(self, message: str):
        """Prints the message as raw text."""
        self.in_block.write(message)
        self.in_block.flush()

    def print_out_block(self, message: str):
        self.out_block.write(message)
        self.out_block.flush()

class MarkdownFormatter(MessageFormatter):
    """Formats messages as markdown using the rich library."""

    def __init__(self, in_block, out_block):
        """Formats and prints the message as markdown."""
        super().__init__(in_block, out_block)
        from rich.console import Console
        self.out_block_console = Console(file=self.out_block)

    def print_in_block(self, message: str):
        """Formats and prints the message as markdown."""
        self.in_block.write(message)
        self.in_block.flush()

    def print_out_block(self, message: str):
        from rich.markdown import Markdown
        markdown = Markdown(message)
        self.out_block_console.print(markdown)

def get_formatter(in_block_path, format_markdown):
    if format_markdown:
        return MarkdownFormatter(in_block_path, sys.stdout)
    else:
        return RawTextFormatter(in_block_path, sys.stdout)

def process_streaming_response(
    cot_token_stream, 
    formatter,
    needs_buffering,
    include_cot_in_message=False
):
    for tag_type, group in groupby(cot_token_stream, key=lambda x: x[0]):
        # Space out between thinking and non thinking blocks
        if tag_type == TagTypes.Content:
            formatter.print_in_block('\n\n')

        response = []
        for i, (_, v) in enumerate(group):
            response.append(v)
            match tag_type:
                case TagTypes.Reasoning:
                    formatter.print_in_block(v)
                case TagTypes.Content if not needs_buffering:
                    formatter.print_out_block(v)
                case _:
                    pass

        if tag_type == TagTypes.Content and needs_buffering:
            formatter.print_out_block(''.join(response))

        if tag_type == TagTypes.Tool_calls:
            tool_call = {"id": '', "name": '', "arguments": ""}
            for v in response:
                for k, v in json.loads(v).items():
                    tool_call[k] += v

            formatter.print_in_block(f'\n\n* Tool Call: {tool_call["name"]}\n')
            yield tag_type, tool_call
        else:
            yield tag_type, ''.join(response)

