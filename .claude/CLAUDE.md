# IFSCA Exam Prep - CRITICAL Workspace Rules for Claude

## ⚠️ CRITICAL ENFORCEMENT: CONTEXT7 MCP IS MANDATORY

**THIS RULE IS ABSOLUTE, NON-NEGOTIABLE, AND BINDING ON ALL CODE WRITING**

**STATUS**: ACTIVE | EFFECTIVE: 2026-05-12+ | ENFORCEMENT: AUTOMATIC | OVERRIDE: IMPOSSIBLE

---

## The Mandatory Rule

### BEFORE WRITING ANY CODE - WITHOUT EXCEPTION:

1. **IDENTIFY** → What technology/library? (FastAPI, SQLite, Python asyncio, Pydantic, pytest, etc.)
2. **SEARCH CONTEXT7** → Use mcp__context7__resolve-library-id
3. **QUERY CONTEXT7** → Use mcp__context7__query-docs for your specific use case
4. **REVIEW DOCS** → Study patterns, examples, security notes, performance tips
5. **WRITE CODE** → Follow Context7 verified patterns EXACTLY
6. **CITE SOURCE** → Reference "Per Context7 docs for {library}: {pattern}"

### APPLIES TO
- ✅ ALL code writing (backend, frontend, tests, infrastructure)
- ✅ ALL modifications (refactoring, bug fixes, features)
- ✅ ALL new functions, endpoints, database operations
- ✅ ALL async/concurrent code
- ✅ ALL error handling code
- ✅ ALL security-sensitive code
- ✅ ALL performance optimization code

### NO EXCEPTIONS FOR
- ❌ "I'm in a hurry" → Context7 takes 30 seconds, prevents hours of debugging
- ❌ "I already know this" → Verify against latest 2026 patterns
- ❌ "Simple change" → Small code can have big security implications
- ❌ "Local utilities" → Still use Context7 for pattern verification
- ❌ "Time pressure" → Rule applies regardless of deadline

---

## How Context7 Works: Step-by-Step

### Step 1: Resolve Library to Context7 ID

```python
libraryId = mcp__context7__resolve-library-id(
    libraryName="FastAPI",      # Or: SQLite, Python asyncio, Pydantic, etc.
    query="specific use case"    # What you're trying to do
)
# Returns: libraryId = "/tiangolo/fastapi"
```

### Step 2: Query Documentation

```python
docs = mcp__context7__query-docs(
    libraryId="/tiangolo/fastapi",
    query="async database connections with error handling and resource cleanup"
)
# Returns: Latest patterns, code examples, best practices, warnings
```

### Step 3: Review & Understand

Before writing code, you should understand:
- ✅ Latest recommended pattern (might be different from 2024)
- ✅ Security considerations
- ✅ Performance implications
- ✅ Version compatibility
- ✅ Common pitfalls to avoid
- ✅ Code examples matching your use case

### Step 4: Write Code Following Context7

Write code ONLY after understanding Context7 documentation.

### Step 5: Reference the Source

Every code output should include:
```
"Per Context7 docs for FastAPI: use asynccontextmanager for resource cleanup"
```

---

## Real Examples from This Project

### Example 1: Database Connection Cleanup

**BEFORE Context7 (RISKY)**:
```python
def get_weak_topics():
    conn = sqlite3.connect("db.db")
    result = conn.execute("SELECT ...").fetchall()
    # FORGOT to close connection! LEAK!
    return result
```

**AFTER Context7 (CORRECT)**:
```python
def get_weak_topics():
    conn = sqlite3.connect("db.db")
    try:
        result = conn.execute("SELECT ...").fetchall()
        return result
    finally:
        conn.close()  # ALWAYS closes, even on error

# Source: "Per Context7 docs for SQLite: use try/finally for connection cleanup"
```

### Example 2: Async Resource Management

**BEFORE Context7 (RISKY)**:
```python
@asynccontextmanager
async def get_session():
    session = create_session()
    yield session
    # FORGOT to close in error case!
```

**AFTER Context7 (CORRECT)**:
```python
@asynccontextmanager
async def get_session():
    session = create_session()
    try:
        yield session
    finally:
        await session.close()  # ALWAYS closes

# Source: "Per Context7 docs for Python asyncio: use try/finally in async context managers"
```

