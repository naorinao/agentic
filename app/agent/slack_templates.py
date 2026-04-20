from __future__ import annotations

from app.schemas import AgentDecision, SlackMessage, SlackTemplate


def build_slack_template_prompt(template: SlackTemplate | None) -> str:
    if template is None:
        return (
            "No structured Slack template provided. "
            "If you decide to notify Slack, populate slack_message.text directly and leave slack_content as null."
        )

    lines = [
        "Structured Slack template provided.",
        "If you decide to notify Slack, populate slack_content using the exact section keys below and leave slack_message as null.",
        f"Title: {template.title}",
    ]
    if template.tone:
        lines.append(f"Tone: {template.tone}")
    if template.audience:
        lines.append(f"Audience: {template.audience}")

    lines.append("Sections:")
    for section in template.sections:
        attributes = [
            f"key={section.key}",
            f"label={section.label}",
            f"type={section.type}",
            f"required={str(section.required).lower()}",
        ]
        if section.min_chars is not None:
            attributes.append(f"min_chars={section.min_chars}")
        if section.min_items is not None:
            attributes.append(f"min_items={section.min_items}")
        if section.max_items is not None:
            attributes.append(f"max_items={section.max_items}")
        if section.instruction:
            attributes.append(f"instruction={section.instruction}")
        lines.append(f"- {', '.join(attributes)}")

    return "\n".join(lines)


def validate_slack_content(template: SlackTemplate, content: dict[str, str | list[str]]) -> list[str]:
    errors: list[str] = []
    known_keys = {section.key for section in template.sections}

    for section in template.sections:
        value = content.get(section.key)
        if value is None:
            if section.required:
                errors.append(f"Missing required section '{section.key}'.")
            continue

        if section.type == "paragraph":
            if not isinstance(value, str):
                errors.append(f"Section '{section.key}' must be a string.")
                continue

            text = value.strip()
            if not text:
                errors.append(f"Section '{section.key}' cannot be empty.")
                continue
            if section.min_chars is not None and len(text) < section.min_chars:
                errors.append(f"Section '{section.key}' must be at least {section.min_chars} characters.")
            continue

        if not isinstance(value, list):
            errors.append(f"Section '{section.key}' must be a list of strings.")
            continue

        if not all(isinstance(item, str) for item in value):
            errors.append(f"Section '{section.key}' must contain only strings.")
            continue

        items = [item.strip() for item in value if item.strip()]
        if len(items) != len(value):
            errors.append(f"Section '{section.key}' cannot contain empty list items.")
            continue
        if not items and not section.required:
            continue
        if section.required and not items:
            errors.append(f"Section '{section.key}' cannot be empty.")
            continue
        if section.min_items is not None and len(items) < section.min_items:
            errors.append(f"Section '{section.key}' must contain at least {section.min_items} items.")
        if section.max_items is not None and len(items) > section.max_items:
            errors.append(f"Section '{section.key}' cannot contain more than {section.max_items} items.")

    extra_keys = sorted(set(content) - known_keys)
    if extra_keys:
        errors.append(f"Unknown slack_content sections: {', '.join(extra_keys)}.")

    return errors


def render_slack_message(template: SlackTemplate, content: dict[str, str | list[str]]) -> SlackMessage:
    errors = validate_slack_content(template, content)
    if errors:
        raise ValueError("Invalid structured Slack content: " + " ".join(errors))

    lines = [f"*{template.title.strip()}*"]
    for section in template.sections:
        value = content.get(section.key)
        if value is None:
            continue

        if section.type == "paragraph":
            lines.append("")
            lines.append(section.label.strip())
            lines.append(value.strip())
            continue

        items = [item.strip() for item in value if item.strip()]
        if not items:
            continue

        lines.append("")
        lines.append(section.label.strip())
        lines.extend(f"- {item}" for item in items)

    return SlackMessage(text="\n".join(lines))


def finalize_slack_decision(decision: AgentDecision, template: SlackTemplate | None) -> AgentDecision:
    if not decision.should_notify_slack:
        return decision.model_copy(update={"slack_content": None, "slack_message": None})

    if template is None:
        if decision.slack_message is None or not decision.slack_message.text.strip():
            raise ValueError("Agent requested Slack notification without a structured template but did not provide slack_message.text.")
        return decision.model_copy(update={"slack_content": None})

    if decision.slack_content is None:
        raise ValueError("Agent requested Slack notification with a structured template but did not provide slack_content.")

    slack_message = render_slack_message(template, decision.slack_content)
    return decision.model_copy(update={"slack_message": slack_message})
