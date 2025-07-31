from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from utils.jwt_handler import decode_access_token

# Use Argon2 password hasher
ph = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

def hash_password(password: str) -> str:
    """
    Hashes a plain password using Argon2.
    """
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against its hashed value using Argon2.
    """
    try:
        return ph.verify(hashed_password, plain_password)
    except:
        return False

def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Retrieves the currently authenticated user based solely on the JWT token.
    """
    try:
        # Decode the JWT token
        payload = decode_access_token(token)
        user_id = payload.get("user_id")
        email = payload.get("email")
        company_id = payload.get("company_id")

        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Return user data directly from the token
        return {
            "id": user_id,
            "email": email,
            "company_id": company_id,
        }

    except Exception as e:
        print(f"Error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

