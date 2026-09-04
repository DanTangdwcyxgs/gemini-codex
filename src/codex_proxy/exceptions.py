"""Custom exception hierarchy for gemini-codex."""


class ProxyError(Exception):
    pass


class ProviderError(ProxyError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConfigurationError(ProxyError):
    pass


class AuthenticationError(ProxyError):
    pass


class ValidationError(ProxyError):
    pass
