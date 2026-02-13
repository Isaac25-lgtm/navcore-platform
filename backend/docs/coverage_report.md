# Test Coverage Report

## Current Status
- Executed with `C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe`.
- Test result: `12 passed`.
- Coverage result:
  - `TOTAL 28%` (broad module coverage map; API route integration tests are still limited).
- Covered functional areas include:
  - deterministic allocation logic
  - NAV preview + explainability
  - close-month reconciliation gating
  - lock rule behavior for closed periods

## Run Command
```bash
pytest --cov=app --cov-report=term-missing --cov-report=xml
```
