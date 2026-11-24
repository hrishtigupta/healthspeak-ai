"""Local AI pipeline: speech recognition and translation.

Everything runs on this machine. No patient audio or text is sent to an outside
AI provider. Models load lazily on first use; if a model or its Python packages
are missing, the rest of the application keeps working and the AI feature
reports itself as unavailable.
"""
