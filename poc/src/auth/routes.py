from fastapi import APIRouter, Depends
from .schemas import User
from .dependencies import verify_current_user

router = APIRouter(prefix="/v1/auth", tags=["auth"])

@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(verify_current_user)) -> User:
    """
    Get the current authenticated user's profile.
    
    This endpoint verifies the JWT token sent in the Authorization header
    against Supabase Auth. It returns the user details if valid.
    """
    return current_user
