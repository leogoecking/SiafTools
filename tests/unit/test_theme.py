from siaf_support_toolbox.ui.theme import PALETTES


def test_light_and_dark_palettes_define_distinct_surfaces():
    assert set(PALETTES) == {"light", "dark"}
    assert PALETTES["light"].background != PALETTES["dark"].background
    assert PALETTES["light"].foreground != PALETTES["dark"].foreground
    assert all(palette.accent.startswith("#") for palette in PALETTES.values())
