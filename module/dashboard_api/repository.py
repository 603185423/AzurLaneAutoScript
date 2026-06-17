import json
from typing import Dict, Iterable, Optional

from sqlalchemy import asc, desc

from module.dashboard_api.db import (
    DashboardApiUser,
    DashboardEvent,
    DashboardEventLatest,
    DashboardResourceLatest,
    DashboardResourceSample,
)


class DashboardRepository:
    def __init__(self, db):
        self.db = db

    def list_users(self):
        with self.db.session() as session:
            return session.query(DashboardApiUser).order_by(DashboardApiUser.id.asc()).all()

    def get_user(self, user_id: int) -> Optional[DashboardApiUser]:
        with self.db.session() as session:
            return session.query(DashboardApiUser).filter(DashboardApiUser.id == user_id).one_or_none()

    def get_user_by_key(self, user_key: str) -> Optional[DashboardApiUser]:
        with self.db.session() as session:
            return session.query(DashboardApiUser).filter(DashboardApiUser.user_key == user_key).one_or_none()

    def get_user_by_token_hash(self, token_hash: str) -> Optional[DashboardApiUser]:
        with self.db.session() as session:
            return session.query(DashboardApiUser).filter(DashboardApiUser.token_hash == token_hash).one_or_none()

    def create_user(self, *, user_key: str, display_name: str, token_hash: str, created_at_ms: int) -> DashboardApiUser:
        with self.db.session() as session:
            user = DashboardApiUser(
                user_key=user_key,
                display_name=display_name,
                token_hash=token_hash,
                is_active=True,
                created_at_ms=created_at_ms,
                updated_at_ms=created_at_ms,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def update_user(self, user_id: int, *, display_name=None, is_active=None, updated_at_ms: int = None):
        with self.db.session() as session:
            user = session.query(DashboardApiUser).filter(DashboardApiUser.id == user_id).one_or_none()
            if user is None:
                return None
            if display_name is not None:
                user.display_name = display_name
            if is_active is not None:
                user.is_active = is_active
            if updated_at_ms is not None:
                user.updated_at_ms = updated_at_ms
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def rotate_token(self, user_id: int, *, token_hash: str, updated_at_ms: int):
        with self.db.session() as session:
            user = session.query(DashboardApiUser).filter(DashboardApiUser.id == user_id).one_or_none()
            if user is None:
                return None
            user.token_hash = token_hash
            user.updated_at_ms = updated_at_ms
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def count_users(self) -> int:
        with self.db.session() as session:
            return session.query(DashboardApiUser).count()

    def insert_samples_and_update_latest(
        self,
        *,
        user_id: int,
        recorded_at_ms: int,
        received_at_ms: int,
        source_instance: Optional[str],
        source_config: Optional[str],
        resources: Dict[str, Dict[str, Optional[int]]],
    ) -> None:
        with self.db.session() as session:
            for resource_name, resource in resources.items():
                sample = DashboardResourceSample(
                    user_id=user_id,
                    resource_name=resource_name,
                    recorded_at_ms=recorded_at_ms,
                    received_at_ms=received_at_ms,
                    value=resource["value"],
                    limit_value=resource.get("limit"),
                    total_value=resource.get("total"),
                    color=resource.get("color"),
                    source_instance=source_instance,
                    source_config=source_config,
                )
                session.add(sample)

                latest = (
                    session.query(DashboardResourceLatest)
                    .filter(
                        DashboardResourceLatest.user_id == user_id,
                        DashboardResourceLatest.resource_name == resource_name,
                    )
                    .one_or_none()
                )
                if latest is None:
                    latest = DashboardResourceLatest(
                        user_id=user_id,
                        resource_name=resource_name,
                        recorded_at_ms=recorded_at_ms,
                        received_at_ms=received_at_ms,
                        value=resource["value"],
                        limit_value=resource.get("limit"),
                        total_value=resource.get("total"),
                        color=resource.get("color"),
                    )
                    session.add(latest)
                    continue

                if recorded_at_ms >= latest.recorded_at_ms:
                    latest.recorded_at_ms = recorded_at_ms
                    latest.received_at_ms = received_at_ms
                    latest.value = resource["value"]
                    latest.limit_value = resource.get("limit")
                    latest.total_value = resource.get("total")
                    latest.color = resource.get("color")
                    session.add(latest)

            session.commit()

    def get_latest_resources(self, user_id: int) -> Iterable[DashboardResourceLatest]:
        with self.db.session() as session:
            return (
                session.query(DashboardResourceLatest)
                .filter(DashboardResourceLatest.user_id == user_id)
                .order_by(DashboardResourceLatest.resource_name.asc())
                .all()
            )

    def get_resource_history(
        self,
        *,
        user_id: int,
        resource_name: str,
        from_ms: Optional[int],
        to_ms: Optional[int],
        limit: int,
        order: str,
    ) -> Iterable[DashboardResourceSample]:
        with self.db.session() as session:
            query = session.query(DashboardResourceSample).filter(
                DashboardResourceSample.user_id == user_id,
                DashboardResourceSample.resource_name == resource_name,
            )
            if from_ms is not None:
                query = query.filter(DashboardResourceSample.recorded_at_ms >= from_ms)
            if to_ms is not None:
                query = query.filter(DashboardResourceSample.recorded_at_ms <= to_ms)
            sort_rule = desc if order == "desc" else asc
            return query.order_by(sort_rule(DashboardResourceSample.recorded_at_ms)).limit(limit).all()

    def insert_event_and_update_latest(
        self,
        *,
        user_id: int,
        source_instance: str,
        source_config: Optional[str],
        event_category: str,
        event_type: str,
        status: Optional[str],
        reason: Optional[str],
        payload: Optional[dict],
        recorded_at_ms: int,
        received_at_ms: int,
    ) -> DashboardEvent:
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload is not None else None
        with self.db.session() as session:
            event = DashboardEvent(
                user_id=user_id,
                source_instance=source_instance,
                source_config=source_config,
                event_category=event_category,
                event_type=event_type,
                status=status,
                reason=reason,
                payload_json=payload_json,
                recorded_at_ms=recorded_at_ms,
                received_at_ms=received_at_ms,
            )
            session.add(event)

            latest = (
                session.query(DashboardEventLatest)
                .filter(
                    DashboardEventLatest.user_id == user_id,
                    DashboardEventLatest.source_instance == source_instance,
                    DashboardEventLatest.event_category == event_category,
                )
                .one_or_none()
            )
            if latest is None:
                latest = DashboardEventLatest(
                    user_id=user_id,
                    source_instance=source_instance,
                    source_config=source_config,
                    event_category=event_category,
                    event_type=event_type,
                    status=status,
                    reason=reason,
                    payload_json=payload_json,
                    recorded_at_ms=recorded_at_ms,
                    received_at_ms=received_at_ms,
                )
                session.add(latest)
            elif recorded_at_ms >= latest.recorded_at_ms:
                latest.source_config = source_config
                latest.event_type = event_type
                latest.status = status
                latest.reason = reason
                latest.payload_json = payload_json
                latest.recorded_at_ms = recorded_at_ms
                latest.received_at_ms = received_at_ms
                session.add(latest)

            session.commit()
            session.refresh(event)
            return event

    def get_events(
        self,
        *,
        user_id: int,
        event_category: Optional[str],
        source_instance: Optional[str],
        event_type: Optional[str],
        from_ms: Optional[int],
        to_ms: Optional[int],
        limit: int,
        order: str,
    ) -> Iterable[DashboardEvent]:
        with self.db.session() as session:
            query = session.query(DashboardEvent).filter(DashboardEvent.user_id == user_id)
            if event_category is not None:
                query = query.filter(DashboardEvent.event_category == event_category)
            if source_instance is not None:
                query = query.filter(DashboardEvent.source_instance == source_instance)
            if event_type is not None:
                query = query.filter(DashboardEvent.event_type == event_type)
            if from_ms is not None:
                query = query.filter(DashboardEvent.recorded_at_ms >= from_ms)
            if to_ms is not None:
                query = query.filter(DashboardEvent.recorded_at_ms <= to_ms)
            sort_rule = desc if order == "desc" else asc
            return query.order_by(sort_rule(DashboardEvent.recorded_at_ms)).limit(limit).all()

    def get_latest_events(
        self,
        *,
        user_id: int,
        event_category: Optional[str],
        source_instance: Optional[str],
    ) -> Iterable[DashboardEventLatest]:
        with self.db.session() as session:
            query = session.query(DashboardEventLatest).filter(DashboardEventLatest.user_id == user_id)
            if event_category is not None:
                query = query.filter(DashboardEventLatest.event_category == event_category)
            if source_instance is not None:
                query = query.filter(DashboardEventLatest.source_instance == source_instance)
            return query.order_by(
                DashboardEventLatest.event_category.asc(),
                DashboardEventLatest.source_instance.asc(),
            ).all()
