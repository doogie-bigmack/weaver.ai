# Library and API Deprecation Audit Report
**Date:** 2025-10-03
**Project:** weaver.ai
**Scope:** Codebase-wide review of outdated libraries and deprecated API patterns

---

## Executive Summary

This audit identified **4 critical deprecated patterns** and **2 medium-priority updates** across the weaver.ai codebase. The main issues involve:

1. **Pydantic V2 deprecated methods** (`.json()`, `.parse_raw()`, `.dict()`)
2. **pytest-asyncio fixture decorator pattern** (missing `loop_scope` parameter)
3. **Redis asyncio connection management** (proper cleanup patterns)
4. **FastAPI lifespan management** (already using modern `@asynccontextmanager` - ✅ GOOD)

**Priority Level Distribution:**
- 🔴 Critical: 2 issues
- 🟠 High: 1 issue
- 🟡 Medium: 1 issue
- ✅ Good: Modern patterns already in use

---

## Detailed Findings

### 🔴 CRITICAL PRIORITY

#### 1. Pydantic V2 Deprecated Serialization Methods

**Issue:** The codebase uses deprecated Pydantic V1 methods that are removed/deprecated in Pydantic V2.

**Affected Locations:**

**`.json()` → `.model_dump_json()`**
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/mesh.py:105` - `event.json()`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/mesh.py:112` - `event.json()`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/queue.py:63` - `task.json()`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/queue.py:163` - `task.json()`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/queue.py:172` - `task.json()`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/queue.py:179` - `task.json()`

**`.parse_raw()` → `.model_validate_json()`**
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/mesh.py:174` - `Event.parse_raw(event_data)`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/queue.py:135` - `Task.parse_raw(task_json)`

**`.dict()` → `.model_dump()`**
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/mesh.py:241` - `task.dict()`

**Current Code Example:**
```python
# DEPRECATED ❌
await self.redis.publish(channel, event.json())
event = Event.parse_raw(event_data)
task_data = task.dict()
```

**Recommended Fix:**
```python
# MODERN ✅
await self.redis.publish(channel, event.model_dump_json())
event = Event.model_validate_json(event_data)
task_data = task.model_dump()
```

**Impact:**
- Currently using Pydantic 2.8+, these methods may emit deprecation warnings
- Future Pydantic versions will remove these methods entirely
- JSON serialization output format may differ slightly (V2 is more compact)

**Migration Notes:**
- `model_dump_json()` produces more compact JSON than `json()` (no spaces after separators)
- `model_validate_json()` is stricter about JSON types vs Python types
- `model_dump()` replaces `dict()` with same functionality

---

#### 2. pytest-asyncio Fixture Decorator Pattern

**Issue:** Using deprecated `@pytest_asyncio.fixture` without the required `loop_scope` parameter in pytest-asyncio 0.23+.

**Affected Locations:**
- `/Users/damon.mcdougald/conductor/weaver.ai/tests/test_memory_persistence.py:18` - `@pytest_asyncio.fixture` (redis_client)
- `/Users/damon.mcdougald/conductor/weaver.ai/tests/test_memory_persistence.py:26` - `@pytest_asyncio.fixture` (memory)
- Multiple test files using `@pytest.mark.asyncio` without configuration

**Current Code Example:**
```python
# DEPRECATED ❌
@pytest_asyncio.fixture
async def redis_client(self):
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()

@pytest.mark.asyncio
async def test_something(self):
    ...
```

**Recommended Fix:**
```python
# MODERN ✅
@pytest_asyncio.fixture(loop_scope="function")
async def redis_client(self):
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()

# Add to pyproject.toml:
# [tool.pytest.ini_options]
# asyncio_default_fixture_loop_scope = "function"
# asyncio_mode = "auto"
```

**Impact:**
- Deprecation warnings in pytest output
- Future pytest-asyncio versions (0.24+) will require explicit `loop_scope`
- Tests may fail or behave unpredictably without proper event loop scoping

**Configuration Required in pyproject.toml:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--strict-markers"
asyncio_default_fixture_loop_scope = "function"  # ADD THIS
asyncio_mode = "auto"  # ADD THIS
```

---

### 🟠 HIGH PRIORITY

#### 3. Redis Asyncio Connection Cleanup Pattern

**Issue:** While the codebase generally follows good patterns with `aclose()`, there's inconsistent usage of connection pool cleanup and potential resource leaks.

**Affected Locations:**
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/mesh.py` - Connection cleanup in `disconnect()`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/cache/redis_cache.py` - Connection cleanup in `disconnect()`
- `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/queue.py` - No explicit connection management

