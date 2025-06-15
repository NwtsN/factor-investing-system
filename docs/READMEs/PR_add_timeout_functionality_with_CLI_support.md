# Pull Request: Add Timeout Functionality with CLI Support

**Branch**: `features/program-timeout`  
**Author**: Neil Watson (`@NwtsN`)  
**Date**: 15 June 2025

---

## 📌 Overview

This PR introduces a robust **program timeout mechanism** with **command-line interface (CLI) support**, enabling users to set a maximum runtime for the data fetcher system. This is particularly useful for long-running fetch operations where API hangups or excessive compute time could block system resources.

---

## 🎯 Goals

- Add a timeout system that gracefully exits the program if it exceeds a user-specified time limit.
- Provide CLI integration to allow users to pass a timeout duration via flags.
- Ensure seamless integration with the existing `DatabaseManager` and logging infrastructure.

---

## 🔧 Key Features and Changes

### 🚀 New Functionality

- **Timeout Class** (`utils/program_timer.py`):
  - Implements a context manager to enforce time limits using threading-based logic (for cross-platform compatibility).
  - Includes safe teardown and exception handling to exit the program cleanly when timeout is reached.

- **Command-Line Interface Integration**:
  - Added `--timeout` (or `-t`) argument to `main.py`.
  - Timeout is specified in **minutes** (validated to be a positive float or integer).
  - If no timeout is provided, the system runs indefinitely as before.

### 🧠 Code Integration

- Introduced logic:
```python
with (timeout_context if timeout_context else contextlib.nullcontext()):
    with DatabaseManager() as db:
        logger = db.get_logger(session_id)
        data_manager = DataManager(db.conn, logger)
```

- This allows conditional timeout usage without duplicating control flow.
- Ensures the logging and DB context stack is respected and safely exited, even under timeout.

---

## 🧹 Refactors & Fixes

- Cleaned up type hints in `main.py` and related modules to support new logic.
- Resolved threading-related implementation bugs and ensured no lingering threads remain after timeout exit.
- Added validation logic to catch invalid timeout inputs early and inform the user via logger.

---

## 🧪 Testing

- Manually tested by simulating long-running fetch operations and confirming:
  - Program exits gracefully after timeout
  - Log entries show timeout was hit and operation cancelled
  - CLI refuses invalid inputs (e.g. negative numbers, non-numeric strings)
- Also tested normal operations with no timeout to confirm backward compatibility

---

## ⚠️ Risks & Considerations

- Threading-based timeout is **cross-platform safe**, but relies on clean resource shutdown (handled via context managers).
- Timeout **does not currently interrupt I/O-bound blocking calls** — future enhancement could explore `asyncio` or signal-based logic for that.
- Users running the program in interactive or GUI-based environments must be aware that forced exits may interfere with unsaved work.

---

## 🔁 Follow-Up Work

- Add unit tests for the `Timeout` class and timeout-enabled main workflow.
- Improve user feedback when timeout is hit (e.g., CLI message and structured logger warning).
- Consider making timeout default configurable via settings or environment variable.

---

## ✅ Checklist

```markdown
- [x] Timeout mechanism implemented as context manager
- [x] CLI argument parsing added
- [x] Input validation and error handling included
- [x] Logging integrates with existing session logger
- [x] Manual testing completed
- [ ] Unit tests still to be added
```

---

## 🔗 Related Commit

- `594115a`: `feat: add program timeout functionality with CLI support`

