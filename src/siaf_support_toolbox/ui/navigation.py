from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NavigationItem:
    page_id: str
    label: str
    title: str
    description: str


NAVIGATION_ITEMS = (
    NavigationItem("dashboard", "Painel", "Painel", "Visão geral do ambiente e dos módulos."),
    NavigationItem(
        "environment",
        "Ambiente detectado",
        "Ambiente detectado",
        "Descoberta automática do SIAF, Firebird e bases candidatas.",
    ),
    NavigationItem(
        "queries",
        "Consultas",
        "Consultas",
        "Templates validados em modo somente leitura, com paginação e cancelamento.",
    ),
    NavigationItem(
        "diagnostics",
        "Diagnósticos",
        "Diagnósticos",
        "Disponível em uma fase futura.",
    ),
    NavigationItem("reports", "Relatórios", "Relatórios", "Disponível em uma fase futura."),
    NavigationItem(
        "compare",
        "Comparar lojas",
        "Comparar lojas",
        "Disponível em uma fase futura.",
    ),
    NavigationItem(
        "operations",
        "Operações controladas",
        "Operações controladas",
        "Disponível em uma fase futura.",
    ),
    NavigationItem("backup", "Backup", "Backup", "Disponível em uma fase futura."),
    NavigationItem(
        "history",
        "Histórico e auditoria",
        "Histórico e auditoria",
        "Disponível em uma fase futura.",
    ),
    NavigationItem(
        "knowledge",
        "Base de conhecimento",
        "Base de conhecimento",
        "Disponível em uma fase futura.",
    ),
    NavigationItem(
        "settings",
        "Configurações",
        "Configurações",
        "Preferências locais da aplicação.",
    ),
)

DEFAULT_PAGE_ID = "dashboard"
VALID_PAGE_IDS = frozenset(item.page_id for item in NAVIGATION_ITEMS)


def navigation_item(page_id: str) -> NavigationItem:
    for item in NAVIGATION_ITEMS:
        if item.page_id == page_id:
            return item
    raise KeyError(page_id)
