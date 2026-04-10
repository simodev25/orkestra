"""Custom exception hierarchy for Orkestra."""


class OrkestraError(Exception):
    """Base exception."""
    pass


class NotFoundError(OrkestraError):
    """Resource not found."""
    pass


class ValidationError(OrkestraError):
    """Input validation failed."""
    pass


class StateViolationError(OrkestraError):
    """Invalid state transition."""
    pass


class AuthorizationError(OrkestraError):
    """Insufficient permissions."""
    pass
