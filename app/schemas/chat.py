from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)

    # No autonomy flag. Mutating tools are gated on a human decision that the
    # caller cannot supply in its own request body.
    model_config = {"extra": "forbid"}


class ChatResponse(BaseModel):
    response: str
    tool_events: list[dict]


class PendingApproval(BaseModel):
    id: str
    tool: str
    arguments: dict


class ApprovalDecision(BaseModel):
    approved: bool


class ApprovalResult(BaseModel):
    id: str
    approved: bool
    recorded: bool
