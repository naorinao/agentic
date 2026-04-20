from __future__ import annotations

import json

from app.schemas import AgentDecision, CompiledSlackSection, CompiledSlackTemplate, GeneratedSlackSection, SlackMessage, SlackTemplate


def compile_slack_template(template: SlackTemplate | None) -> CompiledSlackTemplate | None:
    if template is None:
        return None

    sections = [
        CompiledSlackSection(
            key=section.key,
            label=section.label,
            type=section.type,
            required_level=section.required_level,
            instruction=section.instruction,
            min_chars=section.min_chars,
            min_items=section.min_items,
            max_items=section.max_items,
        )
        for section in template.sections
    ]
    allowed_keys = [section.key for section in sections]
    required_keys = [section.key for section in sections if section.required_level == "hard"]
    prompt_hints: list[str] = []
    if template.tone:
        prompt_hints.append(f"Tone: {template.tone}")
    if template.audience:
        prompt_hints.append(f"Audience: {template.audience}")

    return CompiledSlackTemplate(
        title=template.title,
        sections=sections,
        allowed_keys=allowed_keys,
        required_keys=required_keys,
        prompt_hints=prompt_hints,
    )


def build_slack_template_prompt(template: CompiledSlackTemplate | None) -> str:
    if template is None:
        return (
            "No structured Slack template provided. "
            "If you decide to notify Slack, populate slack_message.text directly and leave slack_sections as null."
        )

    example_items: list[str] = []
    for section in template.sections:
        if section.type == "paragraph":
            example_items.append(f'{{"key":"{section.key}","content":"..."}}')
        else:
            example_items.append(f'{{"key":"{section.key}","content":["..."]}}')
    example_shape = "[" + ",".join(example_items) + "]"

    lines = [
        "Structured Slack template provided.",
        "If you decide to notify Slack, Return slack_sections as a JSON array using only the allowed section keys below and leave slack_message as null.",
        f"Allowed keys: {json.dumps(template.allowed_keys)}",
        f"Required keys: {json.dumps(template.required_keys)}",
        f"Example shape: {example_shape}",
        "Do not include template metadata fields like title, tone, audience, sections, or required_keys inside slack_sections.",
        "Each item in slack_sections must contain exactly one key and one content field.",
        f"Title: {template.title}",
    ]
    lines.extend(template.prompt_hints)

    lines.append("Sections:")
    for section in template.sections:
        attributes = [
            f"key={section.key}",
            f"label={section.label}",
            f"type={section.type}",
            f"required_level={section.required_level}",
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


def _normalize_section_map(
    sections: list[GeneratedSlackSection],
) -> tuple[dict[str, str | list[str]], list[str]]:
    normalized: dict[str, str | list[str]] = {}
    duplicates: list[str] = []
    for section in sections:
        if section.key in normalized:
            duplicates.append(section.key)
            continue
        normalized[section.key] = section.content
    return normalized, duplicates


def validate_slack_sections(template: CompiledSlackTemplate, sections: list[GeneratedSlackSection]) -> list[str]:
    errors: list[str] = []
    normalized, duplicates = _normalize_section_map(sections)
    if duplicates:
        errors.append(f"Duplicate slack_sections keys: {', '.join(sorted(set(duplicates)))}.")

    known_keys = set(template.allowed_keys)
    for section in template.sections:
        value = normalized.get(section.key)
        if value is None:
            if section.required_level == "hard":
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
        if not items and section.required_level == "soft":
            continue
        if section.required_level == "hard" and not items:
            errors.append(f"Section '{section.key}' cannot be empty.")
            continue
        if section.min_items is not None and len(items) < section.min_items:
            errors.append(f"Section '{section.key}' must contain at least {section.min_items} items.")
        if section.max_items is not None and len(items) > section.max_items:
            errors.append(f"Section '{section.key}' cannot contain more than {section.max_items} items.")

    extra_keys = sorted(set(normalized) - known_keys)
    if extra_keys:
        errors.append(f"Unknown slack_sections keys: {', '.join(extra_keys)}.")

    return errors


def render_slack_message(template: CompiledSlackTemplate, sections: list[GeneratedSlackSection]) -> SlackMessage:
    errors = validate_slack_sections(template, sections)
    if errors:
        raise ValueError("Invalid structured Slack content: " + " ".join(errors))

    normalized, _ = _normalize_section_map(sections)
    lines = [f"*{template.title.strip()}*"]
    for section in template.sections:
        value = normalized.get(section.key)
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


def finalize_slack_decision(decision: AgentDecision, template: CompiledSlackTemplate | None) -> AgentDecision:
    if not decision.should_notify_slack:
        return decision.model_copy(update={"slack_sections": None, "slack_message": None})

    if template is None:
        if decision.slack_message is None or not decision.slack_message.text.strip():
            raise ValueError("Agent requested Slack notification without a structured template but did not provide slack_message.text.")
        return decision.model_copy(update={"slack_sections": None})

    if decision.slack_sections is None:
        raise ValueError("Agent requested Slack notification with a structured template but did not provide slack_sections.")

    slack_message = render_slack_message(template, decision.slack_sections)
    return decision.model_copy(update={"slack_message": slack_message})
