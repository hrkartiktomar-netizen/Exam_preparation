# How to Create Workspace Rules in Claude Code

## Overview

Workspace rules (behavioral guidelines that Claude must follow) can be created using Claude's workspace configuration system. This document explains:

1. **What workspace rules are**
2. **How to create them**
3. **How Claude follows them**
4. **Real example: Context7 rule for IFSCA project**

---

## What Are Workspace Rules?

### Definition
Workspace rules are persistent instructions that:
- Apply to ALL conversations in a workspace
- Cannot be overridden by regular instructions
- Are loaded at the start of each conversation
- Take precedence over general guidelines

### Different from Regular Instructions
| Aspect | Regular Instruction | Workspace Rule |
|--------|-------------------|-----------------|
| Scope | Single conversation | All conversations |
| Persistence | Lost after conversation | Persists across sessions |
| Override ability | Can be contradicted | Cannot be overridden |
| Location | Message context | Workspace config files |
| Enforcement | Claude chooses to follow | Automatically enforced |

---

## Two Methods to Create Workspace Rules

### Method 1: CLAUDE.md File (RECOMMENDED)

**How it works:**
1. Create `.claude/CLAUDE.md` in workspace root
2. Claude automatically reads it at startup
3. Contents become binding instructions
4. Cannot be overridden by conversation prompts

**Status in Claude Code**: ✅ **FULLY SUPPORTED**

**Advantages**:
- Simple to create
- Human-readable format
- Easy to update
- Works immediately
- No configuration needed

**Example Structure**:
```
d:\Exam_preparation\
├── .claude/
│   ├── CLAUDE.md                    ← Main workspace rules
│   ├── CONTEXT7_USAGE_GUIDE.md      ← Supporting documentation
│   └── PRE_CODE_WRITE_CHECKLIST.md  ← Quick reference
├── backend/
├── frontend/
└── ... other project files
```

**How to Create**:
```bash
# Create directory
mkdir d:\Exam_preparation\.claude

# Create CLAUDE.md with workspace rules
# (Use any text editor or IDE)
# Make sure it contains:
# - Header: # Workspace Rules
# - Clear, explicit rules
# - Examples where applicable
# - How Claude should behave
```

**What Claude Does**:
- Reads `.claude/CLAUDE.md` automatically
- Treats it as binding workspace policy
- Applies rules to ALL code and decisions
- References it when making choices

### Method 2: settings.json Configuration (ADVANCED)

**How it works:**
1. Modify `.claude/settings.json` or `settings.local.json`
2. Add hooks or automation directives
3. Harness executes behaviors

**Status in Claude Code**: ⚠️ **LIMITED SUPPORT**

**Current Limitations**:
- Hooks execute at harness level (not Claude level)
- Cannot directly control Claude behavior
- Better for permissions/env vars than behavioral rules

**When to use**:
- Permissions: "allow npm install"
- Environment: "set DEBUG=true"
- Not for: "always use Context7" (use CLAUDE.md instead)

---

## Implementation: Creating the Context7 Rule

### Step 1: Create .claude Directory

```bash
mkdir d:\Exam_preparation\.claude
```

**What goes here:**
- Workspace configuration files
- Behavioral rules (CLAUDE.md)
- Supporting documentation
- NOT project code

### Step 2: Create CLAUDE.md

**Structure:**
```markdown
# [Project Name] - Workspace Rules

## Mandatory Rule: [Rule Name]

### The Rule
Clear, explicit statement of what Claude must do

### When to Apply
Specific contexts where this applies

### How to Apply
Step-by-step process

### Examples
Real examples from your project

### Enforcement
How the rule is enforced
```

**Key Elements:**
- ✅ Clear title
- ✅ Explicit language ("MUST", "ALWAYS", "NEVER")
- ✅ Specific conditions
- ✅ Examples from your project
- ✅ Checklist or verification method

### Step 3: Create Supporting Documentation

These help Claude apply the rule consistently:

**CONTEXT7_USAGE_GUIDE.md**:
- Explains the "why" behind the rule
- Provides detailed examples
- Shows integration with workflow

**PRE_CODE_WRITE_CHECKLIST.md**:
- Quick checklist to follow
- Checkboxes for verification
- Quick reference for contexts

### Step 4: Reference in Conversation

The rule is automatically applied, but you can remind Claude:

```
User: "Let's add error handling"
Claude automatically:
  1. Reads CLAUDE.md
  2. Sees Context7 rule
  3. Searches Context7 first
  4. Then writes code
```

---

## Real World Example: Context7 Rule

### The Rule We Created

**File**: `d:\Exam_preparation\.claude\CLAUDE.md`

**Core Rule**:
```
Whenever you are about to write code:
1. FIRST: Search Context7 MCP for the technology
2. THEN: Review documentation returned
3. FINALLY: Write code following verified patterns
```

### Why This Works

1. **Explicit**: Clear when rule applies
2. **Actionable**: Specific steps to follow
3. **Verified**: Tests ensure compliance
4. **Documented**: Supporting files explain reasoning

### How Claude Follows It

```
Conversation Turn:
  ↓
Claude loads CLAUDE.md
  ↓
Claude sees: "Before writing code, use Context7"
  ↓
User: "Add database function"
  ↓
Claude thinks: "This is code, so use Context7 first"
  ↓
Claude searches Context7
  ↓
Claude reviews results
  ↓
Claude writes code following best practices
```

---

## Best Practices for Workspace Rules

### DO:
- ✅ **BE EXPLICIT**: "Always" not "try to"
- ✅ **BE SPECIFIC**: "Use Context7 before all code" not "consider best practices"
- ✅ **PROVIDE EXAMPLES**: Show exactly what you mean
- ✅ **EXPLAIN WHY**: Help Claude understand importance
- ✅ **ADD CHECKLISTS**: Make compliance easy to verify

