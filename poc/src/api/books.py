from fastapi import APIRouter, Depends, HTTPException, status
from supabase import AsyncClient
from loguru import logger

from src.auth.dependencies import verify_current_user, get_user_scoped_client
from src.auth.schemas import User
from .books_schemas import BookCreateRequest, BookResponse, BooksListResponse


router = APIRouter(prefix="/v1/books", tags=["books"])


@router.get("", response_model=BooksListResponse)
async def get_books(
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
) -> BooksListResponse:
    """
    Get all books for the current user.

    RLS automatically filters by auth.uid() - no manual user_id filter needed!
    """
    try:
        # Query books table - RLS automatically filters by current user
        response = await client.table("books").select("*").execute()

        if getattr(response, "error", None):
            logger.error(f"Supabase error while retrieving books: {response.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve books"
            )

        if response.data is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve books"
            )

        books = [
            BookResponse(
                id=book["id"],
                user_id=book["user_id"],
                title=book["title"],
                created_at=book["created_at"],
            )
            for book in response.data
        ]

        logger.info(f"Retrieved {len(books)} books for user {current_user.id}")

        return BooksListResponse(books=books, total=len(books))

    except HTTPException:
        raise
    except Exception as e:
        # 🔒 Security: Log full error with stack trace internally, but hide details from user
        logger.exception(f"Failed to retrieve books for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve books"
        )


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_book(
    request: BookCreateRequest,
    current_user: User = Depends(verify_current_user),
    client: AsyncClient = Depends(get_user_scoped_client),
) -> BookResponse:
    """
    Create a new book for the current user.

    RLS automatically sets user_id to auth.uid() - manual assignment optional.
    """
    try:
        # Insert book - include user_id explicitly (RLS will validate it matches auth.uid())
        response = await client.table("books").insert({
            "title": request.title,
            "user_id": current_user.id,  # Explicit for clarity (RLS validates)
        }).execute()

        if getattr(response, "error", None):
            logger.error(f"Supabase error while creating book: {response.error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create book"
            )

        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create book"
            )

        book_data = response.data[0]

        logger.info(f"Created book {book_data['id']} for user {current_user.id}")

        return BookResponse(
            id=book_data["id"],
            user_id=book_data["user_id"],
            title=book_data["title"],
            created_at=book_data["created_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        # 🔒 Security: Log full error with stack trace internally, but hide details from user
        logger.exception(f"Failed to create book for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create book"
        )
