# admin_auth.py
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .admin_jwt_handler import decode_admin_access_token  # We'll create this separately

ph = PasswordHasher()
oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="/api/admin-sign-in")

def hash_admin_password(password: str) -> str:
    return ph.hash(password)

def verify_admin_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except:
        return False

def get_current_admin(token: str = Depends(oauth2_scheme_admin)):
    try:
        payload = decode_admin_access_token(token)
        return payload  # contains admin_id, email, role
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )