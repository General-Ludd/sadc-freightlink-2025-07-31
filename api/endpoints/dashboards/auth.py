from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import HTTPException, status
from utils.jwt_handler import create_access_token, decode_refresh_token

@router.post("/refresh")
def refresh_token(refresh_token: str):
    try:
        payload = decode_refresh_token(refresh_token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Fetch user from DB (so that we still check if they exist & active)
        # Example: user = await get_user_by_id(user_id)
        # Here, I’ll just simulate:
        user = {"id": user_id, "email": "test@example.com", "first_name": "Test", "last_name": "User", "company_id": None}

        new_access_token = create_access_token(user)
        return {"access_token": new_access_token, "token_type": "bearer"}
    
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")