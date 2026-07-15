from __future__ import annotations

from fastapi import APIRouter

from app.schemas.feature_policy import FeaturePolicy, FeaturePolicyUpdate
from app.services.feature_policy_store import (
    get_feature_policy,
    list_feature_policies,
    reset_feature_policy,
    update_feature_policy,
)

router = APIRouter(prefix="/feature-policies", tags=["feature_policies"])


@router.get("", response_model=list[FeaturePolicy])
def read_feature_policies() -> list[FeaturePolicy]:
    return list_feature_policies()


@router.get("/{feature_key}", response_model=FeaturePolicy)
def read_feature_policy(feature_key: str) -> FeaturePolicy:
    return get_feature_policy(feature_key)


@router.patch("/{feature_key}", response_model=FeaturePolicy)
def patch_feature_policy(feature_key: str, payload: FeaturePolicyUpdate) -> FeaturePolicy:
    return update_feature_policy(feature_key, payload)


@router.post("/{feature_key}/reset", response_model=FeaturePolicy)
def reset_policy(feature_key: str) -> FeaturePolicy:
    return reset_feature_policy(feature_key)
