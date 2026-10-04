from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from typing_extensions import Annotated


class ScanTextRequest(BaseModel):
    text: Optional[Annotated[str, Field(min_length=1, max_length=10000)]] = None
    url: Optional[Annotated[str, Field(min_length=1, max_length=2048)]] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    def has_input(self) -> bool:
        return bool(self.text or self.url)


class ScanUploadRequest(BaseModel):
    text: Optional[Annotated[str, Field(min_length=1, max_length=10000)]] = None
    url: Optional[Annotated[str, Field(min_length=1, max_length=2048)]] = None


class FeedbackRequest(BaseModel):
    helpful: bool
    comment: Optional[Annotated[str, Field(max_length=1000)]] = None