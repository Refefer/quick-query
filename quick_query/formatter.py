import sys

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
):
    response = []
    if needs_buffering:
        out_message = []
        for in_block, chunk in cot_token_stream:
            response.append(chunk)
            if in_block:
                formatter.print_in_block(chunk)
            else:
                out_message.append(chunk)

        formatter.print_out_block(''.join(out_message))
    else:
        for in_block, chunk in cot_token_stream:
            response.append(chunk)
            if in_block:
                formatter.print_in_block(chunk)
            else:
                formatter.print_out_block(chunk)

    return ''.join(response)