### DON'T:
- ❌ Be vague: "Follow best practices" is too broad
- ❌ Be aspirational: "Try to" suggests optional
- ❌ Assume understanding: Explain every detail
- ❌ Mix code and rules: Keep separate files
- ❌ Make rules contradictory: One consistent set

### Example: Good vs Bad Rule

**BAD**:
```
Try to follow best practices when coding.
Consider using established patterns.
Think about security implications.
```

**GOOD**:
```
MANDATORY RULE: Use Context7 Before Writing Code

Whenever you are about to write any code:
1. Identify the technology/library (e.g., "FastAPI")
2. Search Context7 MCP for that library
3. Review recommended patterns from documentation
4. Write code following verified patterns
5. Reference: "Per Context7 docs"

APPLIES TO: All code writing, no exceptions
ENFORCEMENT: Required by workspace policy
SUPPORTING DOCS: See CONTEXT7_USAGE_GUIDE.md
```

---

## File Structure Best Practice

```
d:\Exam_preparation\
├── .claude/                          ← Workspace config directory
│   ├── CLAUDE.md                     ← Primary rules file
│   ├── CONTEXT7_USAGE_GUIDE.md       ← Detailed guidance
│   ├── PRE_CODE_WRITE_CHECKLIST.md   ← Quick reference
│   ├── settings.json                 ← (Optional) advanced config
│   └── README.md                     ← Overview of rules
├── backend/
├── frontend/
├── memory/                           ← Auto-memory directory
│   └── MEMORY.md                     ← Session-persistent notes
├── CLAUDE.md                         ← (Alternative) project root
└── ... other project files
```

**Note**: `.claude/CLAUDE.md` takes precedence over root `CLAUDE.md`

---

## Verification: Is Your Rule Working?

### Test Method 1: Ask Claude to Explain

```
User: "What workspace rules apply to this project?"
Claude should reference CLAUDE.md and list all rules
```

### Test Method 2: Ask for Context7 Search

```
User: "I need a FastAPI endpoint"
Claude should search Context7 BEFORE writing code
```

### Test Method 3: Check References

```
User: "Add database function"
Claude should say: "Per Context7 docs for SQLite: ..."
```

### Test Method 4: Monitor Compliance

```
Over 10 code requests:
- 9/10 include Context7 search? → Working ✅
- 7/10 include Context7 search? → Partially working ⚠️
- 3/10 include Context7 search? → Not working ❌
```

---

## Troubleshooting

### Problem: Claude not following the rule

**Solution 1**: Make rule more explicit
- Change "try to" → "MUST"
- Add concrete examples
- Add enforcement statement

**Solution 2**: Add supporting documentation
- Create checklist file
- Create usage guide
- Make compliance easy

**Solution 3**: Verify file location
- Must be at `.claude/CLAUDE.md`
- Must be valid Markdown
- Must be readable by Claude

### Problem: Rule conflicts with user request

**Solution**: Workspace rules have highest priority
- User request "skip Context7" → Claude still searches
- Urgent task → Still follows rules
- Simple change → Still follows rules

**Why**: This is the point of workspace rules!

---

## Advanced: Multiple Rules

If you need multiple workspace rules:

**File Organization**:
```
.claude/
├── CLAUDE.md                    ← Main rules file
├── SECURITY_RULES.md            ← Security-specific rules
├── TESTING_STANDARDS.md         ← Testing requirements
├── PERFORMANCE_GUIDELINES.md    ← Performance standards
└── GUIDES/
    ├── CONTEXT7_USAGE.md
    ├── API_DESIGN.md
    └── DATABASE_PATTERNS.md
```

**CLAUDE.md references them all**:
```markdown
# Main Workspace Rules

## Rule 1: Use Context7 [details]
See: GUIDES/CONTEXT7_USAGE.md

## Rule 2: Security Requirements [details]
See: SECURITY_RULES.md

## Rule 3: Testing Standards [details]
See: TESTING_STANDARDS.md
```

---

## For This Project

### Files Created

1. **`.claude/CLAUDE.md`** - Main workspace rule
   - Mandatory Context7 usage
   - When to apply
   - Examples

2. **`.claude/CONTEXT7_USAGE_GUIDE.md`** - Detailed guide
   - Why use Context7
   - Step-by-step instructions
   - Real examples
   - Integration workflow

3. **`.claude/PRE_CODE_WRITE_CHECKLIST.md`** - Quick reference
   - Checklist format
   - Quick tech reference
   - Common mistakes
   - Success criteria

### How to Use

From now on, in this workspace:
1. Before writing ANY code
2. Claude will read CLAUDE.md
3. Claude will search Context7 first
4. Claude will follow verified patterns
5. Claude will reference Context7 docs

### Verification

Test in a conversation:
```
User: "I need to add database error handling"

Claude will:
- Read CLAUDE.md
- See Context7 rule
- Search: "SQLite error handling patterns"
- Review documentation
- Write code following best practices
- Reference: "Per Context7 SQLite docs..."
```

---

## Summary

**Workspace rules via CLAUDE.md:**
- ✅ Simple to create (just a Markdown file)
- ✅ Automatically enforced
- ✅ Cannot be overridden
- ✅ Persist across conversations
- ✅ Easy to update and maintain
- ✅ Works with all Claude Code features

**For this project:**
- ✅ Context7 rule implemented
- ✅ Supporting documentation created
- ✅ Checklist provided for compliance
- ✅ Ready for immediate use

---

**Document Version**: 1.0
**Created**: 2026-05-12
**Status**: Active
**Maintenance**: Update CLAUDE.md files as needed
