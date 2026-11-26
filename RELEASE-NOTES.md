# CatPDF RC5 Beta - Audit Patch 3 + UI Hotfix + Icon Fix (frontend 4.5.6.5.11, backend 4.5.6.5.9)

## Changes in this package
- index.html: renderOrganizeInfo restored; applyLang() moved after initialization; hero text says 44 tools (UI Hotfix).
- index.html: card icons are now mapped by tool ID (TOOL_ICONS). Previously icons were assigned by card position from only 6 shapes (bug #106).
- sw.js: cache version 4.5.6.5.11 so browsers refresh.
- backend-config.js: points to the BETA backend (catpdf-beta-backed). The original Audit Patch 3 zip pointed to production. Do NOT copy this file to the production repo.

## Verified in headless Chromium (2026-11-26)
- Page loads with no uncaught JavaScript errors; 44 tool shells; 19 unified cards visible; 19 distinct icons.
- Split: pages 3,4,5 clicked in order 5,3,4 -> output 3 pages, ascending (3,4,5), correct sizes, text selectable.
- Organize state machine + save: reverse, delete, duplicate, add blank, rotate -> 8-page output, order and rotation as expected.

## Limits of this verification
- pdf-lib and pdf.js were served from local copies (pdf.js 6.2.108, app requests 4.10.38). Real CDN behaviour not tested.
- Not tested: Crop, Sign, Metadata/XMP, Standard/Advanced compression, Image resize/crop, mobile, dark mode, backend conversions, rotated-page Crop/Sign.
- Release gate NOT passed. Beta must not be promoted to production yet.
