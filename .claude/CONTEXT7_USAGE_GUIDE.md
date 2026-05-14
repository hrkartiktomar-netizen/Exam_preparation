# Context7 MCP Usage Guide - IFSCA Project

## What is Context7 MCP?

Context7 is a Model Context Protocol (MCP) server that provides:
- **Latest documentation** for software libraries and frameworks
- **Code examples** for common patterns
- **Best practices** from official sources
- **Version-specific guidance** for different library versions

## Why Use Context7 Before Writing Code?

### Problems It Solves

1. **Outdated memory** - Your training data may be from 2024, but library best practices have evolved in 2025-2026
2. **Security vulnerabilities** - Old patterns may have security flaws discovered after training
3. **Deprecation** - APIs change, functions get deprecated, alternatives emerge
4. **Performance** - New optimization techniques may be available
5. **Breaking changes** - Code that worked in v1.0 breaks in v2.0

### Real Example from This Project

**Scenario**: Need to add database connection pooling to FastAPI

**Without Context7 (RISKY)**:
- Write code from memory
- May use patterns that are now discouraged
- May miss FastAPI 0.100+ async/await patterns
- May not include latest security recommendations

**With Context7 (SAFE)**:
- Search: "FastAPI database connection pooling 2026"
- Get: Latest FastAPI patterns, async context managers, SQLAlchemy integration
- Write: Code that follows current best practices
- Reference: Official documentation from Context7

## How to Use Context7: Step-by-Step

### Step 1: Identify the Technology

Before writing code, ask yourself: "What library/framework am I using?"

Examples:
- "I'm writing a FastAPI endpoint" → Library: FastAPI
- "I'm querying SQLite" → Library: SQLite
- "I'm using Claude API" → Library: Claude API / Anthropic SDK
- "I'm writing async code" → Library: Python asyncio

### Step 2: Search for Library ID

Use the resolve-library-id tool:

```
mcp__context7__resolve-library-id(
  libraryName="FastAPI",
  query="async database connections and resource cleanup"
)
```

Response example:
```
{
  "libraryId": "/tiangolo/fastapi",
  "versions": ["0.100.0", "0.109.0", "0.115.0"],
  "description": "Modern async web framework for Python",
  "benchmarkScore": 95
}
```

### Step 3: Query Documentation

Use the query-docs tool with the libraryId:

```
mcp__context7__query-docs(
  libraryId="/tiangolo/fastapi",
  query="async database connection lifecycle and error handling"
)
```

Response contains:
- Code examples
- Best practices
- Security considerations
- Performance tips
- Version compatibility

### Step 4: Review Results

Before writing code, review:
- Latest recommended pattern
- Code examples that match your use case
- Any warnings or deprecations
- Version compatibility notes

### Step 5: Write Code Following Context7 Verified Patterns

Now write code that aligns with what Context7 documented.

## Real Examples from IFSCA Project

### Example 1: FastAPI Endpoint Error Handling

**Task**: Add error handling to exam submission endpoint

**Context7 Search**:
```python
# Step 1: Identify library = FastAPI
# Step 2: Get libraryId
libraryId = "/tiangolo/fastapi"

# Step 3: Query for pattern
query = "error handling in async endpoints, HTTPException proper usage"

# Step 4: Get documentation + examples
# Context7 returns: FastAPI's HTTPException patterns, status codes, error responses
```

**Result**: Write endpoint using latest FastAPI error patterns

```python
@app.post("/api/exams/submit")
async def submit_exam(exam_id: str, request: SubmitRequest):
    try:
        # Verify exam exists
        if not exam_exists(exam_id):
            raise HTTPException(status_code=404, detail="Exam not found")
        
        # Validate request
        if not request.answers:
            raise HTTPException(status_code=400, detail="No answers provided")
            
        # Process
        result = process_submission(exam_id, request.answers)
        return result
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

### Example 2: SQLite Connection Management

**Task**: Add database function with proper connection cleanup

**Context7 Search**:
```python
# Step 1: Identify library = SQLite
# Step 2: Get libraryId
libraryId = "/sqlite/sqlite"  # or directly query for SQLite

# Step 3: Query for pattern
query = "connection lifecycle management, proper cleanup, context managers"

# Step 4: Get documentation
# Context7 returns: Connection management best practices, try/finally patterns
```

**Result**: Write function with verified cleanup pattern

```python
def get_weak_topics(threshold: float = 60.0) -> list[dict]:
    conn = get_connection()
    try:
        results = conn.execute(
            "SELECT * FROM topics WHERE accuracy < ?",
            (threshold,)
        ).fetchall()
        return [dict(row) for row in results]
    finally:
        conn.close()  # ALWAYS close, even on error
```

### Example 3: Python asyncio Context Manager

**Task**: Implement proper async resource management

**Context7 Search**:
```python
# Step 1: Identify library = Python asyncio
# Step 2: Query for pattern
query = "async context managers, resource cleanup, exception handling"

