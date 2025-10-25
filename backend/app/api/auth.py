from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from app.core.database import db

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# --------- SCHEMAS ----------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# --------- ENDPOINTS ----------
@router.post("/signup")
async def signup(payload: SignupRequest):
    """Register a new user"""
    user = await db["users"].find_one({"email": payload.email})
    if user:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = pwd_context.hash(payload.password)
    await db["users"].insert_one({
        "email": payload.email,
        "password": hashed_pw
    })
    return {"message": "Signup successful"}


@router.post("/login")
async def login(payload: LoginRequest):
    """Authenticate user credentials"""
    user = await db["users"].find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not pwd_context.verify(payload.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"message": "Login successful", "email": user["email"]}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Mock forgot password flow (can add email later)"""
    user = await db["users"].find_one({"email": payload.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # In production: send email with reset link/token
    return {"message": f"Password reset link sent to {payload.email}"}
