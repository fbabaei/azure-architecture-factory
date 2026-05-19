from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    context: str = Field(default="")


class AskResponse(BaseModel):
    answer: str
    source: str
