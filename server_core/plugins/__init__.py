from typing import Dict, Optional

from .base import BasePlugin
from .weather import WeatherPlugin


_registry: Dict[str, BasePlugin] = {
    "WEATHER": WeatherPlugin(),
}


def get_plugin(topic: str) -> Optional[BasePlugin]:
    return _registry.get(topic)

