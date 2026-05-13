import json
from openai import OpenAI
from app.config import OPENAI_API_KEY, OPENAI_FALLBACK_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def call_gpt_for_json(prompt: str) -> dict:
    response = client.chat.completions.create(
        model=OPENAI_FALLBACK_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a strict JSON extraction assistant. Return only valid JSON. No markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except Exception:
        raise ValueError(f"GPT fallback returned invalid JSON: {content}")