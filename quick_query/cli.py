#!/usr/bin/env python3
from typing import Optional, Dict, List, Any, Generator
from pathlib import Path
import argparse
import os
import select
import sys

from quick_query.openapi import OpenAIServer, get_model_id
from quick_query.chat import Chat
from quick_query.streaming_response import StreamProcesser
from quick_query.config import load_toml_file, load_toml_prompt, read_model, load_tools_from_toml
from quick_query.formatter import get_formatter
from quick_query.prompter import run_prompt
from quick_query.message import MessageProcessor

def try_read_stdin() -> str | None:
    """Try to read from standard input without blocking.
    
    Uses select to check if input is available. Returns the input if available,
    otherwise returns None.
    """
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read()
    else:
        return None

def hr_rule():
    print("=" *20)

def list_settings(args):
    if args.system_prompts:
        print("Available system prompts:")
        system_data = load_toml_file(args.system_prompt_file)
        for name, d in system_data.items():
            prompt = d['prompt']
            print(f"Prompt Name: {name}")
            hr_rule()
            print(f"Content: {prompt}")
            hr_rule()
            print()

    if args.models:
        models = load_toml_file(args.conf_file)
        for config_name, details in models.items():
            print(f"Config: {config_name}")
            for key, value in details.items():
                if key == 'api_key':
                    continue
                print(f" -{key}: {value}")

            hr_rule()
            print()

def create_system_prompt(args):
    system_prompt = None
    if args.system_prompt_file and args.system_prompt_name:
        system_prompt = load_toml_prompt(
            args.system_prompt_file,
            args.system_prompt_name
        )
        if not system_prompt:
            return

    return system_prompt

def setup_api_params(args):
    conf = read_model(
        args.conf_file,
        args.server
    )
    creds = conf['credentials']
    host = creds['host']
    api_key = creds['api_key']
    model = conf.get("model")
    structured_streaming = conf.get('structured_streaming', True)

    if model is None:
        model = get_model_id(host, api_key)

    tools_to_load = []
    if args.tools is not None:
        tools_to_load.append(args.tools)

    model_tools = conf.get('tools')
    if model_tools is not None:
        if isinstance(model_tools, str):
            model_tools = [model_tools]

        tools_to_load.extend(model_tools)

    tools = {}
    for tool_spec in tools_to_load:
        tools = load_tools_from_toml(tools, tool_spec)

    tools = tools if tools else None

    return OpenAIServer(host, api_key, model, args.cot_token, structured_streaming, tools)

class InitialState:
    def __init__(self, system_prompt, stdin_prompt=None, cli_prompt=None, prompt_file=None):
        self.system_prompt = system_prompt
        self.stdin_prompt = stdin_prompt
        self.cli_prompt = cli_prompt

        if prompt_file is not None:
            with open(prompt_file) as f:
                self.cli_prompt = f.read()

