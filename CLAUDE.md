# Claude Context & Guidelines

## Developer

**Name:** Stiven  
**Tech Stack:** Rust, Python, TypeScript, Go, React, React Native  
**Platforms:** macOS (M5), Linux, Windows  

---

## Communication Style

- Concise & token-optimized
- Present solutions, not lengthy explanations
- Use bullet points for clarity; prose only when necessary
- After commits: full changelog in chat (no PRs unless asked)
- No session/project links in output

---

## Code Standards

### General Conventions

- **Code Quality:** Readable & modular (exceptions documented when necessary)
- **Comments:** Only where code doesn't self-explain
- **Naming:** Meaningful for variables, functions, and files
- **Error Handling:** Explicit, context-aware

### Git Workflow

- Commit under original author
- **Branch Naming:** `alpha`, `beta`, `release/<version>` (e.g., `release/v1.0.0`)
- No auto-PRs; await explicit request
- After commit: post full changelog in chat

### Language-Specific Standards

#### Rust

- Use `petgraph` for graph operations (Verdikt)
- Error handling: `Result<T, E>` with meaningful error types
- Module structure: flat or hierarchical based on crate complexity
- Tests: inline `#[cfg(test)]` modules

#### TypeScript / React

- Functional components with hooks
- Type safety: avoid `any`, use discriminated unions
- Component structure: one per file (unless tightly coupled)
- State: React Context or local `useState` (avoid prop drilling)

#### Python

- Type hints preferred (PEP 484)
- Docstrings for public functions/classes
- Scripts: argparse for CLI, logging for debug output
- Testing: pytest with descriptive names

---

## Problem-Solving Methodology

**Workflow:** Design → Plan → Execute → Test → Ship

- **Design:** Sketch architecture, data structures, API surface
- **Plan:** Break into milestones, identify dependencies
- **Execute:** Write code incrementally, test as you go
- **Test:** Verify correctness, edge cases, performance
- **Ship:** Commit, document, communicate changes


