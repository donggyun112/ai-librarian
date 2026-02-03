from pydantic import BaseModel, Field


class BookCreateRequest(BaseModel):
    """Request schema for creating a book"""
    title: str = Field(..., min_length=1, max_length=500, description="Book title")


class BookResponse(BaseModel):
    """Response schema for book"""
    id: str = Field(..., description="Book ID (UUID)")
    user_id: str = Field(..., description="Owner user ID (UUID)")
    title: str = Field(..., description="Book title")
    created_at: str = Field(..., description="Creation timestamp")


class BooksListResponse(BaseModel):
    """Response schema for list of books"""
    books: list[BookResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total number of books")
