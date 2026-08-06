"""Execution boundary for preserved legacy Streamlit source.

Legacy files and databases remain on disk for audited, offline recovery. They
are not an authentication or persistence surface of the production platform.
"""

ARCHIVE_MESSAGE = (
    "This legacy Streamlit interface is archived and read-only. Use the "
    "canonical FastAPI/React platform. No legacy authentication or database "
    "operation was executed."
)
