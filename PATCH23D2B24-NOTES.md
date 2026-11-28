# Patch23D2B2.4
Root cause: document capture-phase busy-panel click guard blocked Cancel before its handler. Exempt only the global Cancel processing button; retain all other guard behavior. Cache namespace .45; JS asset versions and backend unchanged. Mock guard and conversion tests pass; live browser and worker cancellation pending.
