from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas.persona_item import PersonaItemSchema
from app.services.persona_item_store import (
    list_deleted_persona_items,
    list_persona_items,
    move_persona_item_to_trash,
    purge_persona_item,
    restore_persona_item,
)
from app.services.profile_store import get_profile

router = APIRouter(prefix="/persona-items", tags=["persona_items"])


@router.get("", response_model=list[PersonaItemSchema])
def read_persona_items(
    profile_id: UUID | None = Query(default=None),
    deleted_only: bool = Query(default=False),
) -> list[PersonaItemSchema]:
    if profile_id is not None:
        get_profile(profile_id)
    if deleted_only:
        return list_deleted_persona_items(profile_id)
    return list_persona_items(profile_id)


@router.delete("/{item_id}", response_model=PersonaItemSchema)
def delete_persona_item_to_trash(item_id: UUID) -> PersonaItemSchema:
    """删除只进入回收站；不级联处理 raw_source。"""

    return move_persona_item_to_trash(item_id)


@router.post("/{item_id}/restore", response_model=PersonaItemSchema)
def restore_deleted_persona_item(item_id: UUID) -> PersonaItemSchema:
    return restore_persona_item(item_id)


@router.delete("/{item_id}/purge", response_model=PersonaItemSchema)
def purge_deleted_persona_item(item_id: UUID) -> PersonaItemSchema:
    """彻底删除单条 persona_item；不级联处理 raw_source。"""

    return purge_persona_item(item_id)
