from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.users.models import User
from app.users.schemas import UserRegister, UserLogin, Token, UserResponse
from app.users import service

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and return a JWT token."""
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email,
        password_hash=service.hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = service.create_access_token({"sub": str(user.id)})
    return {"access_token": token}


from fastapi.security import OAuth2PasswordRequestForm

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    """Login with email (as username) + password and receive a JWT token."""
    # OAuth2 specifies the field is named "username", but we use it for our "email"
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar()
    if not user or not service.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = service.create_access_token({"sub": str(user.id)})
    return {"access_token": token}


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: str = Depends(service.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the currently authenticated user's profile."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
