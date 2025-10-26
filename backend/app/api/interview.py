import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException

from ..schemas import StartPayload, StartResponse, AnswerPayload, AnswerResponse, SaveScorePayload
from ..core.state import store
from ..core import gpt
from ..core.database import db

router = APIRouter()

SYSTEM_TMPL = (
    "You are an expert {role} interviewer (seniority: {seniority}). "
    "Ask ONE clear, concise question at a time. Increase difficulty gradually "
    "if the candidate performs well."
)

def system_msg(role: str, seniority: str) -> dict:
    return {"role": "system", "content": SYSTEM_TMPL.format(role=role, seniority=seniority)}

@router.post("/start", response_model=StartResponse)
async def start(payload: StartPayload):
    """
    Initialize a new interview and return the first question.
    """
    sid = payload.session_id or str(uuid.uuid4())
    store.new(sid, system_msg(payload.role, payload.seniority))

    first_prompt = (
        "Generate the FIRST interview question only.\n"
        f"Company: {payload.company or 'generic'}\n"
        f"Role: {payload.role}\n"
        f"Seniority/Level: {payload.seniority or 'unspecified'}\n"
        f"Candidate brief (optional): {payload.context or 'n/a'}\n\n"
        "Rules:\n"
        "- Return a single well-formed question, no preamble, no explanation.\n"
        "- Keep it relevant to the company/role/level and any brief above.\n"
        "- Avoid multi-part questions; one focused question."
    )

    store.add(sid, {"role": "user", "content": first_prompt})
    question = await gpt.chat(store.get(sid))
    store.add(sid, {"role": "assistant", "content": question})

    # create session doc if not exists
    try:
        await db["sessions"].update_one(
            {"sessionId": sid},
            {"$setOnInsert": {"sessionId": sid, "createdAt": datetime.utcnow()}},
            upsert=True,
        )
    except Exception as e:
        print("[warn] session upsert failed:", e)

    return {"session_id": sid, "question": question}

@router.post("/answer", response_model=AnswerResponse)
async def answer(payload: AnswerPayload):
    """
    Accept user's answer, return brief feedback + next question, and persist the turn.
    """
    hist = store.get(payload.session_id)
    if not hist:
        raise HTTPException(status_code=404, detail="Unknown session_id; call /start first")

    # last assistant message is the current question
    last_question = next((m["content"] for m in reversed(hist) if m["role"] == "assistant"), "") or ""

    # push answer + instruction to generate feedback + next question
    hist.append({"role": "user", "content": payload.text})
    hist.append({
        "role": "user",
        "content": (
            "Evaluate my answer briefly in ≤3 sentences (focus on correctness, clarity, completeness). "
            "Then write 'NEXT:' followed by the single next question."
        ),
    })
    full = await gpt.chat(hist)
    hist.append({"role": "assistant", "content": full})

    if "NEXT:" in full:
        feedback, nxt = full.split("NEXT:", 1)
    else:
        feedback, nxt = full, "Interview finished."

    # NEW: independent LLM pass to score 0..10
    score = await gpt.score_answer(last_question, payload.text)

    # persist this turn
    try:
        idx = await db["turns"].count_documents({"sessionId": payload.session_id})
        await db["turns"].insert_one({
            "sessionId": payload.session_id,
            "index": idx,
            "question": last_question,
            "userAnswer": payload.text,
            "feedback": feedback.strip(),
            "score": score,
            "createdAt": datetime.utcnow(),
        })
    except Exception as e:
        print("[warn] turn insert failed:", e)

    return {"feedback": feedback.strip(), "question": nxt.strip(), "score": score}

# NEW: save overall session score (and optionally patch per-question scores)
@router.post("/session/{session_id}/score")
async def save_session_score(session_id: str, payload: SaveScorePayload):
    # store/patch scores onto turns by index (if provided)
    if payload.scores:
        for row in payload.scores:
            try:
                idx = int(row.get("index", -1))
            except Exception:
                idx = -1
            if idx >= 0 and row.get("score") is not None:
                try:
                    await db["turns"].update_one(
                        {"sessionId": session_id, "index": idx},
                        {"$set": {"score": int(row["score"]) }},
                    )
                except Exception as e:
                    print("[warn] turn score update failed:", e)

    try:
        await db["sessions"].update_one(
            {"sessionId": session_id},
            {"$set": {"overallScore": payload.overall, "updatedAt": datetime.utcnow()}},
            upsert=True,
        )
    except Exception as e:
        print("[warn] session overall score save failed:", e)

    return {"ok": True, "overall": payload.overall}
