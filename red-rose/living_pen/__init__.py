"""Living Pen Stage 1; CLI registration is dependency-lazy."""
def register(sub):
    from .cli import register as add
    add(sub)
