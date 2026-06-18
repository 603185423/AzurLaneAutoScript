import json
from typing import Optional

from module.dashboard_api.models import (
    ApiUserResponse,
    EventItemResponse,
    ResourcePointResponse,
    WidgetOverviewResponse,
    WidgetResourceResponse,
)
from module.dashboard_api.repository import DashboardRepository
from module.dashboard_api.utils import generate_token, hash_token, is_valid_resource_name, now_ms, sort_resource_names


class DashboardService:
    def __init__(self, db):
        self.db = db
        self.repository = DashboardRepository(db)

    def health(self) -> dict:
        return {
            "status": "ok",
            "database": self.db.dialect_name,
            "user_count": self.repository.count_users(),
            "generated_at_ms": now_ms(),
        }

    @staticmethod
    def serialize_user(user) -> ApiUserResponse:
        return ApiUserResponse(
            id=user.id,
            user_key=user.user_key,
            display_name=user.display_name,
            is_active=bool(user.is_active),
            created_at_ms=user.created_at_ms,
            updated_at_ms=user.updated_at_ms,
        )

    def list_users(self):
        return [self.serialize_user(user) for user in self.repository.list_users()]

    def get_user(self, user_id: int) -> Optional[ApiUserResponse]:
        user = self.repository.get_user(user_id)
        if user is None:
            return None
        return self.serialize_user(user)

    def get_user_from_token(self, token: str):
        user = self.repository.get_user_by_token_hash(hash_token(token))
        if user is None:
            return None
        return user

    def create_user(self, *, user_key: str, display_name: Optional[str]):
        if self.repository.get_user_by_key(user_key) is not None:
            raise ValueError(f"user_key already exists: {user_key}")
        plain_token = generate_token()
        current_ms = now_ms()
        user = self.repository.create_user(
            user_key=user_key,
            display_name=display_name,
            token_hash=hash_token(plain_token),
            created_at_ms=current_ms,
        )
        return self.serialize_user(user), plain_token

    def update_user(self, user_id: int, *, display_name=None, is_active=None):
        user = self.repository.update_user(
            user_id,
            display_name=display_name,
            is_active=is_active,
            updated_at_ms=now_ms(),
        )
        if user is None:
            return None
        return self.serialize_user(user)

    def rotate_token(self, user_id: int):
        plain_token = generate_token()
        user = self.repository.rotate_token(
            user_id,
            token_hash=hash_token(plain_token),
            updated_at_ms=now_ms(),
        )
        if user is None:
            return None
        return self.serialize_user(user), plain_token

    def store_push(self, user, payload):
        normalized = {}
        for resource_name, resource in payload.resources.items():
            if not is_valid_resource_name(resource_name):
                raise ValueError(f"invalid resource name: {resource_name}")
            normalized[resource_name] = resource.dict(exclude_none=True)
        received_at_ms = now_ms()
        self.repository.insert_samples_and_update_latest(
            user_id=user.id,
            recorded_at_ms=payload.recorded_at_ms,
            received_at_ms=received_at_ms,
            source_instance=payload.source.instance,
            source_config=payload.source.config,
            resources=normalized,
        )
        return {
            "accepted": len(normalized),
            "recorded_at_ms": payload.recorded_at_ms,
            "received_at_ms": received_at_ms,
        }

    @staticmethod
    def serialize_resource(resource) -> ResourcePointResponse:
        return ResourcePointResponse(
            resource_name=resource.resource_name,
            recorded_at_ms=resource.recorded_at_ms,
            received_at_ms=resource.received_at_ms,
            value=resource.value,
            limit=resource.limit_value,
            total=resource.total_value,
            color=resource.color,
        )

    def get_latest_resources(self, user_id: int):
        resources = self.repository.get_latest_resources(user_id)
        serialized = {item.resource_name: self.serialize_resource(item) for item in resources}
        return [serialized[name] for name in sort_resource_names(list(serialized.keys()))]

    def get_resource_history(self, user_id: int, resource_name: str, from_ms, to_ms, limit, order):
        if not is_valid_resource_name(resource_name):
            raise ValueError(f"invalid resource name: {resource_name}")
        return [
            self.serialize_resource(item)
            for item in self.repository.get_resource_history(
                user_id=user_id,
                resource_name=resource_name,
                from_ms=from_ms,
                to_ms=to_ms,
                limit=limit,
                order=order,
            )
        ]

    def get_widget_overview(self, user_id: int) -> WidgetOverviewResponse:
        current_ms = now_ms()
        latest = self.get_latest_resources(user_id)
        resources = [
            WidgetResourceResponse(**item.dict(), age_ms=max(current_ms - item.recorded_at_ms, 0))
            for item in latest
        ]
        return WidgetOverviewResponse(generated_at_ms=current_ms, resources=resources)

    @staticmethod
    def serialize_event(event) -> EventItemResponse:
        payload = None
        if getattr(event, "payload_json", None):
            payload = json.loads(event.payload_json)
        return EventItemResponse(
            id=getattr(event, "id", None),
            source_instance=event.source_instance,
            source_config=event.source_config,
            event_category=event.event_category,
            event_type=event.event_type,
            status=event.status,
            reason=event.reason,
            payload=payload,
            recorded_at_ms=event.recorded_at_ms,
            received_at_ms=event.received_at_ms,
        )

    def store_event(self, user, payload):
        if not is_valid_resource_name(payload.event.event_category):
            raise ValueError(f"invalid event category: {payload.event.event_category}")
        if not is_valid_resource_name(payload.event.event_type):
            raise ValueError(f"invalid event type: {payload.event.event_type}")
        if payload.event.status and not is_valid_resource_name(payload.event.status):
            raise ValueError(f"invalid event status: {payload.event.status}")

        received_at_ms = now_ms()
        event = self.repository.insert_event_and_update_latest(
            user_id=user.id,
            source_instance=payload.source.instance,
            source_config=payload.source.config,
            event_category=payload.event.event_category,
            event_type=payload.event.event_type,
            status=payload.event.status,
            reason=payload.event.reason,
            payload=payload.event.payload,
            recorded_at_ms=payload.recorded_at_ms,
            received_at_ms=received_at_ms,
        )
        serialized = self.serialize_event(event)
        return {
            "accepted": 1,
            "recorded_at_ms": payload.recorded_at_ms,
            "received_at_ms": received_at_ms,
            "event": serialized.dict(),
        }

    def get_events(
        self,
        user_id: int,
        *,
        event_category: Optional[str],
        source_instance: Optional[str],
        event_type: Optional[str],
        from_ms: Optional[int],
        to_ms: Optional[int],
        limit: int,
        order: str,
    ):
        if event_category and not is_valid_resource_name(event_category):
            raise ValueError(f"invalid event category: {event_category}")
        if event_type and not is_valid_resource_name(event_type):
            raise ValueError(f"invalid event type: {event_type}")
        return [
            self.serialize_event(item)
            for item in self.repository.get_events(
                user_id=user_id,
                event_category=event_category,
                source_instance=source_instance,
                event_type=event_type,
                from_ms=from_ms,
                to_ms=to_ms,
                limit=limit,
                order=order,
            )
        ]

    def get_latest_events(
        self,
        user_id: int,
        *,
        event_category: Optional[str],
        source_instance: Optional[str],
    ):
        if event_category and not is_valid_resource_name(event_category):
            raise ValueError(f"invalid event category: {event_category}")
        return [
            self.serialize_event(item)
            for item in self.repository.get_latest_events(
                user_id=user_id,
                event_category=event_category,
                source_instance=source_instance,
            )
        ]
