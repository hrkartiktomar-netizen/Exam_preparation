# Workspace Rules for IFSCA Exam Preparation Project

## Quick Summary

This directory contains workspace rules and guidelines for the IFSCA exam prep platform.

**Main Rule**: Always use Context7 MCP before writing any code.

---

## Files in This Directory

### 1. **CLAUDE.md** ⭐ PRIMARY
**Status**: MANDATORY WORKSPACE RULE

Contains the binding workspace rule that Claude MUST follow:
- Use Context7 MCP before writing code
- Exceptions and context-specific guidance
- How to follow the rule in practice

👉 **This is the master document** - Claude reads this automatically.

---

### 2. **CONTEXT7_USAGE_GUIDE.md** 📚 DETAILED GUIDE

Comprehensive guide on using Context7:
- What Context7 is and why it's useful
- Step-by-step usage instructions
- Real examples from IFSCA project
- Integration with workflow
- Tips, tricks, and best practices

👉 **Read this to understand the "why" and "how"**

---

### 3. **PRE_CODE_WRITE_CHECKLIST.md** ✅ QUICK REFERENCE

Before-writing checklist:
- 6-phase process
- Quick technology reference
- Common mistakes to avoid
- Success criteria

👉 **Use this before every code-writing task**

---

### 4. **HOW_TO_CREATE_WORKSPACE_RULES.md** 🔧 TECHNICAL GUIDE

How workspace rules work:
- What makes a rule "workspace-level"
- How to create them (CLAUDE.md method)
- Best practices
- Troubleshooting

👉 **Read if you want to create new rules or understand the mechanism**

---

## The Mandatory Rule (Summary)

**WHAT**: Before writing any code, search Context7 MCP

**WHY**: 
- Ensures code follows latest best practices
- Prevents security vulnerabilities
- Avoids deprecated patterns
- Catches breaking changes
- Improves code quality

**HOW**:
1. Identify the technology (e.g., "FastAPI")
2. Search Context7 for library documentation
3. Review recommended patterns
4. Write code following verified patterns

**WHEN**: Every code-writing task (no exceptions)

---

## Workflow Example

Here's how a code request flows through this workspace:

```
User Request: "Add error handling to exam submission"
    ↓
Claude reads CLAUDE.md (automatic)
    ↓
Claude sees rule: "Before writing code, use Context7"
    ↓
Claude identifies: "This is FastAPI + SQLite code"
    ↓
Claude searches Context7:
  - libraryName: "FastAPI"
  - query: "error handling in async endpoints"
    ↓
Claude gets Context7 documentation
    ↓
Claude reviews recommended patterns
    ↓
Claude writes code following best practices
    ↓
Claude references: "Per Context7 docs for FastAPI: ..."
```

---

## How Claude Uses This Workspace Config

### Automatic Behavior

At the start of every conversation in this workspace, Claude:
1. Checks for `.claude/` directory
2. Finds and reads `CLAUDE.md`
3. Loads all rules into context
4. Applies rules to all decisions and code

### Why This Works

- Rules are in `.claude/CLAUDE.md` → Claude automatically loads them
- Content is explicit and clear → Claude understands priority
- Cannot be overridden → Ensures consistency
- Persists across sessions → Always applied

---

## Testing the Rule

Want to verify the rule is working?

### Test 1: Check Rule Recognition
```
Ask: "What workspace rules apply to this project?"
Claude should list the Context7 rule from CLAUDE.md
```

### Test 2: Check Context7 Application
```
Ask: "I need to add a database function"
Claude should search Context7 before writing code
```

### Test 3: Check Reference Citations
```
Ask: "Fix the async exception handling"
Claude should cite: "Per Context7 docs for Python asyncio: ..."
```

---

## Technologies Covered by This Rule

All code related to these technologies must follow Context7:

| Technology | Use in Project | Context7 Subject |
|-----------|-----------------|------------------|
| **FastAPI** | Web API framework | Async endpoints, error handling, dependency injection |
| **SQLite** | Database | Connections, queries, transactions |
| **Python asyncio** | Async operations | Context managers, exceptions, cleanup |
| **Pydantic** | Data validation | Models, validators, serialization |
| **pytest** | Testing | Fixtures, async tests, mocking |
| **Claude API** | AI integration | Streaming, errors, token usage |

---

## Document Quick Reference

| Need | File | Time |
|------|------|------|
| Confirm rules exist | CLAUDE.md | 2 min |
| Learn deep details | CONTEXT7_USAGE_GUIDE.md | 10 min |
| Quick checklist | PRE_CODE_WRITE_CHECKLIST.md | 2 min |
| Understand mechanism | HOW_TO_CREATE_WORKSPACE_RULES.md | 5 min |

---

## FAQ

### Q: What if I'm in a hurry?
**A**: The rule still applies. Context7 search takes ~30 seconds and prevents hours of debugging. Worth it.

### Q: Can I skip this rule?
**A**: No. It's a workspace-level rule, which means it cannot be overridden by urgency or user requests.

### Q: What if Context7 doesn't have info?
**A**: Most mature libraries are covered. If truly unavailable, document the search attempt and proceed. Still better than skipping.

### Q: Does this apply to all code?
**A**: Primarily for: business logic, API endpoints, database code, testing. Less critical for: comments, documentation, configuration files.

### Q: How do I report issues with this rule?
**A**: Update CLAUDE.md with clarifications or new guidance. Keep all files in sync.

---

## Maintenance

### When to Update Files

- **New technologies added to project?** → Add to CLAUDE.md
- **Find a Context7 gap?** → Document in CONTEXT7_USAGE_GUIDE.md
- **New common mistake?** → Add to PRE_CODE_WRITE_CHECKLIST.md
- **Process changes?** → Update HOW_TO_CREATE_WORKSPACE_RULES.md

### Review Schedule

- Quarterly: Review CLAUDE.md for new patterns
- Annually: Full review of all workspace rules
- As-needed: Update when issues arise

---

## Project Status

- **Project**: IFSCA Grade A Exam Preparation Platform
- **Phase**: Phase 3 Complete (Adaptive Mock Generation + Exam UI)
- **Code Quality**: Production-ready (53/53 tests passing)
- **Audit Status**: Comprehensive audit complete (May 12, 2026)
- **Rules Enforcement**: Context7 rule activated (May 12, 2026)

---

## Summary

✅ **Workspace rules are installed and active**

This directory contains binding rules that Claude follows automatically:
- Primary rule: Use Context7 MCP before writing code
- Supported by 3 detailed guides
- Cannot be overridden or suspended
- Applies to all conversations in this workspace
- Improves code quality and security

**Start using it**: Just request code changes normally. Claude will follow the rule automatically.

---

**Version**: 1.0  
**Effective Date**: 2026-05-12  
**Status**: ACTIVE  
**Last Updated**: 2026-05-12
