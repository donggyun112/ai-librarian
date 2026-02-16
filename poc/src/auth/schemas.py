from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field

class UserIdentity(BaseModel):
    id: str
    user_id: str
    identity_data: Dict[str, Any] = Field(default_factory=dict)
    provider: str
    created_at: Optional[str] = None
    last_sign_in_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class User(BaseModel):
    """Supabase User Model Mirror"""
    id: str
    aud: str
    role: str = "authenticated"
    email: Optional[str] = None
    email_confirmed_at: Optional[str] = None
    phone: Optional[str] = None
    confirmed_at: Optional[str] = None
    last_sign_in_at: Optional[str] = None
    app_metadata: Dict[str, Any] = Field(default_factory=dict)
    user_metadata: Dict[str, Any] = Field(default_factory=dict)
    identities: List[UserIdentity] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
