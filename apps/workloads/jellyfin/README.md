# Jellyfin recovery validation

The verified archive extract is intentionally outside Git at:

`C:\Users\Joeri\OneDrive\Bureaublad\downloadbox-config\jellyfin-restore-validation-20260803\downloadbox-state\config\jellyfin`

The chart is initially scaled to zero so that Jellyfin cannot initialise an empty server before recovery.

1. Sync this application so that the `jellyfin-config` PVC is bound.
2. Set `restoreHelper.enabled: true` and sync. Wait for the `jellyfin-restore-helper` pod to be ready.
3. Copy the *contents* of the staged `jellyfin` directory into `/config` in that helper pod, preserving the directory structure.
4. Set `restoreHelper.enabled: false` and `replicaCount: 1`, then sync.
5. Validate the existing user logins and watched/resume state before adding any media storage.

Do not delete, replace, or initialise the PVC during this validation.
