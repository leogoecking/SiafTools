import json
import threading

from siaf_support_toolbox.ui.navigation import DEFAULT_PAGE_ID
from siaf_support_toolbox.ui.preferences import WindowPreferences, WindowPreferencesStore


def test_window_preferences_normalize_size_position_theme_and_page():
    preferences = WindowPreferences(
        width=200,
        height=100,
        x=9_999,
        y=-50,
        theme="invalid",
        selected_page="unknown",
    )

    normalized = preferences.normalized(screen_width=1280, screen_height=720)

    assert (normalized.width, normalized.height) == (900, 600)
    assert (normalized.x, normalized.y) == (380, 0)
    assert normalized.theme == "light"
    assert normalized.selected_page == DEFAULT_PAGE_ID


def test_window_preferences_round_trip_without_sensitive_fields(tmp_path):
    store = WindowPreferencesStore(tmp_path / "window-state.json")
    expected = WindowPreferences(
        width=1200,
        height=700,
        x=25,
        y=35,
        maximized=True,
        theme="dark",
        selected_page="environment",
    )

    store.save(expected)
    loaded = store.load()
    content = store.path.read_text(encoding="utf-8")

    assert loaded == expected
    assert "password" not in content.lower()
    assert "senha" not in content.lower()


def test_window_preferences_ignore_invalid_json(tmp_path):
    path = tmp_path / "window-state.json"
    path.write_text("{invalid", encoding="utf-8")

    loaded = WindowPreferencesStore(path).load()

    assert loaded == WindowPreferences()


def test_window_preferences_ignore_invalid_value_types(tmp_path):
    path = tmp_path / "window-state.json"
    path.write_text(
        json.dumps(
            {
                "width": True,
                "height": "large",
                "x": "left",
                "y": [],
                "maximized": "yes",
            }
        ),
        encoding="utf-8",
    )

    assert WindowPreferencesStore(path).load() == WindowPreferences()


def test_window_preferences_preserve_secondary_and_left_monitor_coordinates():
    secondary = WindowPreferences(width=1120, height=720, x=1920, y=100).normalized(
        screen_width=3840,
        screen_height=1080,
        screen_x=0,
        screen_y=0,
    )
    left = WindowPreferences(width=1120, height=720, x=-1600, y=80).normalized(
        screen_width=3840,
        screen_height=1080,
        screen_x=-1920,
        screen_y=0,
    )

    assert (secondary.x, secondary.y) == (1920, 100)
    assert (left.x, left.y) == (-1600, 80)


def test_concurrent_window_preference_saves_use_independent_temporary_files(tmp_path):
    store = WindowPreferencesStore(tmp_path / "window-state.json")
    workers = 20
    barrier = threading.Barrier(workers)
    errors: list[Exception] = []

    def save(index: int) -> None:
        try:
            barrier.wait(timeout=5)
            store.save(WindowPreferences(x=index, selected_page="dashboard"))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=save, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert store.load().selected_page == "dashboard"
    assert not list(tmp_path.glob("*.tmp"))
