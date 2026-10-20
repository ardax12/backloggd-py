"""Custom exceptions for the backloggd library."""


class BackloggdError(Exception):
    """Base exception for all Backloggd errors."""


class ChallengeResponseError(BackloggdError):
    """Raised when Backloggd returns an anti-bot challenge (Anubis / Cloudflare / Proof of work)."""


class RateLimitError(BackloggdError):
    """Raised when Backloggd rate limits requests (HTTP 429)."""


class ResourceNotFoundError(BackloggdError):
    """Base exception for 404 Not Found errors on Backloggd."""


class UserNotFoundError(ResourceNotFoundError):
    """Raised when a user profile or library does not exist (HTTP 404)."""



class GameNotFoundError(ResourceNotFoundError):
    """Raised when a game page does not exist (HTTP 404)."""


class ListNotFoundError(ResourceNotFoundError):
    """Raised when a custom list page does not exist (HTTP 404)."""


class ReviewNotFoundError(ResourceNotFoundError):
    """Raised when a review does not exist (HTTP 404)."""
