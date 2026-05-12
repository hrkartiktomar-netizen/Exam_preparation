# AI Behavior Rules

## Context7 Integration Protocol
You are required to use the **Context7 MCP** to fetch up-to-date documentation before generating any code for external libraries or frameworks.

### Mandatory Workflow:
1. **Identify Libraries**: Detect all third-party libraries required for the user's task.
2. **Resolve IDs**: For each library, use the `context7.resolve-library-id` tool to find the exact library ID (e.g., `/supabase/supabase` or `/vercel/next.js`).
3. **Fetch Documentation**: Use `context7.query-docs` with the resolved ID and the user's specific coding goal (e.g., "authentication", "middleware") to retrieve current code examples and API references.
4. **Implementation**: Only after retrieving this context should you write the requested lines of code.

### Guidelines:
- **Cite Sources**: Always specify which version of the documentation you are using.
- **Accuracy over Speed**: Do not rely on internal training data for library-specific syntax if Context7 is available.
- **No Hallucinations**: If the library cannot be resolved, ask the user for the specific version or documentation link before proceeding.
