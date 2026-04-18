from __future__ import annotations

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("scheduled-agent-mcp", instructions="Use these tools for deterministic alert scoring.")


@mcp.tool()
def keyword_score(text: str) -> int:
    """Return a simple urgency score based on alert keywords in text."""
    lowered = text.lower()
    score = 0
    for keyword, weight in {
        "error": 3,
        "failed": 3,
        "incident": 4,
        "urgent": 4,
        "warning": 2,
        "delayed": 1,
        "degraded": 2,
    }.items():
        if keyword in lowered:
            score += weight
    return score


@mcp.tool()
def suggest_audience(score: int) -> str:
    """Map an urgency score to a human-readable notification audience."""
    if score >= 6:
        return "high-priority responders"
    if score >= 3:
        return "team channel"
    return "no broad notification"


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