**Current Pattern (Good ✅):**
```python
# In redis_cache.py
async def disconnect(self) -> None:
    if self.client:
        await self.client.close()  # ✅ Good
        self._connected = False
```

**Recommended Enhancement:**
```python
# Modern pattern with connection pool cleanup
async def disconnect(self) -> None:
    if self.client:
        await self.client.aclose()  # Use aclose() for async cleanup
        self._connected = False

# For connection pools
async def disconnect(self) -> None:
    if self.pubsub:
        await self.pubsub.close()
    if self.redis:
        await self.redis.aclose()  # aclose() is the modern method
    self._connected = False
```

**Current Usage:**
- `redis_mesh.py:59` - Uses `await self.redis.close()` ✅
- `redis_cache.py:84` - Uses `await self.client.close()` ✅

**Recommendation:**
- Update to use `aclose()` instead of `close()` (modern asyncio pattern)
- Ensure all connection pools are properly closed
- Add context manager support for automatic cleanup

---

### 🟡 MEDIUM PRIORITY

#### 4. FastAPI Response Models and HTTPException

**Current State:** ✅ The codebase is already using modern FastAPI patterns!

**Good Patterns Found:**
```python
# gateway_cached.py - EXCELLENT ✅
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global model_router
    # Startup
    cache_config = CacheConfig(...)
    yield
    # Shutdown
    await cleanup()
```

**No Deprecated Patterns Found:**
- ✅ Using `@asynccontextmanager` for lifespan (modern)
- ✅ NOT using deprecated `@app.on_event("startup")` or `@app.on_event("shutdown")`
- ✅ Proper exception handling with `HTTPException`

---

## Additional Observations

### ✅ Good Practices Already in Use

1. **FastAPI Lifespan Management** - Using modern `@asynccontextmanager` pattern
2. **Type Annotations** - Extensive use of modern Python 3.12 type hints
3. **Pydantic V2 BaseModel** - Core models already use Pydantic V2
4. **Async/Await Patterns** - Consistent async patterns throughout

### ⚠️ Version Constraints Review

**Current Dependencies (pyproject.toml):**
```toml
pydantic>=2.8          # ✅ Modern version
pytest>=8              # ✅ Up to date
pytest-asyncio>=0.23   # ⚠️ Needs configuration updates
redis>=5.0             # ✅ Modern asyncio support
fastapi>=0.115         # ✅ Latest features
httpx>=0.27            # ✅ Modern async client
```

**Recommendations:**
- Keep current version constraints
- Add pytest-asyncio configuration to pyproject.toml
- Consider pinning upper bounds for production stability

---

## Migration Priority Roadmap

### Phase 1: Critical Fixes (Do Immediately)
1. **Update Pydantic serialization methods** (2-4 hours)
   - Replace `.json()` → `.model_dump_json()`
   - Replace `.parse_raw()` → `.model_validate_json()`
   - Replace `.dict()` → `.model_dump()`
   - Run full test suite to verify

2. **Add pytest-asyncio configuration** (30 minutes)
   - Update `pyproject.toml` with `asyncio_default_fixture_loop_scope`
   - Add `loop_scope="function"` to all `@pytest_asyncio.fixture` decorators
   - Run test suite to verify

### Phase 2: High Priority (Next Sprint)
3. **Standardize Redis connection cleanup** (1-2 hours)
   - Update all `.close()` → `.aclose()`
   - Add context manager support where missing
   - Test connection lifecycle

### Phase 3: Documentation & Best Practices (Ongoing)
4. **Update development guidelines**
   - Document modern Pydantic V2 patterns
   - Add pytest-asyncio best practices
   - Create migration guide for new developers

---

## Testing Strategy

### Pre-Migration Testing
```bash
# Verify current state
pytest tests/ -v
pytest tests/ -W error::DeprecationWarning  # Fail on deprecation warnings
```

### Post-Migration Validation
```bash
# Run full test suite
pytest tests/ -v --tb=short

# Check for any remaining deprecation warnings
pytest tests/ -W error::DeprecationWarning

# Run type checking
mypy weaver_ai/

# Performance regression tests
pytest tests/performance/ -v
```

---

## Code Examples for Common Patterns

### Pydantic V2 Serialization Pattern

```python
from pydantic import BaseModel

class Event(BaseModel):
    event_type: str
    data: dict

# ❌ DEPRECATED
event_json = event.json()
event_dict = event.dict()
parsed = Event.parse_raw(json_string)

# ✅ MODERN
event_json = event.model_dump_json()
event_dict = event.model_dump()
parsed = Event.model_validate_json(json_string)

# Advanced: with options
event_json = event.model_dump_json(exclude_unset=True)
event_dict = event.model_dump(exclude={'password'}, mode='json')
```

