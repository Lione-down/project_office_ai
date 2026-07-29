from app.services.decks.contracts import (
    DeckConfirmCommand,
    DeckCreateCommand,
    DeckDraftSnapshot,
    DeckGenerationCommand,
    DeckUpdateCommand,
)


DeckCreateRequest = DeckCreateCommand
DeckUpdateRequest = DeckUpdateCommand
DeckConfirmRequest = DeckConfirmCommand
DeckGenerationRequest = DeckGenerationCommand
DeckDraftResponse = DeckDraftSnapshot
