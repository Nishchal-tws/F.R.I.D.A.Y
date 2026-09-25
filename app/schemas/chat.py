from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    autonomous: bool = False

class ChatResponse(BaseModel):
    response: str
