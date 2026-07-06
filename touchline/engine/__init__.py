"""Pure game engine: domain model and simulation logic.

Nothing in this package may import Flask, SQLAlchemy, or pywebview. All
randomness flows through an injected ``random.Random`` instance so behaviour is
deterministic under test.
"""
