"""Custom exception hierarchy for gemini-codex."""


class ProxyError(Exception):
    pass


class ProviderError(ProxyError):
    pass


class ConfigurationError(ProxyError):
    pass


class AuthenticationError(ProxyError):
    pass


class ValidationError(ProxyError):
    pass