### Example 3: FastAPI Error Handling

**BEFORE Context7 (INCOMPLETE)**:
```python
@app.post("/api/exams/submit")
async def submit_exam(request: Request):
    result = process(request)
    return result  # What if process() fails?
```

**AFTER Context7 (ROBUST)**:
```python
@app.post("/api/exams/submit")
async def submit_exam(request: SubmitRequest):
    try:
        if not validate(request):
            raise HTTPException(status_code=400, detail="Invalid request")
        result = process(request)
        return result
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

# Source: "Per Context7 docs for FastAPI: proper exception handling in async endpoints"
```

---

## Technologies in This Workspace (Always Use Context7)

| Tech | Use | Query Examples |
|------|-----|-----------------|
| **FastAPI** | Web API | "async endpoints error handling", "dependency injection", "response models" |
| **SQLite** | Database | "connection lifecycle", "parameterized queries", "transactions" |
| **Python asyncio** | Async code | "async context managers", "exception handling", "task management" |
| **Pydantic** | Validation | "model validation", "custom validators", "serialization" |
| **pytest** | Testing | "async fixtures", "mocking patterns", "test organization" |
| **Claude API** | AI integration | "streaming responses", "error handling", "token optimization" |
| **Python typing** | Type hints | "modern union syntax", "type annotation best practices" |

---

## Enforcement Mechanism

### HOW CLAUDE FOLLOWS THIS RULE

```
Conversation Start
    ↓
Claude reads .claude/CLAUDE.md
    ↓
Claude loads rule into memory
    ↓
User requests code change
    ↓
Claude thinks: "This is code, therefore Context7 is mandatory"
    ↓
Claude identifies technology (FastAPI, SQLite, etc.)
    ↓
Claude searches Context7 MCP
    ↓
Claude reviews documentation
    ↓
Claude writes code following verified patterns
    ↓
Claude cites: "Per Context7 docs..."
    ↓
User receives code that follows best practices
```

### WHY THIS WORKS

1. **Automatic**: Claude reads CLAUDE.md at every conversation start
2. **Binding**: Workspace rules cannot be overridden
3. **Persistent**: Applies to all conversations in this workspace
4. **Transparent**: Clear, explicit language
5. **Verifiable**: Output always cites Context7 source

---

## What Happens If Context7 Doesn't Have Info

**Scenario**: You need a pattern for a very new or obscure library

**Solution**:
1. Still attempt Context7 search (framework might be there)
2. If unavailable, document the search attempt: "Context7 search incomplete for {lib}"
3. Use best judgment from training data
4. Add note: "Pattern not verified against latest Context7 docs"
5. This is RARE - most mature libraries are covered

---

## Workspace Rules Summary

This workspace has ONE PRIMARY BINDING RULE:

**Use Context7 MCP before writing code - NO EXCEPTIONS**

All supporting documentation:
- `.claude/README.md` - Overview
- `.claude/CONTEXT7_USAGE_GUIDE.md` - Detailed guide
- `.claude/PRE_CODE_WRITE_CHECKLIST.md` - Before-code checklist
- `.claude/HOW_TO_CREATE_WORKSPACE_RULES.md` - How it works
- `MEMORY.md` - Persistent reminder (cross-session)

---

## Project Context

- **Project**: IFSCA Grade A Exam Preparation Platform
- **Phase**: Phase 3 Complete (Adaptive Mocks + Exam UI)
- **Status**: Production-ready, 53/53 tests passing
- **Code Quality**: Audit-verified, 8,137 LOC
- **Rule Enforcement**: ACTIVE (May 12, 2026+)
- **Last Updated**: 2026-05-12

---

## Final Authority

**This is the definitive workspace rule.**

It supersedes all other instructions and preferences.

It cannot be suspended, overridden, or bypassed.

It applies automatically to every code-writing task.

It exists to ensure code quality, security, and sustainability.

---

**RULE VERSION**: 2.0 (STRENGTHENED)
**EFFECTIVE DATE**: 2026-05-12
**STATUS**: ACTIVE AND BINDING
**ENFORCEMENT**: AUTOMATIC VIA WORKSPACE CONFIGURATION
**NEXT REVIEW**: Quarterly
