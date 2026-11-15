"""Common schemas and response models."""
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
