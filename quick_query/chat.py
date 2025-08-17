import json
import pprint
from typing import Any, Callable, Dict, List, Optional
import readline

from quick_query.formatter import process_streaming_response
from .openapi import TagTypes


class Command:
    """Base class for chat commands."""

    cmd: Optional[str] = None

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Execute the command.

        Returns:
            bool: ``True`` if the chat loop should continue,
                  ``False`` to break out of the current input phase.
        """
        raise NotImplementedError()

    def help(self) -> str:
        """Return a short help string for the command."""
        return f"/{self.cmd}"


class Reset(Command):
    cmd = "reset"

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Reset the conversation to its original length."""
        chat.messages[:] = chat.messages[: chat.orig_message_len]
        return True

class Save(Command):
    cmd = "save"

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Save the current message history to a file."""
        path = user_input[6:].strip()
        with open(path, "w") as out:
            for message in chat.messages:
                print(json.dumps(message), file=out)

        print(f"Saved to {path}")
        return True


class Pretty(Command):
    cmd = "pretty"

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Pretty‑print all stored messages."""
        for message in chat.messages:
            pprint.pprint(message)

        return True


class Redo(Command):
    cmd = "redo"

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Redo the most recent user input that was undone."""
        if len(chat.messages) > 2:
            buffer.append(chat.messages[-2]["content"])
            chat.messages[:] = chat.messages[:-2]
            return False

        return True


class Undo(Command):
    cmd = "undo"

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Undo the last user‑assistant exchange."""
        if len(chat.messages) > 2:
            chat.messages[:] = chat.messages[:-2]

        return True


class Multiline(Command):
    cmd = "multiline"

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Collect multiline input until '/multiline' is entered again."""
        while True:
            line = chat.read_input()
            maybe_cmd = chat.parse_cmd(line)
            if maybe_cmd == self.cmd:
                return False

            buffer.append(line)


class ToolsToggle(Command):
    """Enable, disable, or list tools at runtime.

    Invoked as ``/tools <enable|disable|list> [tool_name]``.
    """

    cmd = "tools"

    def process(
        self,
        chat: "Chat",
        user_input: str,
        buffer: List[str],
    ) -> bool:
        """Handle three sub‑commands:
        
