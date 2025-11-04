"""Django application configuration for channels-rpc."""

from __future__ import annotations

import logging

logger = logging.getLogger("channels_rpc")


class ChannelsRpcConfig:
    """Django app configuration for channels-rpc.

    This AppConfig is used when channels-rpc is installed as a Django app.
    It performs initialization and validation when Django starts.

    Examples
    --------
    Add to INSTALLED_APPS in settings.py::

        INSTALLED_APPS = [
            ...
            'channels_rpc',
            ...
        ]

    Or specify the config explicitly::

        INSTALLED_APPS = [
            ...
            'channels_rpc.apps.ChannelsRpcConfig',
            ...
        ]
    """

    name = "channels_rpc"
    verbose_name = "Django Channels RPC"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Perform initialization when Django starts.

        This method is called once when Django initializes. It:
        - Loads and validates configuration
        - Logs initialization info
        - Performs any necessary setup

        Notes
        -----
        This method should not perform any database operations or import
        models, as it runs before Django is fully initialized.
        """
        from channels_rpc.config import get_config

        # Load configuration early to catch any issues
        config = get_config()

        # Log initialization with configuration summary
        logger.info(
            "channels-rpc initialized with limits: "
            "MAX_MESSAGE_SIZE=%d, MAX_ARRAY_LENGTH=%d, MAX_NESTING_DEPTH=%d",
            config.limits.max_message_size,
            config.limits.max_array_length,
            config.limits.max_nesting_depth,
        )

        if config.log_rpc_params:
            logger.warning(
                "LOG_RPC_PARAMS is enabled - RPC parameters will be logged. "
                "This may expose sensitive information (PII, credentials). "
                "Only enable in development environments."
            )
