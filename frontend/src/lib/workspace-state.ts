export const ACTIVE_PROFILE_STORAGE_KEY = "memory-workbench-active-profile-id";
export const WORKSPACE_PROFILE_EVENT = "memory-workbench-profile-change";
export const WORKSPACE_STATUS_EVENT = "memory-workbench-status-refresh";

type ProfileChangeDetail = {
  profileId: string | null;
};

export function readActiveProfileId() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACTIVE_PROFILE_STORAGE_KEY);
}

export function setActiveProfileId(profileId: string | null) {
  if (typeof window === "undefined") {
    return;
  }
  if (profileId) {
    window.localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, profileId);
  } else {
    window.localStorage.removeItem(ACTIVE_PROFILE_STORAGE_KEY);
  }
  window.dispatchEvent(
    new CustomEvent<ProfileChangeDetail>(WORKSPACE_PROFILE_EVENT, {
      detail: { profileId },
    }),
  );
}

export function notifyWorkspaceStatusChanged(profileId?: string | null) {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(
    new CustomEvent<ProfileChangeDetail>(WORKSPACE_STATUS_EVENT, {
      detail: { profileId: profileId ?? readActiveProfileId() },
    }),
  );
}
