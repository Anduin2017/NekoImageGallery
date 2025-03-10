from datetime import datetime
from typing import Optional
from uuid import UUID

from numpy import ndarray
from pydantic import BaseModel, Field


class ImageData(BaseModel):
    id: UUID
    url: str
    thumbnail_url: Optional[str] = None
    ocr_text: Optional[str] = None
    image_vector: Optional[ndarray] = Field(None, exclude=True)
    text_contain_vector: Optional[ndarray] = Field(None, exclude=True)
    index_date: datetime
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[float] = None
    starred: Optional[bool] = False

    @property
    def payload(self):
        result = self.model_dump(exclude={'image_vector', 'text_contain_vector', 'id', 'index_date'})
        # Qdrant database cannot accept datetime object, so we have to convert it to string
        result['index_date'] = self.index_date.isoformat()
        return result

    @classmethod
    def from_payload(cls, id: str, payload: dict,
                     image_vector: Optional[ndarray] = None, text_contain_vector: Optional[ndarray] = None):
        # Convert the datetime string back to datetime object
        index_date = datetime.fromisoformat(payload['index_date'])
        del payload['index_date']
        return cls(id=UUID(id),
                   index_date=index_date,
                   **payload,
                   image_vector=image_vector if image_vector is not None else None,
                   text_contain_vector=text_contain_vector if text_contain_vector is not None else None)

    class Config:
        arbitrary_types_allowed = True
