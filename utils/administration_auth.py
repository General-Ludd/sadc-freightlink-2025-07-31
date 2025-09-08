# admin_auth.py
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from .admin_jwt_handler import decode_admin_access_token  # We'll create this separately

ph = PasswordHasher()
oauth2_admin_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")

def hash_admin_password(password: str) -> str:
    return ph.hash(password)

def verify_admin_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except:
        return False

def get_current_admin(token: str = Depends(oauth2_admin_scheme)):
    try:
        payload = decode_admin_access_token(token)
        admin_id = payload.get("id")
        email = payload.get("email")
        role = payload.get("role")  # "super" or "support"

        if not admin_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "id": admin_id,
            "email": email,
            "role": role
        }
    except Exception as e:
        print(f"Error in get_current_admin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )