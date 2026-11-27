# RC5 Patch19.2
- Conversion worker timeout 300 seconds; browser conversion deadline 330 seconds. Compression timeout unchanged (150 seconds).
- Poll progress every three seconds; retain explicit cancellation.
- Log queue, worker start, completion, timeout and cancellation with elapsed time; no filenames or document content added to these logs.
- Avoid duplicate table detection on initial pages; reuse span centers and row-local cell lookup in editable Word export.
- Add processing note to conversion forms and processing status.
- Supabase auth unchanged. Version 4.5.6.5.28.
- Python/JS syntax checks and synthetic editable table test passed locally. Actual failing PDF not supplied; Render performance, cancellation and visual fidelity not verified live. No guarantee of faster conversion or exact layout.
