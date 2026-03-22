from openai import OpenAI


def _estimate_tokens(text: str) -> int:
    # Approximation: ~1 token per 4 characters for English prose.
    return max(1, int(len(text or "") / 4))


def build_report_prompt(detections):
    return f"""
Detected issues: {detections}
Generate civil inspection report with summary, severity, causes, repair, prevention.
"""


def generate_report_with_usage(client, model_name, detections):
    prompt = build_report_prompt(detections)
    res = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
    )

    content = res.choices[0].message.content or ""
    usage = getattr(res, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)

    if prompt_tokens is None:
        prompt_tokens = _estimate_tokens(prompt)
    if completion_tokens is None:
        completion_tokens = _estimate_tokens(content)
    if total_tokens is None:
        total_tokens = int(prompt_tokens) + int(completion_tokens)

    return content, int(prompt_tokens), int(completion_tokens), int(total_tokens)


def generate_report(client, model_name, detections):
    content, _, _, _ = generate_report_with_usage(client, model_name, detections)
    return content