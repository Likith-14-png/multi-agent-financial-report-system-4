from pydantic import BaseModel, Field, ConfigDict


class RedFlagAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(..., min_length=1, description="Company name")
    collection: str = Field(..., min_length=1, description="Chroma collection name")
