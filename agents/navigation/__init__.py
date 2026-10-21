"""Serviços de navegação compartilhados pelas entidades."""

from agents.navigation.bfs import find_path
from agents.navigation.service import NavigationService

__all__ = ["NavigationService", "find_path"]
