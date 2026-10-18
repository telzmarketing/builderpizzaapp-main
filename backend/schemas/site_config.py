from typing import Any
from pydantic import RootModel


class SiteConfigIn(RootModel[dict[str, Any]]):
    """Published free-form site-content object contract."""