### pytest-asyncio Fixture Pattern

```python
import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis

# ❌ DEPRECATED
@pytest_asyncio.fixture
async def redis_client():
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()

# ✅ MODERN
@pytest_asyncio.fixture(loop_scope="function")
async def redis_client():
    client = FakeAsyncRedis(decode_responses=True)
    yield client
    await client.aclose()

# For class-scoped fixtures
@pytest_asyncio.fixture(loop_scope="class", scope="class")
async def shared_resource():
    resource = await create_resource()
    yield resource
    await resource.cleanup()
```

### Redis Async Connection Pattern

```python
import redis.asyncio as redis

# ❌ OLD
async def connect():
    client = await redis.from_url("redis://localhost")
    # ... use client
    await client.close()  # Old method

# ✅ MODERN
async def connect():
    client = await redis.from_url("redis://localhost")
    try:
        # ... use client
    finally:
        await client.aclose()  # Modern method

# ✅ BEST - Context manager
async def connect():
    async with redis.from_url("redis://localhost") as client:
        # ... use client
    # Automatically closed
```

---

## Files Requiring Updates

### High Priority Files (Critical Updates)
1. `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/mesh.py`
   - Lines 105, 112, 174, 241
   - Update: `.json()` → `.model_dump_json()`, `.parse_raw()` → `.model_validate_json()`, `.dict()` → `.model_dump()`

2. `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/queue.py`
   - Lines 63, 135, 163, 172, 179
   - Update: `.json()` → `.model_dump_json()`, `.parse_raw()` → `.model_validate_json()`

3. `/Users/damon.mcdougald/conductor/weaver.ai/tests/test_memory_persistence.py`
   - Lines 18, 26
   - Update: Add `loop_scope="function"` to fixtures

4. `/Users/damon.mcdougald/conductor/weaver.ai/pyproject.toml`
   - Add pytest-asyncio configuration

### Medium Priority Files (Enhancement Updates)
5. `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/cache/redis_cache.py`
   - Line 84 - Update: `.close()` → `.aclose()`

6. `/Users/damon.mcdougald/conductor/weaver.ai/weaver_ai/redis/mesh.py`
   - Line 59 - Update: `.close()` → `.aclose()`

---

## Risk Assessment

### Low Risk (Safe to Update)
- ✅ Pydantic method replacements (1:1 equivalents)
- ✅ pytest-asyncio configuration (backward compatible)
- ✅ Redis `aclose()` method (modern equivalent)

### Medium Risk (Test Thoroughly)
- ⚠️ JSON serialization format changes (V2 is more compact)
- ⚠️ Event loop scoping in tests (may affect test isolation)

### No Breaking Changes Expected
- ✅ All changes are drop-in replacements
- ✅ No API signature changes required
- ✅ Existing functionality preserved

---

## Appendix: Library Documentation References

### Pydantic V2
- **Migration Guide:** https://docs.pydantic.dev/latest/migration/
- **Serialization:** https://docs.pydantic.dev/latest/concepts/serialization/
- **Key Changes:**
  - `.json()` → `.model_dump_json()`
  - `.dict()` → `.model_dump()`
  - `.parse_raw()` → `.model_validate_json()`
  - `.parse_obj()` → `.model_validate()`

### pytest-asyncio
- **Repository:** https://github.com/pytest-dev/pytest-asyncio
- **Migration from 0.23:** https://github.com/pytest-dev/pytest-asyncio/blob/main/docs/how-to-guides/migrate_from_0_23.rst
- **Key Changes:**
  - `scope` argument deprecated → use `loop_scope`
  - Must set `asyncio_default_fixture_loop_scope` in config
  - Recommended: `asyncio_mode = "auto"`

### redis-py (asyncio)
- **Repository:** https://github.com/redis/redis-py
- **Async Guide:** https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
- **Key Patterns:**
  - Use `aclose()` instead of `close()` for async clients
  - Proper connection pool cleanup required
  - Context manager support recommended

---

## Conclusion

The weaver.ai codebase is generally well-maintained with modern patterns, but requires updates to align with the latest library APIs. The critical issues are straightforward to fix and carry minimal risk. The recommended migration can be completed in 1-2 days with thorough testing.

**Immediate Action Items:**
1. ✅ Update Pydantic serialization methods (4-6 locations)
2. ✅ Add pytest-asyncio configuration
3. ✅ Update Redis connection cleanup patterns
4. ✅ Run comprehensive test suite
5. ✅ Update documentation

**Estimated Total Effort:** 4-6 hours of development + 2-3 hours of testing

---

*Report generated: 2025-10-03*
*Audited by: Claude Code (Anthropic)*
