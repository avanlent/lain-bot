from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Any

from ..models.profile import Profile


class VndbProfile(Profile):
    __slots__ = ['name', 'avatar']
    DEFAULT_AVATAR = 'https://files.catbox.moe/suqy48.png'

    def __init__(
        self,
        name: str = '',
        avatar: str = '',
        **kwargs,
    ) -> None:
        self.name = name
        self.avatar = avatar or self.DEFAULT_AVATAR

    @property
    def dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'avatar': self.avatar,
        }

    def __repr__(self) -> str:
        return f"<{str(self)}>"

    def __str__(self) -> str:
        return f"name={self.name}, avatar={self.avatar}"