+        * ``/tools enable <tool_name>`` – turn a tool **on**
+        * ``/tools disable <tool_name>`` – turn a tool **off**
+        * ``/tools list`` – show every tool and whether it is enabled
        """
        parts = user_input.strip().split()
        if len(parts) < 2:
            print("Usage: /tools <enable|disable|list> [tool_name]")
            return True

        action = parts[1].lower()

        # ---- LIST sub‑command -------------------------------------------------
        if action == "list":
            self._list_tools(chat)
            return True  # stay in the main loop

        # ---- ENABLE / DISABLE ------------------------------------------------
        if len(parts) < 3:
            print(f"Usage: /tools {action} <tool_name>")
            return True
        tool_name = parts[2]

        if action not in {"enable", "disable"}:
            print("Action must be 'enable', 'disable', or 'list'.")
            return True

        tools_dict = getattr(chat.server, "tools", None)
        if not tools_dict:
            print("No tools are registered on the server.")
            return True

        if tool_name not in tools_dict:
            print(f"Tool `{tool_name}` not found. Run `/tools list` to see all names.")
            return True

        tool = tools_dict[tool_name]
        tool.enabled = (action == "enable")
        print(f"Tool `{tool_name}` has been {action}d.")
        return True

    def _list_tools(self, chat) -> None:
        """Print a nicely formatted table of all registered tools.
        Each line shows the tool name and a ✅/❌ indicator for its enabled state.
        """
        tools = getattr(chat.server, "tools", {})
        if not tools:
            print("No tools are registered on the server.")
            return

        print("\nAvailable tools:")
        for name, tool in sorted(tools.items()):
            enabled = getattr(tool, "enabled", True)
            status = "✅ enabled" if enabled else "❌ disabled"
            print(f"  {name:<20} {status}")

class Chat:
    """Encapsulates a conversational session with command handling."""

    def __init__(
        self,
        initial_state: Any,
        server: Any,
        stream_processor: Any,
        formatter: Any,
        message_processor: Any,
        needs_buffering: bool,
    ) -> None:
        """Create a new Chat instance.

        Args:
            initial_state: Object containing prompts and configuration.
            server: Backend that provides ``send_chat_completion`` and tool calls.
            stream_processor: Converts raw streaming chunks into higher‑level blocks.
            formatter: Formats processed blocks for display.
            message_processor: Handles conversion of raw text to chat messages.
            needs_buffering: Whether the formatter requires output buffering.
        """
        self.initial_state = initial_state
        self.server = server
        self.stream_processor = stream_processor
        self.formatter = formatter
        self.message_processor = message_processor
        self.needs_buffering = needs_buffering

        self.messages: List[Dict[str, Any]] = self._setup_messages()
        self.orig_message_len: int = len(self.messages)
        self.commands: Dict[str, Command] = {}

        for cmd_cls in (Reset, Save, Undo, Redo, Pretty, Multiline, ToolsToggle):
            self.add_command(cmd_cls())

    def _setup_messages(self) -> List[Dict[str, Any]]:
        """Initialize the message list based on the provided initial state."""
        msgs: List[Dict[str, Any]] = []
        if getattr(self.initial_state, "system_prompt", None):
            msgs.append(
                {"role": "system", "content": self.initial_state.system_prompt}
            )

        user_prompt = self._construct_initial_user_prompt()
        if user_prompt is not None:
            msgs.append(
                self.message_processor.process_user_prompt(user_prompt)
            )

        return msgs

    def _construct_initial_user_prompt(self) -> Optional[str]:
        """Combine CLI and stdin prompts from the initial state."""
        parts: List[str] = []
        if getattr(self.initial_state, "cli_prompt", None):
            parts.append(self.initial_state.cli_prompt)

        if getattr(self.initial_state, "stdin_prompt", None):
            parts.append(self.initial_state.stdin_prompt)

        return "\n".join(parts) if parts else None

    def add_command(self, command: Command) -> None:
        """Register a command instance with the chat."""
        if not command.cmd:
            raise ValueError("Command must define a non‑empty ``cmd`` attribute.")

        self.commands[command.cmd] = command

    def read_input(self) -> str:
        """Prompt the user for input, ignoring empty lines."""
        while True:
            user_input = input("> ").strip()
            if user_input:
                return user_input

    def parse_cmd(self, user_input: str) -> Optional[str]:
        """Extract a command name from the user input, if present."""
        pieces = user_input.split(None, 1)[0].lower()
        pieces = pieces.split("/", 1)
        return pieces[1] if len(pieces) == 2 else None

    def get_user_input(self) -> str:
        """Collect user input, handling commands and multiline mode."""
        buffer: List[str] = []
        while True:
            user_input = self.read_input()
            print("=" * 10)
            maybe_cmd = self.parse_cmd(user_input)
            cmd = self.commands.get(maybe_cmd)
            if cmd is not None:
                continue_loop = cmd.process(self, user_input, buffer)
                if continue_loop:
                    continue
                break

            else:
                buffer.append(user_input)
                break

        return "\n".join(buffer)

    def run(self) -> None:
        """Main chat loop that processes user input and model responses."""
        try:
            while True:
                if not self.messages or self.messages[-1]["role"] not in ("user", "tool"):
                    print(
                        "Commands:",
                        ", ".join("/" + name for name in self.commands),
                    )
                    user_input = self.get_user_input()
                    self.messages.append(
                        self.message_processor.process_user_prompt(user_input)
                    )

                chunk_stream = self.server.send_chat_completion(self.messages)
                cot_stream = self.stream_processor.process_stream(chunk_stream)
                response = dict(
                    process_streaming_response(
                        cot_stream,
                        self.formatter,
                        self.needs_buffering,
                    )
                )

                if TagTypes.Tool_calls in response:
                    tc = response[TagTypes.Tool_calls]
                    self.messages.append(
                        self.message_processor.process_tool_request(tc)
                    )
                    tool_resp = self.server.process_tool_call(tc)
                    self.messages.append(
                        self.message_processor.process_tool_response(tool_resp)
                    )
                else:
                    self.messages.append(
                        {"role": "assistant", "content": response["content"]}
                    )
                    if not self.messages[-1]["content"].endswith("\n"):
                        print()
                    print("=" * 10)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat.")
