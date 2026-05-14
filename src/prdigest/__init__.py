"""prdigest — render a GitHub pull request as one LLM-ready markdown document."""

from prdigest.core import build_digest
from prdigest.models import PRRef

__all__ = ["build_digest", "PRRef"]
__version__ = "0.1.0"
