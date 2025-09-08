# utils/admin_jwt_handler.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status
from models.administration import Platform_Super_Admins

SECRET_KEY_ADMIN = "52f6a17d6b32d899c0d839ec771f6c27d95e101a464b8978f779a62857a1b0b5fb0d4f94fa02fac64502bf5f45f1e20e10c5be498aca671139ae1cc3703db5f7bb97b09ddd8264405f31050002717d890be45bd95c06d29d554d75cc3229c766a892f1257be75bffe3f33df059f033c95db8d9d06190b334b7f331b2b3d731b7b68c1db53a8178139329370fce47a923c5ef30310386b346ee6e4381673f06c2025c6ec3bf79b0e6c15c46f3114aa2c2a4c0d87128f4ede07013d3829fd619b4be653d7372b512421dec6279e44475e3187a03f934e6420c2a962d8fa34c6531bbbc351d811661b13818e008b41243495b4fc566f4ee6fcc8fe60dd836050b7f2b1bacd33b6e385bec7b4790d1e365762eb7bc07052ace2b81c3401844a52eec"  # Use a secure, unique secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 3000

def create_admin_access_token(admin_data: Platform_Super_Admins) -> str:
    to_encode = {
        "admin_id": admin_data["id"],
        "email": admin_data["email"],
        "role": admin_data["role"]
    }
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY_ADMIN, algorithm=ALGORITHM)

def decode_admin_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY_ADMIN, algorithms=[ALGORITHM])
        admin_id: str = payload.get("admin_id")
        email: str = payload.get("email")
        role: str = payload.get("role")

        if admin_id is None or email is None or role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload  # contains admin_id, email, role

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )