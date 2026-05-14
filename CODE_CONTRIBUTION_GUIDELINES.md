# CODE CONTRIBUTION GUIDELINES - IFSCA Exam Prep

## ⚠️ CRITICAL: CONTEXT7 MCP REQUIREMENT

**Every piece of code in this project must be written using Context7 MCP documentation first.**

This is not optional. This is not a "nice to have." This is MANDATORY.

---

## Before Writing ANY Code

### The Process (Takes ~30 seconds)

1. **Identify** the technology you're using
   - Example: "I'm writing a FastAPI endpoint"
   - Example: "I'm querying SQLite"
   - Example: "I'm writing async cleanup code"

2. **Search Context7** using resolve-library-id
   ```python
   context7_id = search_library("FastAPI", "your specific use case")
   ```

3. **Query Context7** using query-docs
   ```python
   docs = query_docs(context7_id, "error handling in async endpoints")
   ```

4. **Review** the documentation returned
   - Check for latest patterns
   - Review security notes
   - Look for code examples
   - Understand best practices

5. **Write** code following Context7 patterns
   - Match the recommended approach
   - Include proper error handling
   - Add resource cleanup
   - Follow naming conventions

6. **Reference** the source
   - Add comment: "Per Context7 docs for FastAPI: [pattern]"
   - Include link if available
   - Cite the specific recommendation

---

## Why This is Mandatory

### Real Problems This Solves

| Problem | Without Context7 | With Context7 |
|---------|------------------|---------------|
| Using outdated patterns | Code uses 2024 approaches | Uses latest 2026 patterns |
| Security vulnerabilities | Misses new vulnerabilities | Built-in security |
| Performance issues | Optimizations unknown | Performance-tuned |
| Breaking changes | Incompatible APIs | Version-verified |
| Resource leaks | Connections left open | Proper cleanup |
| Exception handling | Incomplete error handling | Robust error handling |

### This Project: Real Example

**Phase 2 Audit Found**: Duplicate `_run_migration_002()` function
- One version: **Had finally block** (proper cleanup)
- One version: **Missing finally block** (CONNECTION LEAK)
- Python used the broken version (last definition wins)

**With Context7 in place**: This error would never happen
- Context7 docs would show: "Always use try/finally for resource cleanup"
- Developer would know which pattern is correct
- Code review would catch deviations

---

## Technologies Covered

### Backend (ALWAYS use Context7)
- **FastAPI** - API endpoints, middleware, dependency injection
- **SQLite** - Connection management, queries, transactions
- **Python asyncio** - Async code, context managers, cleanup

### Frontend (ALWAYS use Context7)
- **HTML/JavaScript** - DOM manipulation, event handling, async fetch
- **CSS** - Layout, styling, responsive design

### Testing (ALWAYS use Context7)
- **pytest** - Fixtures, async tests, mocking

### AI Integration (ALWAYS use Context7)
- **Claude API** - Streaming, error handling, tokens
- **Anthropic SDK** - Latest patterns

---

## Verification Checklist

Before submitting code, ask yourself:

- [ ] Did I search Context7 for this technology?
- [ ] Did I review the documentation returned?
- [ ] Does my code match the recommended pattern?
- [ ] Did I include proper error handling (per Context7)?
- [ ] Did I include proper resource cleanup (per Context7)?
- [ ] Is security considered (per Context7)?
- [ ] Did I reference the source ("Per Context7 docs...")?
- [ ] Would a code reviewer see the Context7 citation?

**If you answered NO to any question**: Go back and follow Context7.

---

## Code Review Guidelines

### Reviewers: Check for Context7 Compliance

Every piece of code should have:

1. ✅ **Citation visible**: "Per Context7 docs for {library}: {pattern}"
2. ✅ **Pattern match**: Code follows recommended practice
3. ✅ **Best practices**: Security/performance considerations included
4. ✅ **Completeness**: Error handling and cleanup included
5. ✅ **Version compatibility**: Code works for stated version+

### Reviewers: Red Flags

- ❌ No Context7 citation visible
- ❌ Code doesn't match documented patterns
- ❌ Missing error handling
- ❌ Missing resource cleanup
- ❌ Security considerations overlooked
- ❌ Commit message doesn't mention verification

**Action**: Request revision with Context7 verification.

---

## Common Scenarios

### Scenario 1: "Quick Bug Fix"

**Your thought**: "This is a 2-line fix, I don't need Context7"

**Reality**: Those 2 lines might be in error handling, resource cleanup, or security code

**What to do**:
1. Search Context7 for the affected technology
2. Verify your 2-line fix matches recommended pattern
3. Include citation in commit message

**Time cost**: 30 seconds

---

### Scenario 2: "I Know This Technology"

**Your thought**: "I've used FastAPI for years, I don't need Context7"

**Reality**: FastAPI has evolved. Patterns from 2024 might be deprecated in 2026.

**What to do**:
1. Search Context7 to verify current best practice
2. You'll likely learn something new
3. You'll be using verified latest patterns

**Benefit**: Current knowledge + verification = better code

---

### Scenario 3: Emergency/Urgent Task

**Your thought**: "This is urgent, I'll skip Context7 and fix later"

**Reality**: Context7 search takes 30 seconds. "Fix later" never happens. Technical debt accumulates.

**What to do**:
1. Use Context7 first (30 seconds)
2. Write correct code immediately
3. No post-processing needed

**Net time**: Same or faster

---

## Project Technologies (Reference)

These ALWAYS require Context7:

**Backend**:
- FastAPI (web framework)
- SQLite (database)
- Python asyncio (async runtime)
- Pydantic (validation)

**Frontend**:
- Vanilla JavaScript (no framework)
- HTML5
- CSS3

**Testing**:
- pytest (testing framework)

**AI**:
- Claude/Anthropic SDK (AI integration)

**Infrastructure**:
- Git (version control)
- Python (runtime)

---

## How to Get Context7 Docs

### In-Conversation

**Using Context7 MCP tools** (Claude does this automatically):

```python
# Step 1: Resolve library
libraryId = mcp__context7__resolve-library-id(
    libraryName="FastAPI",
    query="async database connection with error handling"
)

# Step 2: Query docs
docs = mcp__context7__query-docs(
    libraryId=libraryId,
    query="best practices for connection lifecycle"
)

# Now you have latest patterns, examples, and best practices
```

### Referenced in Code

```python
# Example citation in code
def get_connection():
    """
    Get database connection with proper lifecycle management.

    Per Context7 docs for SQLite: use try/finally for guaranteed cleanup
    on both success and error paths.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()  # Always closes
```

---

## Project Status

- **Phase**: 3 (Complete)
- **Tests**: 53/53 passing
- **Audit**: Comprehensive end-to-end (May 12, 2026)
- **Code Quality**: Production-ready
- **Context7 Enforcement**: ACTIVE

---

## Questions?

Reference these files:
- `.claude/CLAUDE.md` - Main enforcement rule
- `.claude/CONTEXT7_USAGE_GUIDE.md` - Detailed guide
- `.claude/PRE_CODE_WRITE_CHECKLIST.md` - Quick checklist
- `.claude/HOW_TO_CREATE_WORKSPACE_RULES.md` - How it works

---

**Version**: 1.0
**Effective**: 2026-05-12
**Status**: MANDATORY
**Questions**: Refer to .claude/ documentation
