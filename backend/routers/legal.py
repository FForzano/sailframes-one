"""Public legal-document metadata (``/api/legal``).

Serves only the current version + effective date of the Terms of Service and
Privacy Policy — the document text itself is rendered by the frontend
(``frontend/src/content/legal/*``). Public and unauthenticated so the
registration and standalone /terms, /privacy pages can label which version a
visitor is about to accept before they have an account. Versions are the
single source of truth in ``backend/legal.py``.
"""

from fastapi import APIRouter

from ..legal import legal_metadata

router = APIRouter(prefix="/api/legal", tags=["legal"])


@router.get("")
def get_legal_metadata():
    return legal_metadata()
