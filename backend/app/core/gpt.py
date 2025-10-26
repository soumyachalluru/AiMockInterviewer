"""
LLM wrapper compatible with openai-python v1.x
"""

import os
from typing import List, Dict
from openai import AsyncOpenAI
# at top of gpt.py
import datetime


client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


async def chat(messages: List[Dict[str, str]]) -> str:
    """
    messages -> single assistant string
    """
    resp = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

async def score_answer(question: str, answer: str) -> int:
    """
    return an integer 0..10 for how strong the answer is.
    keep it deterministic and strict (no text, only an integer).
    """
    resp = await client.chat.completions.create(
        model=MODEL,
        temperature=0,  # deterministic scoring
        messages=[
            {"role": "system", "content": "Return ONLY an integer from 0 to 10 rating the candidate's answer quality. No text."},
            {"role": "user", "content": f"Question: {question}\nAnswer: {answer}\nScore (0-10):"}
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        val = int("".join(ch for ch in raw if ch.isdigit()))
        # clamp
        return max(0, min(10, val))
    except Exception:
        return 0
