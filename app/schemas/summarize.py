from pydantic import BaseModel


class KeyDetail(BaseModel):
    label: str
    value: str


class SummaryResult(BaseModel):
    summary: str
    key_details: list[KeyDetail]


class SummarizeResponse(BaseModel):
    status: str
    filename: str
    result: SummaryResult