def main(args) -> None:
    """
    Main execution flow for the script.
    """
    
    server = setup_api_params(args)
    stream_processer = StreamProcesser(args.cot_token, args.min_chunk_size)
    formatter = get_formatter(args.cot_block_fd, args.format_markdown)

    mp = MessageProcessor(args.re2)
    match args.mode:
        case "chat":
            initial_state = InitialState(create_system_prompt(args))

            chat = Chat(initial_state, server, stream_processer, formatter, mp, needs_buffering=args.format_markdown)
            chat.run()

        case "template":
            try:
                import jinja2
            except ImportError:
                print("Jinja is not installed!")
                sys.exit(1)

            import quick_query.template as template
            initial_state = InitialState(create_system_prompt(args))
            if args.template_from_file is not None:
                template_extractor = template.TemplateFileExtractor(args.template_from_file)
            else:
                template_extractor = template.TemplaterFromField(args.template_from_field)

            if args.variables is not None:
                var_stream = template.JsonArrayStreamer(args.variables)
            else:
                var_stream = template.JsonlStreamer(args.variables_from_file)

            templater = template.Templater(args.output, args.concurrency)
            templater.run(initial_state, server, stream_processer, mp, template_extractor, var_stream)

        case _:
            initial_state = InitialState(
                create_system_prompt(args),
                try_read_stdin(),
                args.prompt,
                args.prompt_file)

            run_prompt(initial_state, server, stream_processer, formatter, mp, needs_buffering=args.format_markdown)

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "quick-query"
    system_prompt_file= config_dir / "prompts.toml"
    conf_file: Path = config_dir / "conf.toml"

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Query an OpenAI-compatible endpoint"
    )

    parser.add_argument(
        "--system-prompt-file",
        default=str(system_prompt_file),
        help="Path to TOML file containing system prompts"
    )
    parser.add_argument(
        "-sp",
        "--system-prompt-name",
        default='default',
        help="Name of the system prompt section in the TOML file"
    )
    parser.add_argument(
        "--conf-file",
        default=str(conf_file),
        help="Path to TOML file containing configuration"
    )
    parser.add_argument(
        "-s",
        dest="server",
        default="default",
        help="Name of the server to connect to in conf.toml"
    )
    parser.add_argument(
        "-t", 
        "--tools",
        dest="tools",
        help="Loads a set of tools from a toml file."
    )

    parser.add_argument(
        "-m",
        "--format-markdown",
        action="store_true",
        help="If enabled, formats output for the terminal in markdown.  If the library isn't installed, prints as text"
    )

    parser.add_argument(
        "--cot-block-fd",
        default='/dev/tty',
        help="Where to emit cot blocks.  Default is /dev/tty."
    )
    parser.add_argument(
        "--cot-token",
        default="think",
        help="Specifies the tag name for chain-of-thought."
    )
    parser.add_argument(
        "--re2",
        action="store_true",
        help="If specified, uses re-think prompting."
    )

    parser.add_argument(
        "--min-chunk-size",
        default=10,
        type=int,
        help="Specifies the minimum characters to emit for stream."
    )

    subparsers = parser.add_subparsers(
        dest="mode", 
        required=True, 
        help="Which mode to run qq")

    # Standard one prompt, one response piped to stdout
    completion = subparsers.add_parser("completion", help="Performs a completion task.")

    group = completion.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-p",
        "--prompt",
        help="The user's prompt"
    )

    group.add_argument(
        "-f",
        "--prompt-file",
        help="Load the prompt from a file"
    )

    # Interactive mode
    chat = subparsers.add_parser("chat", help="Uses qq in interactive chat mode")

    lister = subparsers.add_parser(
        "list",
        help="List details about the underlying configs"
    )

    lister.add_argument(
        "--system-prompts",
        action="store_true",
        help="Lists system prompts currently configured"
    )

    lister.add_argument(
        "--models",
        action="store_true",
        help="Lists the models configured on the system"
    )

    # Runs in template mode
    template = subparsers.add_parser("template", help="Runs qq in template mode")

    group = template.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--template-from-file",
        dest="template_from_file",
        help="File containing the jinja template."
    )

    group.add_argument(
        "--template-from-field",
        dest="template_from_field",
        help="Reads the template from the specified field on the variables dictionary."
    )

    group = template.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--variables",
        "-v",
        default=None,
        help="Inline JSON structure for jinja2 variables."
    )

    group.add_argument(
        "--variables-from-file",
        "-vj",
        default=None,
        help="Read variables from jsonl file.  If set to '-', reads from stdin "
    )

    template.add_argument(
        "-o",
        "--output",
        default=None,
        help="Where to output the results.  If omitted, writes to stdout.  Output format is in JSONL format with the following"
             'keys: "prompt", "variables", "response"'
    )

    import multiprocessing
    template.add_argument(
        "-c",
        "--concurrency",
        default=multiprocessing.cpu_count(),
        type=int,
        help="Where to output the results.  If omitted, writes to stdout.  Output format is in JSONL format with the following"
    )

    return parser.parse_args()

def cli_entrypoint():
    args = parse_arguments()
    if args.mode == 'list':
        list_settings(args)
        sys.exit(0)

    main(args)

if __name__ == "__main__":
    cli_entrypoint()
