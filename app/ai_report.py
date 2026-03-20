from openai import OpenAI

def generate_report(client, model_name, detections):
    prompt = f"""
Detected issues: {detections}
Generate civil inspection report with summary, severity, causes, repair, prevention.
"""

    res = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content