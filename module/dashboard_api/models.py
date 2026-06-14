from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ApiUserCreateRequest(BaseModel):
    user_key: str = Field(..., min_length=1, max_length=64)
    display_name: Optional[str] = Field(default=None, max_length=128)


class ApiUserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=128)
    is_active: Optional[bool] = None


class ApiUserResponse(BaseModel):
    id: int
    user_key: str
    display_name: Optional[str]
    is_active: bool
    created_at_ms: int
    updated_at_ms: int


class ApiUserTokenResponse(BaseModel):
    user: ApiUserResponse
    token: str


class PushSource(BaseModel):
    instance: Optional[str] = None
    config: Optional[str] = None
    producer: Optional[str] = None


class ResourcePayload(BaseModel):
    value: int
    limit: Optional[int] = None
    total: Optional[int] = None
    color: Optional[str] = None


class PushRequest(BaseModel):
    recorded_at_ms: int
    source: PushSource = Field(default_factory=PushSource)
    resources: Dict[str, ResourcePayload]

    @validator("recorded_at_ms")
    def validate_recorded_at_ms(cls, value):
        if value <= 0:
            raise ValueError("recorded_at_ms must be positive")
        return value

    @validator("resources")
    def validate_resources(cls, value):
        if not value:
            raise ValueError("resources must not be empty")
        return value


class ResourcePointResponse(BaseModel):
    resource_name: str
    recorded_at_ms: int
    received_at_ms: int
    value: int
    limit: Optional[int] = None
    total: Optional[int] = None
    color: Optional[str] = None


class ResourceLatestListResponse(BaseModel):
    resources: List[ResourcePointResponse]


class WidgetResourceResponse(ResourcePointResponse):
    age_ms: int


class WidgetOverviewResponse(BaseModel):
    generated_at_ms: int
    resources: List[WidgetResourceResponse]
