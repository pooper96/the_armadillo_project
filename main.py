# main.py
from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import List

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.utils import platform

# Prefer KivyMD; fallback to Kivy App
HAS_MD = True
try:
    from kivymd.app import MDApp as _BaseApp
    from kivymd.uix.dialog import MDDialog
except Exception:
    from kivy.app import App as _BaseApp  # type: ignore[assignment]
    MDDialog = None  # type: ignore[assignment]
    HAS_MD = False

from services.state import GameState
from services.persistence import Persistence
from services.economy import Economy
from ui.components import (
    show_toast,
    MDCompatibleScreenManager,
    HomeScreen,
    HabitatsScreen,
    BreedingScreen,
    DexScreen,
    ShopScreen,
    TopBar,
)

ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAsSAAALEgHS3X78AAAA"
    "GXRFWHRTb2Z0d2FyZQBwYWludC5uZXQgNC4xLjFhZkzvAAABUUlEQVR4nO2aMW7CMBBFZ2wI4k8p"
    "Jg1oQF7GQ5w0rIapQh0h7kL5Ck9kN8m2m8Jg6bq6J5ncrj3y5m8kq3fG1u4m3g0k8H9mJ5rS6u4o"
    "A8C3b3s2zqC6z0aQ8JwV3mF3g8r3o4cH6Cqv1b8h4fZ2v3l3wQy+o9W4oQ8o7y1mF6y0Vq9k5JrF"
    "8hZkDqg0pVqVgk1m1m3yC9lq2w9E2lJ0wB0rA0eY7gVq2bVj6cJ0gqVYyx4Q7g1sCkpQGm9g2F0x"
    "1k3Jwqgk8oH1s8y7C3Jr2rZQ8R1l/2vC5Cwq8oZ7q0b6sU5gYI/0qk4sB0lq9o8JcYyqg1c1G3wH"
    "kQ3qQy9o2qv7Xq0wZ8pZl3oWQ8M0oVQb4l5pQy4W2Rk3qf1C6k8B7oG1l2R4YwH7p8m9f4QHf2q/"
    "7s4k0eG3G3wC3w8Kxk7o3X1kYk8tHq8i6wVXK6i4Q0cP7l4gQFQnQ0r9wF2dF6Z3sQAAAABJRU5E"
    "rkJggg=="
)


class ArmadilloApp(_BaseApp):
    title = "Armadillo Farmer"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = GameState.instance()
        self.state.app = self
        self._autosave_trigger = Clock.create_trigger(self._save, 0.6)
        self.topbar: TopBar | None = None
        self.sm: MDCompatibleScreenManager | None = None

    # ---------- Persistence helpers ----------
    def _save_path(self) -> Path:
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        return Path(self.user_data_dir) / "save.json"

    def _save(self, *_):
        """Autosave with flexible Persistence API support."""
        path = str(self._save_path())
        try:
            Persistence.save(path, self.state.to_dict())  # (path, dict)
        except TypeError:
            try:
                Persistence.save(path, self.state)  # (path, state)
            except TypeError:
                Persistence.save(self.state)  # (state)

    def _load_or_seed(self) -> None:
        """Load game state using flexible signatures; seed on first run."""
        path = str(self._save_path())
        data = None
        try:
            data = Persistence.load(path)  # (path)
        except TypeError:
            try:
                data = Persistence.load(path, self.state)  # (path, state)
            except TypeError:
                try:
                    data = Persistence.load(self.state)  # (state)
                except TypeError:
                    data = None

        if isinstance(data, dict) and data:
            self.state.from_dict(data)
            self.state.meta["first_run"] = False
        elif data:
            self.state.meta["first_run"] = False  # loader mutated state in place
        else:
            self.state.seed_starters()
            self.state.meta["first_run"] = True
            self._save()

    # ---------- App lifecycle ----------
    def build(self):
        self._ensure_assets()
        self.icon = str(self._icon_path())
        if HAS_MD:
            self.theme_cls.theme_style = "Dark"  # type: ignore[attr-defined]
            self.theme_cls.primary_palette = "Teal"  # type: ignore[attr-defined]
        self._load_kv_if_present()
        if platform not in ("android", "ios"):
            Window.size = (420, 780)

        self.topbar = TopBar()
        self.sm = MDCompatibleScreenManager()
        self._add_screens(self.sm)
        root = self.sm.build_root_with_nav(self.topbar)

        self._load_or_seed()
        self._wire_observer()
        Clock.schedule_interval(self._tick, 0.25)
        self._refresh_all()
        return root

    def on_start(self):
        if self.state.meta.get("first_run"):
            show_toast("Welcome! Your farm is ready.")
        self._update_topbar()

    def on_pause(self):
        self._save()
        return True

    def on_stop(self):
        self._save()

    # ---------- Build helpers ----------
    def _add_screens(self, sm: MDCompatibleScreenManager) -> None:
        sm.add_widget(HomeScreen(name="home", app=self))
        sm.add_widget(HabitatsScreen(name="habitats", app=self))
        sm.add_widget(BreedingScreen(name="breeding", app=self))
        sm.add_widget(DexScreen(name="dex", app=self))
        sm.add_widget(ShopScreen(name="shop", app=self))
        sm.current = "home"

    def _load_kv_if_present(self) -> None:
        kv_path = Path("kv/main.kv")
        if kv_path.exists():
            Builder.load_file(str(kv_path))

    # ---------- Observer / autosave ----------
    def _wire_observer(self) -> None:
        def _obs():
            self._update_topbar()
            self._autosave_trigger()
            self._refresh_current()
        self.state.add_observer(_obs)

    # ---------- Tick / hatch flow ----------
    def _tick(self, dt: float):
        babies = self.state.breeding_tick(time.time())
        if not babies:
            return
        self.state.add_coins(Economy.REWARD_HATCH * len(babies))
        names = [f"{b.name} ({b.color})" for b in babies]
        show_toast(f"Hatched: {', '.join(names)}")
        self._show_hatch_dialog(names)
        self._refresh_all()

    def _show_hatch_dialog(self, lines: List[str]) -> None:
        if HAS_MD and MDDialog:
            MDDialog(title="New Hatchlings!", text="\n".join(lines), buttons=[]).open()

    # ---------- UI updates ----------
    def _update_topbar(self) -> None:
        if self.topbar:
            self.topbar.update_coin_label(self.state.coins)

    def _refresh_current(self) -> None:
        if not self.sm:
            return
        screen = self.sm.get_screen(self.sm.current)
        if hasattr(screen, "refresh"):
            screen.refresh()  # type: ignore[func-returns-value]

    def _refresh_all(self) -> None:
        if not self.sm:
            return
        for name in ("home", "habitats", "breeding", "dex", "shop"):
            scr = self.sm.get_screen(name)
            if hasattr(scr, "refresh"):
                scr.refresh()  # type: ignore[func-returns-value]

    # ---------- Assets ----------
    def _icon_path(self) -> Path:
        assets_dir = Path("assets")
        assets_dir.mkdir(parents=True, exist_ok=True)
        return assets_dir / "icon.png"

    def _ensure_assets(self) -> None:
        icon_path = self._icon_path()
        if icon_path.exists():
            return
        with open(icon_path, "wb") as f:
            f.write(base64.b64decode(ICON_B64))


if __name__ == "__main__":
    ArmadilloApp().run()
