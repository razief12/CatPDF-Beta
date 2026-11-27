# RC5 Patch 16 / 4.5.6.5.23
Evidence-based fixes after an audit of Patches 11-15 (see AUDIT-REPORT.md). Base: Patch 15 source.
- Backend: bounded, killable conversion workers (worker.py): hard 150 s limit, client-cancel kills the job and any LibreOffice child, real failure reason returned to the UI (no more "check server logs"). API parent no longer imports the heavy engine. /health now lists supported kinds.
- Frontend: cold-start-aware connection (retries through Render's HTML error pages), version mismatch warns instead of blocking, per-phase timeouts, specific HTTP/network error text.
- XLSX->PDF: skip the openpyxl round-trip when it would delete shapes/charts/pivots/etc.; otherwise freeze formulas to the file's own cached values.
- PDF->XLSX: keep the source's decimal places in RM amounts; keep leading zeros (007).
- Scanned-page notices no longer claim "OCR transcription" (no OCR is performed).
- HTML->PDF: allow inline data: URIs only (UNVERIFIED against WeasyPrint 68; see report).
- Dockerfile: Carlito/Caladea (metric-compatible Calibri/Cambria).
- New: diagnose.html (one-click evidence capture), tests/pdf_paths_docker.py (content-verified PDF->X harness; must be run in Docker).
Deploy frontend and backend from the same commit. Not live-tested.
