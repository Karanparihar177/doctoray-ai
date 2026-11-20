"""Pick the LLM provider from configuration.

Switching vendor is a settings change (LLM_PROVIDER, LLM_MODEL, key), not a
code change. Each adapter module registers a factory under its name.
"""

from collections.abc import Callable

from app.core.config import Settings, settings as default_settings
from app.services.llm.base import LLMProvider
from app.services.llm.errors import ProviderConfigError

ProviderFactory = Callable[[Settings], LLMProvider]

_FACTORIES: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    _FACTORIES[name.lower()] = factory


def available_providers() -> list[str]:
    return sorted(_FACTORIES)


def create_provider(config: Settings = default_settings) -> LLMProvider:
    name = (config.llm_provider or "").lower()
    if not name:
        raise ProviderConfigError("LLM_PROVIDER is not set")
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ProviderConfigError(
            f"Unknown LLM provider '{name}'. Available: {available_providers() or 'none yet'}"
        ) from None
    return factory(config)
