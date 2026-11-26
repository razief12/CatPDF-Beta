# CatPDF RC5 Beta - Patch 6 (frontend 4.5.6.5.13, backend 4.5.6.5.9)

## Changes in this package
- index.html: renderOrganizeInfo restored; applyLang() moved after initialization; hero text says 44 tools (UI Hotfix).
- index.html: card icons mapped by tool ID (TOOL_ICONS) instead of card position (bug #106).
- stability.js: Diagnostic log reported version 4.3.2; now 4.5.6.5.13 (source of the "still says v4.3" observation).
- Metadata (#100): "Remove existing XMP" is now ticked by default so an edited title/author cannot be contradicted by old XMP. Untick to keep XMP.
- interactive-edit.js (v5.0.9): Image Resizer shows an amber warning when the output is larger than the original. Upscaling is still allowed.
- sw.js: cache version 4.5.6.5.13; interactive-edit.js cache key 5.0.9.
- backend-config.js: points to the BETA backend (catpdf-beta-backed). Do NOT copy this file to the production repo.

## Known open items
- #100 XMP synchronisation (rewriting XMP from edited fields) is not implemented; removal is the supported behaviour.

## Release gate
NOT passed. See TEST-RESULTS.txt. Beta must not be promoted to production yet.

## Patch 7 (4.5.6.5.14)
CATPDF-107: selective crop scopes, per-page margins, page navigation and reset controls. Current page default. Existing crop boxes retained for unselected pages. No backend changes. Thumbnail grid deferred.