# Step 3: Get documentation
# Context7 returns: asynccontextmanager pattern, best practices
```

**Result**: Write using verified async context manager

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_session():
    session = create_session()
    try:
        yield session
    finally:
        await session.close()

# Usage
async def process_request():
    async with get_db_session() as session:
        # session is available here
        result = await session.query(Question).all()
    # session automatically closed here
```

## Context7 Workflow Integration

### Before Every Code Change

```
CODE REQUEST
    ↓
IDENTIFY TECHNOLOGY
    ↓
SEARCH CONTEXT7 (resolve-library-id)
    ↓
QUERY CONTEXT7 (query-docs)
    ↓
REVIEW DOCUMENTATION
    ↓
WRITE CODE following Context7 patterns
    ↓
REFERENCE: "Per Context7 docs for {library}"
```

### What Categories of Code Need Context7?

**ALWAYS use Context7** for:
- ✅ Backend framework code (FastAPI, Django, etc.)
- ✅ Database operations (SQLite, PostgreSQL, etc.)
- ✅ Async/concurrent code (asyncio, threading, etc.)
- ✅ API integration (Claude API, external services)
- ✅ Testing frameworks (pytest, unittest, etc.)
- ✅ Authentication/security code (passwords, tokens, etc.)
- ✅ Configuration/deployment code

**LIKELY use Context7** for:
- ✅ Algorithm implementation
- ✅ Data structure choices
- ✅ Performance optimization
- ✅ Error handling patterns

**MAYBE skip Context7** for:
- ❓ Simple business logic
- ❓ Project-specific utilities
- ❓ Non-technical documentation

**When in doubt**: Use Context7. 30 seconds of research saves hours of debugging.

## Context7 Tips & Tricks

### Tip 1: Be Specific with Queries

**Bad query**: "FastAPI error handling"
- Too broad, returns generic information

**Good query**: "FastAPI async database connection with error handling and transaction rollback"
- Specific to your use case
- Gets targeted documentation

### Tip 2: Check Version Compatibility

Context7 returns version-specific information. Always verify:
- "Does this apply to the version I'm using?"
- "Are there breaking changes between versions?"

### Tip 3: Review Code Examples First

When Context7 returns documentation:
1. Look for code examples first
2. Understand the pattern
3. Then read explanatory text
4. Verify against your use case

### Tip 4: Check for Security/Performance Notes

Context7 output often includes:
- ⚠️ Security warnings ("Don't do X because...")
- 📊 Performance notes ("Use Y for better throughput")
- 🔄 Deprecation warnings ("Z is deprecated, use W instead")

Always read these carefully.

### Tip 5: Search Multiple Related Libraries

Sometimes you need multiple libraries:
- FastAPI (web framework) + SQLAlchemy (ORM) + Pydantic (validation)
- Search each one for how they integrate

Example query: "FastAPI and SQLAlchemy integration patterns"

## Integration with IFSCA Project

### Technologies in This Project Requiring Context7

| Technology | Use | Context7 Query Examples |
|-----------|-----|------------------------|
| **FastAPI** | Web framework | "async endpoint patterns", "dependency injection", "error handling" |
| **SQLite** | Database | "connection lifecycle", "query optimization", "transaction management" |
| **Python asyncio** | Async code | "async context managers", "exception handling in async" |
| **Pydantic** | Validation | "model validation best practices", "custom validators" |
| **pytest** | Testing | "async test patterns", "fixtures", "mocking" |
| **Claude API** | AI integration | "streaming responses", "error handling", "token usage" |

## Enforcement in This Workspace

**How**: CLAUDE.md rule at `.claude/CLAUDE.md` contains this as mandatory workspace rule

**When**: Every code-writing task triggers Context7 search first

**Why**: Ensures all code follows current best practices and latest security standards

**Override**: Cannot be overridden; workspace rules are binding

## Quick Reference Commands

### Resolve Library ID
```python
mcp__context7__resolve-library-id(
  libraryName="<LibraryName>",
  query="<specific use case>"
)
```

### Query Documentation
```python
mcp__context7__query-docs(
  libraryId="/org/project",
  query="<specific pattern or problem>"
)
```

### Example: FastAPI + Database

```python
# 1. Resolve FastAPI
id1 = resolve_library_id("FastAPI", "async database connections")

# 2. Resolve SQLite
id2 = resolve_library_id("SQLite", "connection pooling and cleanup")

# 3. Query FastAPI patterns
fastapi_docs = query_docs(id1, "async dependency injection for database")

# 4. Query SQLite patterns
sqlite_docs = query_docs(id2, "connection lifecycle in concurrent applications")

# 5. Combine and write code
```

---

**Document Version**: 1.0
**Last Updated**: 2026-05-12
**Status**: Active
**Audience**: Claude (this workspace)
