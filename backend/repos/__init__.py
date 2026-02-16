"""
Repository layer for AIde.

All SQL lives here and ONLY here. No database access outside this module.
"""

from backend.repos.aide_repo import AideRepo
from backend.repos.conversation_repo import ConversationRepo
from backend.repos.magic_link_repo import MagicLinkRepo
from backend.repos.signal_mapping_repo import SignalMappingRepo
from backend.repos.user_repo import UserRepo

__all__ = [
    "UserRepo",
    "MagicLinkRepo",
    "AideRepo",
    "ConversationRepo",
    "SignalMappingRepo",
]
