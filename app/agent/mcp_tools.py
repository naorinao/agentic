from __future__ import annotations

import sys

from app.schemas import MCPConfig


def build_mcp_servers(config: MCPConfig):
    if not config.enabled:
        return []

    from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

    if config.transport == "stdio":
        command = sys.executable if config.command in {"python", "python3"} else config.command
        return [
            MCPServerStdio(
                command,
                args=config.args,
                tool_prefix=config.tool_prefix,
                include_instructions=config.include_instructions,
            )
        ]

    if not config.url:
        raise ValueError("mcp.url is required when using streamable-http transport")

    return [
        MCPServerStreamableHTTP(
            config.url,
            tool_prefix=config.tool_prefix,
            include_instructions=config.include_instructions,
        )
    ]
