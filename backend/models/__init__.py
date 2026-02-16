"""
Pydantic models for AIde.

All data shapes defined here. No imports from db, repos, or routes.
"""

from backend.models.aide import (
    Aide,
    AideResponse,
    CreateAideRequest,
    UpdateAideRequest,
)
from backend.models.auth import (
    LogoutResponse,
    MagicLink,
    SendMagicLinkRequest,
    SendMagicLinkResponse,
    VerifyMagicLinkRequest,
)
from backend.models.conversation import Conversation, ConversationResponse, Message
from backend.models.signal_mapping import (
    CreateSignalMappingRequest,
    SignalMapping,
    SignalMappingResponse,
)
from backend.models.user import User, UserPublic

__all__ = [
    # User models
    "User",
    "UserPublic",
    # Auth models
    "MagicLink",
    "SendMagicLinkRequest",
    "SendMagicLinkResponse",
    "VerifyMagicLinkRequest",
    "LogoutResponse",
    # Aide models
    "Aide",
    "CreateAideRequest",
    "UpdateAideRequest",
    "AideResponse",
    # Conversation models
    "Conversation",
    "Message",
    "ConversationResponse",
    # Signal mapping models
    "SignalMapping",
    "CreateSignalMappingRequest",
    "SignalMappingResponse",
]
