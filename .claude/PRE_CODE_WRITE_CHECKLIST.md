# PRE-CODE-WRITE CHECKLIST

**USE THIS CHECKLIST BEFORE WRITING ANY CODE IN THIS WORKSPACE**

## When to Use This Checklist

✅ Whenever you are about to:
- Write a new function
- Add/modify an API endpoint
- Change database code
- Implement async/await logic
- Add error handling
- Optimize performance
- Test new functionality

## The Checklist

### Phase 1: Identify Technology
- [ ] What library/framework will I use?
  - Example: "FastAPI for this endpoint"
  - Example: "SQLite for this query"
  - Example: "Python asyncio for this async operation"

### Phase 2: Search Context7 (MANDATORY)
- [ ] Used mcp__context7__resolve-library-id?
  - Input: Library name + specific use case query
  - Output: Library ID (e.g., "/tiangolo/fastapi")
  
- [ ] Used mcp__context7__query-docs?
  - Input: Library ID + detailed query about your pattern
  - Output: Latest documentation + code examples

### Phase 3: Review Documentation
- [ ] Read Context7 documentation returned?
- [ ] Identified the recommended pattern?
- [ ] Checked for security warnings? ⚠️
- [ ] Checked for performance notes? 📊
- [ ] Verified version compatibility?
- [ ] Noted any deprecations or breaking changes?

### Phase 4: Plan Your Code
- [ ] Based on Context7 docs, what pattern should I use?
- [ ] Do I understand the recommended approach?
- [ ] Are there code examples I can follow?
- [ ] Have I noted the best practices?

### Phase 5: Write Code
- [ ] Write code following Context7 verified patterns
- [ ] Reference the source: "Per Context7 docs for {library}"

### Phase 6: Verify
- [ ] Does my code match the Context7 recommended pattern?
- [ ] Have I included proper error handling?
- [ ] Have I included proper resource cleanup?
- [ ] Is security considered?
- [ ] Is performance considered?

---

## Quick Reference: Technology → Query Examples

### FastAPI Code
```
Resolve:  libraryName="FastAPI"
Query:    "error handling in async endpoints" OR
          "HTTP exception patterns" OR
          "dependency injection for async functions"
```

### SQLite Code
```
Resolve:  libraryName="SQLite"
Query:    "connection lifecycle and cleanup" OR
          "parameterized queries and SQL injection prevention" OR
          "transaction management and rollback"
```

### Python Async Code
```
Resolve:  libraryName="Python asyncio"
Query:    "async context managers" OR
          "exception handling in async code" OR
          "proper resource cleanup with async"
```

### API Integration (Claude)
```
Resolve:  libraryName="Anthropic SDK" OR "Claude API"
Query:    "streaming responses" OR
          "error handling and retries" OR
          "token usage and cost optimization"
```

### Testing Code
```
Resolve:  libraryName="pytest"
Query:    "mocking and fixtures" OR
          "async test patterns" OR
          "test organization and structure"
```

---

## Common Mistakes to Avoid

❌ **DON'T**: Write code without searching Context7
- Just because you "know" a library

❌ **DON'T**: Skip Context7 for "quick" changes
- Small code can have big security/performance issues

❌ **DON'T**: Use patterns from memory
- Your training data is outdated compared to 2026 libraries

❌ **DON'T**: Ignore Context7 warnings
- They're there for a reason

❌ **DON'T**: Assume version compatibility
- Always verify

---

## Success Criteria

After using this checklist, you should:
1. ✅ Have Context7 documentation for your technology
2. ✅ Understand the recommended pattern
3. ✅ Know what security/performance considerations apply
4. ✅ Be able to write code with confidence
5. ✅ Have a reference to cite ("Per Context7 docs")

---

## How to Use This Checklist

### Option A: Quick Review (2 minutes)
1. Go through all checkbox items
2. If you can't check 3+ items, stop and search Context7
3. Then proceed with code writing

### Option B: Detailed Review (5 minutes)
For complex code changes:
1. Use this entire checklist
2. Document your answers
3. Then write code with full Context7 understanding

### Option C: Emergency Skip?
If somehow you MUST skip Context7 (truly emergency):
1. Write a TODO comment in code: `# TODO: Review per Context7 for {library}`
2. Still search Context7 later
3. Update code with correct pattern

**BUT**: Emergency skips = technical debt. Fix promptly.

---

## Workspace Enforcement

**This checklist is binding in this workspace**
- It's connected to the CLAUDE.md mandatory rule
- Applies to ALL code writing tasks
- Cannot be overridden by urgency/time pressure
- Violations get caught during code review

---

## Questions?

Refer to:
- `.claude/CLAUDE.md` - Workspace rule enforcement
- `.claude/CONTEXT7_USAGE_GUIDE.md` - Detailed usage guide
- Context7 MCP documentation - Direct from library maintainers

---

**Checklist Version**: 1.0
**Last Updated**: 2026-05-12
**Print this**: You can print this and keep it nearby!
