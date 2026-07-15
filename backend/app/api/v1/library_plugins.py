from __future__ import annotations

from fastapi import APIRouter

from app.schemas.library_plugin import (
    LibraryPluginCatalog,
    LibraryPluginPolicy,
    LibraryPluginPolicyUpdate,
    LibraryPluginRegistryResponse,
)
from app.services.library_plugin_store import (
    current_library_catalog,
    get_current_library_policy,
    list_library_plugins,
    reset_current_library_policy,
    update_current_library_policy,
)

router = APIRouter(prefix="/library-plugins", tags=["library_plugins"])


@router.get("", response_model=LibraryPluginRegistryResponse)
def read_library_plugins() -> LibraryPluginRegistryResponse:
    return list_library_plugins()


@router.get("/current", response_model=LibraryPluginPolicy)
def read_current_library_plugin() -> LibraryPluginPolicy:
    return get_current_library_policy()


@router.patch("/current", response_model=LibraryPluginPolicy)
def patch_current_library_plugin(payload: LibraryPluginPolicyUpdate) -> LibraryPluginPolicy:
    return update_current_library_policy(payload)


@router.post("/current/reset", response_model=LibraryPluginPolicy)
def reset_current_library_plugin() -> LibraryPluginPolicy:
    return reset_current_library_policy()


@router.get("/current/catalog", response_model=LibraryPluginCatalog)
def read_current_library_catalog() -> LibraryPluginCatalog:
    return current_library_catalog()
