# CatPDF conversion audit — Patch 15 handover → Patch 16

**Date:** 2026-11-27 · **Scope:** `reconstructed-source` (Beta + patches 11–15), original archives, the two Render log files.
**Not touched:** production CatPDF. **Not available in my sandbox:** PyMuPDF, WeasyPrint, FastAPI, a browser, network, live Render/GitHub Pages. Every claim below is labelled with how it was established.

| Label | Meaning |
|---|---|
| **EXEC** | Real repo code executed here, output inspected with independent tools (poppler, pypdf, pixel diffs) |
| **LOG** | Established from Render logs matched to archive source line numbers |
| **STATIC** | Read from code only; not executed |
| **UNVERIFIED** | Change/claim I could not test |

## 1. Bottom line
1. **The failures in the supplied logs are fully explained, and none is an infrastructure failure.** They are engine decisions: (a) image-only PDFs are rejected — a guard that already exists in **RC4.3 and Beta-main** (LOG+STATIC), not a patch regression; (b) Patch 13's server-side Tesseract (`eng+msa`, 35 s per page) timed out (LOG). The "worker failure" text the UI showed wrapped those engine errors and hid the real reason (STATIC, `app.py` P11–13). The subprocess worker itself succeeded on three `pdfdocx` requests (15:38:24, 15:43:11, 15:47:49).
2. **"Patch 15 still cannot convert" is NOT established.** No log, network trace or failing input post-dates Patch 15; the last log line (15:52:03) still runs Patch 13 code. I found no defect in P15 that would stop a text PDF converting. I did find ways it can *appear* broken (below) — hypotheses until `diagnose.html` output exists.
3. **A scanned PDF can't be "editably converted" on this hosting by design.** P15 returns a Word file with the page image + a notice (no content silently lost in DOCX; TXT/MD/XLSX contain only the notice). If the user's real files are scans (the five 422s at 15:21–15:22 were image-only rejects), "converts" ≠ "text extracted". Real OCR needs the browser (tesseract.js already ships in the OCR Scanner) or a job queue; not implemented.
4. **Real, reproduced defects were found in paths that *do* run** (XLSX→PDF, frontend gate, cancel). Fixed in Patch 16 and tested to the extent possible (§4).

## 2. Log ↔ source mapping (LOG)
| Log time | Evidence | Deployed code |
|---|---|---|
| 15:35–15:36 | traceback `job_runner.py:8` → `engine.py:201` = `raise ValueError('Image-only page detected…')`. Line 201 is exactly that statement in **RC4.3 and Beta-main** `engine.py` | worker app (P11/12) + baseline engine |
| 15:38, 15:43, 15:47 | `POST /convert/pdfdocx 200` | worker architecture **worked** |
| 15:49:50, 15:52:03 | `engine.py:163` `subprocess.run(['tesseract'…timeout=35)`, `:255 ocr_page(p)` — both match **Patch 13** `engine.py` exactly | Patch 13 |
| every ~5 min after deploy | `Detected service running on port 10000` | Render's port scan, benign — **not** a crash |
`pptxpdf` (15:10:27) and `htmlpdf` (15:13:26) show HTTP 200 only; content was never verified.

