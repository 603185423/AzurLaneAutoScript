from typing import Any, Dict, List, Optional

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


class EventPayload(BaseModel):
    event_category: str = Field(..., min_length=1, max_length=64)
    event_type: str = Field(..., min_length=1, max_length=64)
    status: Optional[str] = Field(default=None, max_length=64)
    reason: Optional[str] = Field(default=None, max_length=128)
    payload: Optional[Dict[str, Any]] = None


class EventPushRequest(BaseModel):
    recorded_at_ms: int
    source: PushSource = Field(default_factory=PushSource)
    event: EventPayload

    @validator("recorded_at_ms")
    def validate_event_recorded_at_ms(cls, value):
        if value <= 0:
            raise ValueError("recorded_at_ms must be positive")
        return value

    @validator("source")
    def validate_event_source(cls, value):
        if not value.instance:
            raise ValueError("source.instance is required for events")
        return value


class EventItemResponse(BaseModel):
    id: Optional[int] = None
    source_instance: str
    source_config: Optional[str] = None
    event_category: str
    event_type: str
    status: Optional[str] = None
    reason: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    recorded_at_ms: int
    received_at_ms: int


class EventHistoryListResponse(BaseModel):
    items: List[EventItemResponse]


class EventLatestListResponse(BaseModel):
    events: List[EventItemResponse]
