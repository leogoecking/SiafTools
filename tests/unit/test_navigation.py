import pytest

from siaf_support_toolbox.ui.navigation import (
    DEFAULT_PAGE_ID,
    NAVIGATION_ITEMS,
    VALID_PAGE_IDS,
    navigation_item,
)


def test_navigation_contains_the_roadmap_sections_once():
    labels = [item.label for item in NAVIGATION_ITEMS]

    assert labels == [
        "Painel",
        "Ambiente detectado",
        "Consultas",
        "Diagnósticos",
        "Relatórios",
        "Comparar lojas",
        "Operações controladas",
        "Backup",
        "Histórico e auditoria",
        "Base de conhecimento",
        "Configurações",
    ]
    assert len(VALID_PAGE_IDS) == len(NAVIGATION_ITEMS)
    assert DEFAULT_PAGE_ID in VALID_PAGE_IDS


def test_navigation_item_rejects_unknown_page():
    with pytest.raises(KeyError):
        navigation_item("unknown")