## 3. Findings
| ID | Sev | Finding | Evidence | Status |
|---|---|---|---|---|
| F-01 | High | XLSX→PDF silently **deletes shapes/text boxes** (openpyxl round-trip). Text box present in raw LibreOffice, absent via `office()` | EXEC | **Fixed**, tested |
| F-02 | High | XLSX→PDF **changes displayed values**: formula cached `5` rendered as `2` (cached values stripped → recalculated) | EXEC | **Fixed**, tested (drawing-free case) |
| F-03 | High | PDF→XLSX forces `"RM" #,##0.00`: `RM 1,234.567`→`1,234.57`, `RM 99.999`→`100.00`, `RM 1,234`→`1,234.00`; `007`→`7` | EXEC on exact rule lines + real openpyxl/LO; full engine path not run | **Fixed** (2 lines) |
| F-04 | High | PDF→Word/Excel/Markdown **drop images and vector graphics on pages that have text** (`page_blocks` skips image blocks); only scanned pages keep an image (Word). No warning | STATIC | **Not fixed**; harness probe `[AUDIT S1]` |
| F-05 | High | Frontend gate: exact `version===` equality blocks all conversion when backend is one build behind; during Render spin-up `await health.json()` surfaces a raw JSON `SyntaxError` | EXEC (verbatim logic reproduced) | **Fixed**, 13/13 tests |
| F-06 | High | P15 thread execution: no server timeout, cancel only abandons the wait, single slot ⇒ Cancel→retry queues behind the abandoned job (CATPDF-109/110/111 mechanism) | STATIC | **Fixed** (worker.py), supervisor 10/10; disconnect detection under real uvicorn UNVERIFIED |
| F-07 | Med | Dockerfile lacks Calibri/Cambria metric fonts: with a Docker-equivalent fontconfig, 6/7 pages of a Calibri doc start at different text (no content loss, same page count in this sample) | EXEC (LO 24.2 emulation; prod LO is older) | Fixed in Dockerfile; image build UNVERIFIED |
| F-08 | Med | `no_fetch` probably blocks `data:` URIs ⇒ base64 images in user HTML (and CatPDF's own HTML exports) vanish in HTML→PDF | STATIC | Fix applied, **UNVERIFIED** (harmless if WeasyPrint already handled it) |
| F-09 | Med | Word export takes page size/orientation from page 1 only; PPTX slide size from page 1; Excel column widths are overwritten per table | STATIC | Not fixed; harness probe `[AUDIT S4]` |
| F-10 | Med | Scanned-page notices said "OCR transcription (review accuracy)" though no OCR runs | STATIC | **Fixed** (honest wording) |
| F-11 | Low | Server image endpoints (`jpgpng`,`pngjpg`,`webp`,`imgpdf`,`pdftxt`,`pdfimg`) are **not called by the UI**. Latent: DPI dropped; `imgpdf` makes an A4@300dpi PNG a 875×1238 mm page and re-encodes lossless PNG as JPEG (max err 156/255); >20 MP rejected explicitly | EXEC | Not fixed (dead code) |
| F-12 | Perf | `page_blocks` re-extracts the page once per text block and runs `find_tables` twice → likely CPU-heavy on a 0.1-CPU free instance | STATIC, unmeasured | Not changed: can't prove output equivalence without PyMuPDF |
| Note | — | `clean_cell` re-joins `SECTIO\nN`→`SECTION`, `SUBTO\nTAL`→`SUBTOTAL`: sample-specific heuristic, restores wrapped words | EXEC | Left, disclosed |

## 4. Converter status (a PASS needs evidence; HTTP 200 does not count)
| Converter | Status | Evidence |
|---|---|---|
| DOCX→PDF | **PASS (synthetic)** | 24/24: 20 text/Unicode/number tokens incl. header/footer/merged cell, 3 pages, Letter + landscape section sizes, 1 image |
| PPTX→PDF | **PASS (synthetic)** | 11/11: 3 slides, 960×540 pt, table/Unicode/picture. (Speaker notes are not in PDF output — normal) |
| XLSX→PDF | P15 **FAIL** (F-01, F-02) → P16 **PASS** on tested files | differential vs raw LibreOffice; pagination differs from raw LO only on sheets without explicit print setup (intentional fit-to-width) |
| PDF→Word / Excel / PPT / HTML Preserve / HTML Editable / Markdown / Text / Image | **NOT TESTED** | need PyMuPDF. Run `tests/pdf_paths_docker.py` |
| TXT→PDF, HTML→PDF | **NOT TESTED** | need WeasyPrint |
| Advanced compression, mobile visual editing, JPG↔PNG/WebP in browser | **NOT TESTED** | need browser / PyMuPDF |
Image engine (server): JPG→PNG pixel-identical **PASS**; WebP lossless **PASS** (visible pixels identical); PNG→JPG lossy by design (q95, flattens alpha to white).

**Gaps vs your mandatory requirements:** "Preserve Original Layout" vs "Editable" modes exist only for HTML; Word/Excel are editable reconstructions (fonts, colours, lists, hyperlinks, headers/footers of text are not carried); PowerPoint is image-only. These are existing limits, disclosed here, not changed.

## 5. What Patch 16 changes
`app.py`, `worker.py`(new), `kinds.py`(new), `engine.py`, `conversion.js`, `stability.js`, `sw.js`, `index.html`, `Dockerfile`, `.dockerignore`(new), `diagnose.html`(new), `tests/`(new). `job_runner.py` unchanged. Version 4.5.6.5.23 in all five places.

## 6. Tests actually executed — `TEST-RESULTS.txt` (80 PASS / 3 FAIL)
The 3 FAILs are F-11, deliberately left visible. Self-tests found two bugs in *my own* code and one overly-strict check of mine, all corrected before release. **Not exercised:** FastAPI routing/CORS/multipart, `request.is_disconnected` under uvicorn, Docker build, Render, browser UI/service worker, Debian's LibreOffice 7.4 (I ran 24.2).

## 7. Deploy
1. Tag the current commit (`git tag pre-patch16`).
2. Copy the Patch 16 files over the repo; push. Render rebuilds (new apt fonts ⇒ slower first build); Pages updates separately. Gate is now non-blocking, so order doesn't matter.
3. In the app: **Clear Cache** (cache name changed), then open `…/CatPDF-Beta/diagnose.html` → *Run diagnostics* → send me the report (needs ≤ ~3 min on a sleeping server).
4. In Docker: `python tests/pdf_paths_docker.py` (confirms/refutes F-04, F-09, and F-03's full path). HTML→PDF `data:` check: `pdfimages -list` on a PDF made from `<img src="data:image/png;base64,…">`.

## 8. Rollback
`git revert` the Patch 16 commit (or redeploy `pre-patch16`). Reverting re-introduces the exact-version gate: frontend and backend must then be reverted together.

## 9. Unresolved
Server OCR for scans (needs browser-side OCR or a job queue); F-04/F-09 content loss in PDF→Word/Excel/Markdown; F-12 performance; non-Latin fonts (no CJK/Arabic/Thai fonts in image); cold start remains 50 s+ (now handled, not removed); the real Patch 15 failure, pending evidence.
