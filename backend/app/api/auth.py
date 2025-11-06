from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from passlib.context import CryptContext
from pymongo.errors import DuplicateKeyError
from datetime import datetime
from ..core.database import db  # <-- relative import

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        return str(v).strip().lower()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        return str(v).strip().lower()

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        return str(v).strip().lower()

@router.post("/signup")
async def signup(payload: SignupRequest):
    hashed_pw = pwd_context.hash(payload.password)
    try:
        res = await db["users"].insert_one({
            "email": str(payload.email),
            "password": hashed_pw,
            "createdAt": datetime.utcnow(),
        })
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="User already exists")
    # return userId so frontend can store it
    return {
        "message": "Signup successful",
        "email": str(payload.email),
        "userId": str(res.inserted_id),
    }

@router.post("/login")
async def login(payload: LoginRequest):
    user = await db["users"].find_one({"email": str(payload.email)})
    if not user or not pwd_context.verify(payload.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    # include userId for linking sessions
    return {
        "message": "Login successful",
        "email": user["email"],
        "userId": str(user["_id"]),
    }

@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    user = await db["users"].find_one({"email": str(payload.email)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"Password reset link sent to {payload.email}"}
