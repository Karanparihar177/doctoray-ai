import pytest

from app.core.config import Settings
from app.services.llm import registry
from app.services.llm.errors import ProviderConfigError
from tests.llm_helpers import ScriptedProvider


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(registry._FACTORIES)
    registry._FACTORIES.clear()
    yield
    registry._FACTORIES.clear()
    registry._FACTORIES.update(saved)


def test_provider_is_chosen_by_name_from_settings():
    registry.register_provider("Scripted", lambda cfg: ScriptedProvider())

    provider = registry.create_provider(Settings(llm_provider="scripted", _env_file=None))

    assert provider.name == "scripted"


def test_factory_receives_the_settings():
    seen = {}
    registry.register_provider("x", lambda cfg: seen.setdefault("model", cfg.llm_model) and ScriptedProvider())

    registry.create_provider(Settings(llm_provider="x", llm_model="m-1", _env_file=None))

    assert seen["model"] == "m-1"


def test_missing_provider_setting_is_an_error():
    with pytest.raises(ProviderConfigError, match="LLM_PROVIDER is not set"):
        registry.create_provider(Settings(_env_file=None))


def test_unknown_provider_lists_the_available_ones():
    registry.register_provider("a", lambda cfg: ScriptedProvider())

    with pytest.raises(ProviderConfigError, match=r"Unknown LLM provider 'b'.*\['a'\]"):
        registry.create_provider(Settings(llm_provider="b", _env_file=None))
