# backend/app/api/session.py
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, EmailStr

from ..core import ner
from .interview import start as start_interview, StartPayload
from ..core.state import store
from ..core.database import db

# all session routes live under /session
router = APIRouter(prefix="/session", tags=["session"])


# =========================
# models
# =========================
class SessionReq(BaseModel):
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    role: Optional[str] = None
    level: Optional[str] = None
    user_text: str                # free-text brief
    session_id: Optional[str] = None


class SessionResp(BaseModel):
    session_id: str
    question: str


# =========================
# helpers
# =========================
def _merge(form: SessionReq, slots: dict):
    return {
        "company": (form.company or (slots or {}).get("company") or "").strip(),
        "role":    (form.role    or (slots or {}).get("role")    or "").strip(),
        "level":   (form.level   or (slots or {}).get("level")   or "").strip(),
    }


# Normalize a session document coming from either schema variant:
#   Variant A (your create() below): { _id: sid, startedAt, endedAt, ... }
#   Variant B (older code): { sessionId: sid, createdAt, updatedAt, overallScore, ... }
def _normalize_session_doc(doc: dict) -> dict:
    if not doc:
        return {}
    sid = doc.get("sessionId") or doc.get("_id")
    started = doc.get("startedAt") or doc.get("createdAt")
    ended = doc.get("endedAt") or doc.get("updatedAt")
    overall = doc.get("overallScore")
    if overall is None and isinstance(doc.get("scores"), dict):
        overall = doc["scores"].get("overall")

    return {
        "sessionId": sid,
        "createdAt": started or doc.get("createdAt") or datetime.utcnow(),
        "endedAt": ended,
        "company": doc.get("company"),
        "role": doc.get("role"),
        "level": doc.get("level"),
        "overallScore": overall,
        "userEmail": doc.get("userEmail"),
    }


# =========================
# create / reset
# =========================
@router.post("", response_model=SessionResp)
async def create(req: SessionReq):
    # NER to enrich only (don’t block if it fails)
    try:
        slots = await ner.extract(req.user_text)
    except Exception as e:
        print("NER failed (continuing):", e)
        slots = {}

    merged = _merge(req, slots)

    if not merged["company"] or not merged["role"]:
        missing = []
        if not merged["company"]:
            missing.append("company")
        if not merged["role"]:
            missing.append("role")
        raise HTTPException(status_code=422, detail=f"Need: {', '.join(missing)}")

    sid = req.session_id or str(uuid.uuid4())

    # Start interview with richer context for a better first question
    data = await start_interview(
        StartPayload(
            session_id=sid,
            role=merged["role"],
            seniority=merged["level"] or "unspecified",
            company=merged["company"],
            context=req.user_text,  # pass the candidate brief here
        )
    )

    # persist the session doc (Variant A)
    try:
        await db["sessions"].update_one(
            {"_id": sid},
            {
                "$setOnInsert": {
                    "_id": sid,
                    "userEmail": (str(req.email).lower() if req.email else None),
                    "company": merged["company"],
                    "level": merged["level"] or None,
                    "role": merged["role"],
                    "startedAt": datetime.utcnow(),
                    "endedAt": None,
                    "durationSec": None,
                    "setup": {
                        "form": {
                            "company": req.company,
                            "role": req.role,
                            "level": req.level,
                            "user_text": req.user_text,
                        },
                        "ner": {
                            "company": (slots or {}).get("company"),
                            "role": (slots or {}).get("role"),
                            "level": (slots or {}).get("level"),
                        },
                        "merged": merged,
                    },
                    "scores": None,
                }
            },
            upsert=True,
        )
    except Exception as e:
        print("[warn] session insert/upsert failed:", e)

    return {"session_id": data["session_id"], "question": data["question"]}


@router.patch("/{sid}", response_model=SessionResp)
async def reset(req: SessionReq, sid: str = Path(..., description="Existing session to reset")):
    if store.get(sid) is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    try:
        # wipe in-memory chat for this session
        store._store.pop(sid)  # type: ignore[attr-defined]
    except Exception:
        pass
    req.session_id = sid
    return await create(req)


# =========================
# dashboard helpers
# =========================

@router.get("/list")
async def list_sessions():
    """
    Return all sessions (most recent first).
    If you have auth/userEmail, filter by {"userEmail": current_user_email}.
    Works with either sessions schema variant.
    """
    # pull all docs, normalize, sort by created/started desc
    cur = db["sessions"].find({})
    docs = [_normalize_session_doc(s) async for s in cur]
    docs.sort(key=lambda d: d.get("createdAt") or datetime.min, reverse=True)
    return docs


@router.get("/{session_id}/summary")
async def session_summary(session_id: str):
    """
    Return a single session with its turns.
    - session: normalized metadata
    - turns: [{index, question, userAnswer, feedback, score, createdAt}, ...]
    """
    # look up session in both schema variants
    sess = await db["sessions"].find_one({"_id": session_id}) or await db["sessions"].find_one(
        {"sessionId": session_id}
    )
    session_norm = _normalize_session_doc(sess) if sess else {"sessionId": session_id}

    turns_cur = db["turns"].find({"sessionId": session_id}, {"_id": 0}).sort("index", 1)
    turns = [t async for t in turns_cur]

    return {"session": session_norm, "turns": turns}
