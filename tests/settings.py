"""Minimal Django settings for testing channels-rpc."""

SECRET_KEY = "test-secret-key-for-channels-rpc-testing"

INSTALLED_APPS = [
    "channels",
]

# Database configuration for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Channel layers configuration for testing
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Async support
ASGI_APPLICATION = None  # Set per test if needed

# Logging configuration for tests
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "channels_rpc": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}
