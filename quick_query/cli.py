#!/usr/bin/env python3
from typing import Optional, Dict, List, Any, Generator
from pathlib import Path
import argparse
import os
import select
import sys

from quick_query.openapi import OpenAIServer, get_model_id
from quick_query.chat import chat
from quick_query.streaming_response import StreamProcesser
from quick_query.config import load_toml_file, load_toml_prompt, read_api_conf
from quick_query.formatter import get_formatter
from quick_query.prompter import run_prompt

def try_read_stdin() -> str | None:
    """Try to read from standard input without blocking.
    
    Uses select to check if input is available. Returns the input if available,
    otherwise returns None.
    """
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read()
    else:
        return None

def list_prompts(args):
    print("Available system prompts:")
    system_data = load_toml_file(args.system_prompt_file)
    for key in system_data:
        print(f"  {key}")

    print("\nAvailable user prompts:")
    user_data = load_toml_file(args.user_prompt_file)
    for key in user_data:
        print(f"  {key}")

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

def create_user_prompt(args):
    user_prompt = None
    if args.user_prompt_file and args.user_prompt_name:
        user_prompt = load_toml_prompt(
            args.user_prompt_file,
            args.user_prompt_name
        )

    return user_prompt

def setup_api_params(args):
    if args.host is None:
        conf = read_api_conf(
            args.conf_file,
            args.server
        )
        args.host = conf.get("host")
        args.api_key = args.api_key or conf.get("api_key")
        args.model = args.model or conf.get("model")

    if args.model is None:
        args.model = get_model_id(
            args.host,
            args.api_key
        )

    return OpenAIServer(args.host, args.api_key, args.model)

class InitialState:
    def __init__(self, system_prompt, user_prompt, cli_prompt, stdin_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.cli_prompt = cli_prompt
        self.stdin_prompt = stdin_prompt

def main(args) -> None:
    """
    Main execution flow for the script.
    """
    
    server = setup_api_params(args)
    stream_processer = StreamProcesser(args.cot_token, args.min_chunk_size)
    formatter = get_formatter(args.cot_block_fd, args.format_markdown)

    initial_state = InitialState(
        create_system_prompt(args),
        create_user_prompt(args),
        try_read_stdin(),
        args.prompt)

    if args.chat:
        chat(initial_state, server, stream_processer, formatter, needs_buffering=args.format_markdown)

    else:
        run_prompt(initial_state, server, stream_processer, formatter, needs_buffering=args.format_markdown)
        
def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "quick-query"
    system_prompt_file= config_dir / "prompts.toml"
    user_prompt_file: Path = config_dir / "user_prompts.toml"
    conf_file: Path = config_dir / "conf.toml"

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Query an OpenAI-compatible endpoint"
    )
    parser.add_argument(
        "-p",
        "--prompt",
        required=not "-c" in sys.argv and not '--list-prompts' in sys.argv,
        help="The user's prompt"
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
        "--user-prompt-file",
        default=str(user_prompt_file),
        help="Path to TOML file containing user prompts"
    )
    parser.add_argument(
        "--user-prompt-name",
        default=None,
        help="Name of the user prompt section in the TOML file"
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
        "--host",
        default=None,
        help="API endpoint base URL"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for authentication"
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model identifier"
    )
    parser.add_argument(
        "-c",
        "--chat",
        action="store_true",
        help="Enter interactive chat mode"
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
        "--list-prompts",
        action="store_true",
        help="List all available system and user prompts and exit"
    )
    parser.add_argument(
        "--cot-token",
        default="think",
        help="Specifies the tag name for chain-of-thought."
    )
    parser.add_argument(
        "--min-chunk-size",
        default=10,
        type=int,
        help="Specifies the minimum characters to emit for stream."
    )

    return parser.parse_args()

def cli_entrypoint():
    args = parse_arguments()
    if args.list_prompts:
        list_prompts(args)
        sys.exit(0)

    main(args)

if __name__ == "__main__":
    cli_entrypoint()
