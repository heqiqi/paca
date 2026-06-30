"""Redis/Valkey event publishing for real-time updates."""

import json
from typing import Any

from app.core.redis import get_redis


async def publish_event(channel: str, event_type: str, payload: dict[str, Any]) -> None:
    """Publish an event to the Redis pub/sub channel for the realtime service."""
    redis = get_redis()
    message = json.dumps({"type": event_type, "payload": payload}, default=str)
    await redis.publish(channel, message)


async def publish_task_event(project_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Publish a task-related event."""
    await publish_event(f"project:{project_id}:tasks", event_type, payload)


async def publish_sprint_event(project_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Publish a sprint-related event."""
    await publish_event(f"project:{project_id}:sprints", event_type, payload)


async def stream_activity(activity_data: dict[str, Any]) -> None:
    """Add an activity record to the Redis stream for async processing."""
    redis = get_redis()
    await redis.xadd("paca:stream:activities", {"data": json.dumps(activity_data, default=str)})


async def stream_notification(notification_data: dict[str, Any]) -> None:
    """Add a notification to the Redis stream for async processing."""
    redis = get_redis()
    await redis.xadd("paca:stream:notifications", {"data": json.dumps(notification_data, default=str)})
