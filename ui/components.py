# ui/components.py
from __future__ import annotations

from typing import Optional, Tuple, Dict, List

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.tabbedpanel import TabbedPanel
from kivy.uix.widget import Widget
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty

from services.state import GameState
from services.economy import Economy


# ---------------------------------------------------------------------------
# KivyMD detection + fallbacks
# ---------------------------------------------------------------------------
# --- KivyMD fallback handling ---
HAS_MD = False
try:
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.card import MDCard
    from kivymd.uix.snackbar import Snackbar
    from kivymd.uix.screen import MDScreen
    from kivymd.uix.screenmanager import MDScreenManager
    from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
    from kivymd.uix.label import MDLabel  # <-- add this
    HAS_MD = True
except ImportError:
    MDBoxLayout = BoxLayout
    MDCard = BoxLayout
    MDScreen = Screen
    MDScreenManager = ScreenManager
    Snackbar = None
    MDBottomNavigation = TabbedPanel
    MDBottomNavigationItem = BoxLayout
    MDLabel = Label  # <-- fallback alias


    class Snackbar:  # type: ignore
        """Minimal shim so code that calls Snackbar(...).open() won't crash."""
        text: str = ""
        def __init__(self, text: str = "", **kwargs):
            self.text = text
        def open(self):
            print(f"[Snackbar] {self.text}")
        @staticmethod
        def show(text: str = "", **kwargs):
            print(f"[Snackbar.show] {text}")

    def _md_toast(message: str, *_, **__):  # type: ignore
        print(f"[Toast] {message}")

    _MDLabel = Label  # type: ignore

# Export consistent names
toast = _md_toast
MDLabel = _MDLabel


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _state():
    """Return the GameState stored on the running App (if present)."""
    return getattr(App.get_running_app(), "state", None)


def _toast(msg: str) -> None:
    """Safe toast helper (works with/without KivyMD)."""
    try:
        toast(msg)
    except Exception:
        old = Window.title
        Window.title = msg
        Clock.schedule_once(lambda *_: setattr(Window, "title", old), 1.0)

# Maintain compatibility with main.py expecting show_toast
def show_toast(text: str) -> None:
    _toast(text)


# ---------------------------------------------------------------------------
# Top bar and screen manager with bottom nav (so main.py can import them)
# ---------------------------------------------------------------------------
class TopBar(MDBoxLayout):
    """Simple top bar; coin text bound from main via ids or property."""
    coin_text = StringProperty("0")

    def __init__(self, app=None, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = "horizontal"
        self.padding = dp(8)
        self.spacing = dp(8)
        self.size_hint_y = None
        self.height = dp(56)

    def update_coin_label(self, coins: int) -> None:
        self.coin_text = str(coins)


class MDCompatibleScreenManager(MDScreenManager):
    """
    Wrapper that provides a bottom navigation (KivyMD if available,
    TabbedPanel fallback otherwise). main.py sets up screens and calls
    build_root_with_nav(topbar) to get the final root widget.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._root = None

    def build_root_with_nav(self, topbar: TopBar):
        from kivy.uix.boxlayout import BoxLayout

        root = BoxLayout(orientation="vertical")
        root.add_widget(topbar)
        root.add_widget(self)

        if HAS_MD and MDBottomNavigation:
            bn = MDBottomNavigation()
            # Create nav items (names must match screen names)
            for item_id, text, icon in [
                ("home", "Home", "home"),
                ("habitats", "Habitats", "terrain"),
                ("breeding", "Breeding", "egg"),
                ("dex", "Dex", "view-grid"),
                ("shop", "Shop", "cart"),
            ]:
                it = MDBottomNavigationItem(name=item_id, text=text, icon=icon)
                # clicking a tab should switch the ScreenManager current
                def _bind_switch(item_ref):
                    def _switch(*_a):
                        try:
                            self.current = item_ref.name
                        except Exception:
                            pass
                    return _switch
                it.bind(on_tab_press=_bind_switch(it))
                bn.add_widget(it)
            root.add_widget(bn)
        else:
            # Simple Kivy fallback: tabbed footer
            from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
            tp = TabbedPanel(do_default_tab=False, tab_height=dp(44), tab_width=dp(120))
            for nm, txt in [("home", "Home"), ("habitats", "Habitats"), ("breeding", "Breeding"),
                            ("dex", "Dex"), ("shop", "Shop")]:
                th = TabbedPanelHeader(text=txt)
                th.bind(on_release=lambda *_a, n=nm: setattr(self, "current", n))
                tp.add_widget(th)
            root.add_widget(tp)

        self._root = root
        return root


# ---------------------------------------------------------------------------
# Drag shadow overlay
# ---------------------------------------------------------------------------
class DragShadow(FloatLayout):
    """A lightweight floating card that follows the pointer during drag."""

    def __init__(self, title: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.size = Window.size  # full-window overlay
        self._card = MDCard(
            elevation=4,
            radius=[12],
            size_hint=(None, None),
            md_bg_color=(0.18, 0.18, 0.18, 0.95) if HAS_MD else (0, 0, 0, 0),
        )
        self._card.size = (dp(160), dp(48))

        # Create the label safely for MD/non-MD cases
        if HAS_MD:
            lbl = MDLabel(
                text=title,
                halign="center",
                valign="middle",
                size_hint=(1, 1),
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                font_size="15sp",
            )
        else:
            lbl = Label(
                text=title,
                halign="center",
                valign="middle",
                size_hint=(1, 1),
                font_size="15sp",
            )
            # ensure halign/valign apply by binding text_size
            lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self._label = lbl
        self._card.add_widget(self._label)
        self.add_widget(self._card)

    def move_to(self, pos: Tuple[float, float]) -> None:
        x, y = pos
        self._card.pos = (x - self._card.width / 2, y - self._card.height / 2)

# ---------------------------------------------------------------------------
# ArmadilloCard (tap to select, long-press to drag)
# ---------------------------------------------------------------------------
class ArmadilloCard(ButtonBehavior, MDCard):
    """
    Tap to select; long-press (~0.35s) starts drag to a habitat.
    Shows a left avatar (colored circle) + name + subtitle.
    Selection adds a subtle outline.
    """

    def __init__(self, armadillo_id: str, name: str, subtitle: str = "", color_name: str = "Brown", **kwargs) -> None:
        super().__init__(**kwargs)
        self.armadillo_id = armadillo_id
        self.armadillo_name = name
        self._color_name = color_name


        # visuals
        self.radius = [12]
        self.padding = dp(10)
        self.size_hint_y = None
        self.height = dp(96)
        if hasattr(self, "md_bg_color"):
            self.md_bg_color = (0.16, 0.16, 0.16, 1)

        # selection outline
        with self.canvas.after:
            Color(0, 0, 0, 0)  # off by default
            self._sel_color = self.canvas.after.children[0]  # Color instruction handle
            Rectangle(pos=self.pos, size=self.size)
            self._sel_rect = self.canvas.after.children[0]
        self.bind(pos=self._update_outline, size=self._update_outline)

        # content: avatar + text
        row = MDBoxLayout(orientation="horizontal", spacing=dp(10))
        avatar = Widget(size_hint=(None, None), size=(dp(48), dp(48)))
        with avatar.canvas:
            r, g, b, a = self._color_rgba(self._color_name)
            Color(r, g, b, a)
            Ellipse(pos=avatar.pos, size=avatar.size)
        avatar.bind(pos=lambda *_: self._refresh_avatar(avatar), size=lambda *_: self._refresh_avatar(avatar))
        row.add_widget(avatar)

        col = MDBoxLayout(orientation="vertical", spacing=dp(2))
        col.add_widget(MDLabel(text=name, halign="left", font_size="15sp"))
        if subtitle:
            if HAS_MD:
                sub = MDLabel(
                    text=subtitle,
                    halign="left",
                    font_size="12sp",
                    theme_text_color="Secondary",
                )
            else:
                sub = Label(text=subtitle, halign="left", font_size="12sp")
                sub.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            col.add_widget(sub)

        row.add_widget(col)
        self.add_widget(row)

        # drag state
        self._lp_ev = None
        self._dragging = False
        self._shadow: Optional[DragShadow] = None

    # ----- avatar helpers -----
    @staticmethod
    def _color_rgba(name: str) -> Tuple[float, float, float, float]:
        # simple palette; extend as you add traits
        palette = {
            "Brown": (0.49, 0.33, 0.25, 1),
            "Albino": (0.95, 0.95, 0.95, 1),
            "Blue": (0.25, 0.5, 0.95, 1),
            "Green": (0.25, 0.75, 0.35, 1),
            "Red":   (0.85, 0.25, 0.25, 1),
            "Gold":  (0.95, 0.80, 0.20, 1),
        }
        return palette.get(name, (0.6, 0.6, 0.6, 1))

    def _refresh_avatar(self, avatar: Widget) -> None:
        # redraw the circle when the widget resizes/moves
        avatar.canvas.clear()
        with avatar.canvas:
            r, g, b, a = self._color_rgba(self._color_name)
            Color(r, g, b, a)
            Ellipse(pos=avatar.pos, size=avatar.size)

    def _update_outline(self, *_args) -> None:
        self._sel_rect.pos = self.pos
        self._sel_rect.size = self.size

    # ----- app/screen helpers -----
    @staticmethod
    def _hab_screen() -> Optional["HabitatsScreen"]:
        root = App.get_running_app().root
        for w in root.walk():
            if getattr(w, "id", None) == "habitats_screen":
                return w  # type: ignore[return-value]
        return None

    def _start_drag(self, *_args) -> None:
        st = _state()
        if not st or getattr(st, "selected_id", None) != self.armadillo_id:
            return
        self._dragging = True
        self._shadow = DragShadow(self.armadillo_name)
        Window.add_widget(self._shadow)

    def _cancel_longpress(self) -> None:
        if self._lp_ev is not None:
            self._lp_ev.cancel()
            self._lp_ev = None

    # ----- ButtonBehavior: tap selection -----
    def on_release(self):
        # select on tap and show outline
        st = _state()
        if st:
            if hasattr(st, "select"):
                st.select(self.armadillo_id)
            elif hasattr(st, "select_armadillo"):
                st.select_armadillo(self.armadillo_id)
        # visual outline for feedback
        self._sel_color.rgba = (0.2, 0.8, 0.7, 0.9)
        Clock.schedule_once(lambda *_: setattr(self._sel_color, "rgba", (0, 0, 0, 0)), 0.25)
        _toast(f"Selected {self.armadillo_name}")

    # ----- touch handlers for long-press drag -----
    def on_touch_down(self, touch) -> bool:
        if self.collide_point(*touch.pos):
            self._lp_ev = Clock.schedule_once(self._start_drag, 0.35)
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch) -> bool:
        if touch.grab_current is self:
            if self._dragging and self._shadow:
                self._shadow.move_to(touch.pos)
                hs = self._hab_screen()
                if hs:
                    hs.highlight_dropzones(touch.pos, True)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch) -> bool:
        if touch.grab_current is self:
            touch.ungrab(self)
            was_dragging = self._dragging
            self._cancel_longpress()
            hs = self._hab_screen()
            if was_dragging:
                if hs:
                    hs.try_drop(touch.pos)
                    hs.highlight_dropzones(touch.pos, False)
                if self._shadow:
                    Window.remove_widget(self._shadow)
                self._shadow = None
                self._dragging = False
                return True
        return super().on_touch_up(touch)

    # ---- Touch handling ----
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._press_time = time.time()
            # Long-press to start drag if this card is already selected
            Clock.schedule_once(lambda *_: self._maybe_start_drag(touch), 0.35)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._drag_shadow:
            # follow pointer
            self._drag_shadow.pos = (touch.x - self._drag_shadow.width / 2,
                                     touch.y - self._drag_shadow.height / 2)
            # highlight drop zones if available
            try:
                GameState.instance().app.root.ids.habitats.highlight_dropzones(touch.pos, True)  # type: ignore[attr-defined]
            except Exception:
                pass
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        # Finish drag if active
        if self._drag_shadow:
            try:
                app = GameState.instance().app
                app.root.ids.habitats.highlight_dropzones(touch.pos, False)  # type: ignore[attr-defined]
                app.root.ids.habitats.try_drop(touch.pos)  # type: ignore[attr-defined]
            except Exception:
                pass
            Window.remove_widget(self._drag_shadow)
            self._drag_shadow = None
        else:
            # Simple tap → select
            if self.collide_point(*touch.pos):
                GameState.instance().select(self.did)
                show_toast(f"Selected: {self.name}")
        self._press_time = None
        return super().on_touch_up(touch)

    # ---- Drag helpers ----
    def _maybe_start_drag(self, touch):
        if self._press_time is None:  # touch was released
            return
        gs = GameState.instance()
        sel = gs.get_selected()
        if not sel or sel.id != self.did:
            return  # only drag the currently selected card
        if not self._drag_shadow:
            self._drag_shadow = DragShadow(self.name)
            Window.add_widget(self._drag_shadow)
            # position immediately so there’s no visual jump
            self._drag_shadow.pos = (touch.x - self._drag_shadow.width / 2,
                                     touch.y - self._drag_shadow.height / 2)


    # ----- internal helpers -----
    @staticmethod
    def _hab_screen() -> Optional["HabitatsScreen"]:
        """Find the Habitats screen by id without importing App logic here."""
        root = App.get_running_app().root
        for w in root.walk():
            if getattr(w, "id", None) == "habitats_screen":
                return w  # type: ignore[return-value]
        return None

    def _start_drag(self, *_args) -> None:
        """Begin dragging only if this card is currently selected in GameState."""
        st = _state()
        if not st or getattr(st, "selected_id", None) != self.armadillo_id:
            return
        self._dragging = True
        self._shadow = DragShadow(self.armadillo_name)
        Window.add_widget(self._shadow)

    def _cancel_longpress(self) -> None:
        if self._lp_ev is not None:
            self._lp_ev.cancel()
            self._lp_ev = None

    # ----- touch handlers -----
    def on_touch_down(self, touch) -> bool:
        if self.collide_point(*touch.pos):
            # schedule long-press; quick tap will cancel it in on_touch_up
            self._lp_ev = Clock.schedule_once(self._start_drag, 0.35)
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch) -> bool:
        if touch.grab_current is self:
            if self._dragging and self._shadow:
                self._shadow.move_to(touch.pos)
                hs = self._hab_screen()
                if hs:
                    hs.highlight_dropzones(touch.pos, True)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch) -> bool:
        if touch.grab_current is self:
            touch.ungrab(self)
            was_dragging = self._dragging
            self._cancel_longpress()

            hs = self._hab_screen()
            if was_dragging:
                if hs:
                    hs.try_drop(touch.pos)
                    hs.highlight_dropzones(touch.pos, False)
                if self._shadow:
                    Window.remove_widget(self._shadow)
                self._shadow = None
                self._dragging = False
                return True

            # quick tap → select this card
            st = _state()
            if st:
                if hasattr(st, "select"):
                    st.select(self.armadillo_id)
                elif hasattr(st, "select_armadillo"):
                    st.select_armadillo(self.armadillo_id)  # legacy name
                _toast(f"Selected {self.armadillo_name}")
            return True
        return super().on_touch_up(touch)


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
class BaseScreen(MDScreen):
    app = ObjectProperty(None)  # <-- add this line

    def refresh(self) -> None:
        pass



class HomeScreen(BaseScreen):
    def refresh(self) -> None:
        st = _state()
        if not st:
            return
        sel = getattr(st, "get_selected", lambda: None)()
        self.ids.selected_label.text = f"Selected: {getattr(sel, 'name', 'None')}"
        inv = getattr(st, "inventory", {})
        self.ids.inventory_label.text = f"Food: {inv.get('food',0)} • Toys: {inv.get('toy',0)}"
        self.ids.feed_btn.disabled = sel is None
        self.ids.pet_btn.disabled = sel is None

        lst = self.ids.home_list
        lst.clear_widgets()
        for d in getattr(st, "armadillos", []):
            subtitle = f"{d.sex} • {d.color} • Hunger {d.hunger}% • Happy {d.happiness}%"
            lst.add_widget(ArmadilloCard(d.id, d.name, subtitle, getattr(d, "color", "Brown")))

    def on_feed(self) -> None:
        st = _state()
        if not st:
            return
        ok = getattr(st, "feed_selected", lambda: False)()
        _toast("Fed!" if ok else "Need food. Buy in Shop.")
        self.refresh()

    def on_pet(self) -> None:
        st = _state()
        if not st:
            return
        ok = getattr(st, "pet_selected", lambda: False)()
        _toast("Pet!" if ok else "Select an armadillo first.")
        self.refresh()


        # Roster
        roster_len = len(gs.armadillos)
        lst = self.ids.home_list

        if roster_len != self._last_roster_len:
            # Rebuild only if the number of cards changed
            self._last_roster_len = roster_len
            lst.clear_widgets()
            for d in gs.armadillos:
                subtitle = f"{d.sex} • {d.color} • Hunger {d.hunger}% • Happy {d.happiness}%"
                card = ArmadilloCard(did=d.id, name=d.name, subtitle=subtitle)
                lst.add_widget(card)
        else:
            # Update existing cards' subtitles in place
            cards = list(getattr(lst, "children", []))
            id_to_card = {getattr(c, "did", None): c for c in cards}
            for d in gs.armadillos:
                card = id_to_card.get(d.id)
                if card:
                    card.name = d.name
                    card.subtitle = (
                        f"{d.sex} • {d.color} • Hunger {d.hunger}% • Happy {d.happiness}%"
                    )

    def on_feed(self) -> None:
        ok = GameState.instance().feed_selected()
        show_toast("Fed!" if ok else "Need food. Buy in Shop.")
        self.refresh()

    def on_pet(self) -> None:
        ok = GameState.instance().pet_selected()
        show_toast("Pet!" if ok else "Select an armadillo first.")
        self.refresh()


class HabitatsScreen(BaseScreen):
    """
    Handles highlighting and accepting drops, upgrades, and label refresh.
    Expects ids: hab_card_1..3, hab_cap_1..3, hab_occ_1..3 (from KV).
    """

    def _collect_dropzones(self) -> Dict[Widget, str]:
        """Map visible cards to their corresponding habitat *ids* (not indexes)."""
        st = _state()
        zones: Dict[Widget, str] = {}
        if not st:
            return zones
        habitats = getattr(st, "habitats", [])
        for idx in (1, 2, 3):
            card = self.ids.get(f"hab_card_{idx}")
            if card and len(habitats) >= idx:
                zones[card] = habitats[idx - 1].id
        return zones

    def highlight_dropzones(self, pos, active: bool) -> None:
        zones = self._collect_dropzones()
        for card in zones.keys():
            card.opacity = 0.95 if active else 1.0
        if active:
            for card in zones.keys():
                if card.collide_point(*card.to_widget(*pos)):
                    card.opacity = 1.0
                    break

    def try_drop(self, pos) -> bool:
        st = _state()
        if not st:
            return False
        zones = self._collect_dropzones()
        target_hid: Optional[str] = None
        for card, hid in zones.items():
            if card.collide_point(*card.to_widget(*pos)):
                target_hid = hid
                break
        if not target_hid:
            _toast("No habitat under drop")
            return False

        result = st.move_selected_to_habitat(target_hid)
        ok, msg = (
            result if isinstance(result, tuple) else (bool(result), "Moved" if result else "Cannot move")
        )
        _toast(msg)
        if ok:
            self.refresh()
        return ok

    def refresh(self) -> None:
        st = _state()
        if not st:
            return
        habitats: List = getattr(st, "habitats", [])[:3]

        def name_lookup(aid: str) -> str:
            if hasattr(st, "get_by_id"):
                obj = st.get_by_id(aid)
                return getattr(obj, "name", aid) if obj else aid
            if hasattr(st, "get_name_by_id"):
                return st.get_name_by_id(aid)
            return aid

        rows = [
            (self.ids.hab_cap_1, self.ids.hab_occ_1, 0),
            (self.ids.hab_cap_2, self.ids.hab_occ_2, 1),
            (self.ids.hab_cap_3, self.ids.hab_occ_3, 2),
        ]
        for cap_lbl, occ_lbl, i in rows:
            if i < len(habitats):
                h = habitats[i]
                used = len(getattr(h, "occupants", []))
                cap_lbl.text = f"Lv {h.level} • Cap {used}/{h.capacity}"
                names = [name_lookup(aid) for aid in h.occupants]
                occ_lbl.text = "Occupants: " + (", ".join(names) if names else "—")
            else:
                cap_lbl.text = "Lv 0 • Cap 0/0"
                occ_lbl.text = "Occupants: —"

    def on_upgrade(self, hid_idx: int) -> None:
        st = _state()
        if not st:
            _toast("State unavailable")
            return
        habitats = getattr(st, "habitats", [])
        if 1 <= hid_idx <= len(habitats):
            hid = habitats[hid_idx - 1].id
            result = st.upgrade_habitat(hid, Economy.COST_HABITAT_UPGRADE, Economy.UPGRADE_CAPACITY_DELTA)
            ok, msg = (
                result if isinstance(result, tuple) else (bool(result), "Upgraded" if result else "Cannot upgrade")
            )
            _toast(msg)
            if ok and hasattr(App.get_running_app(), "refresh_all"):
                App.get_running_app().refresh_all()
            else:
                self.refresh()
        else:
            _toast("No such habitat")


class BreedingScreen(BaseScreen):
    """Breeding UI: pick parents, show queue, and start incubation."""

    @staticmethod
    def _parse_id(text: str) -> Optional[str]:
        """Extract the trailing (id) from 'Name (id)'; returns None if invalid."""
        if not text or "(" not in text or not text.endswith(")"):
            return None
        try:
            return text[text.rindex("(") + 1 : -1].strip()
        except Exception:
            return None

    def refresh(self) -> None:
        st = _state()
        if not st:
            return
        try:
            adults = st.adults() or []
        except Exception:
            adults = []
        dads = [f"{a.name} ({a.id})" for a in adults if getattr(a, "sex", None) == "M"]
        moms = [f"{a.name} ({a.id})" for a in adults if getattr(a, "sex", None) == "F"]
        self.ids.dad_spinner.values = dads
        self.ids.mom_spinner.values = moms
        if not dads:
            self.ids.dad_spinner.text = "Pick Male"
        if not moms:
            self.ids.mom_spinner.text = "Pick Female"

        box = self.ids.queue_box
        box.clear_widgets()
        for job in getattr(st, "breeding_queue", []):
            try:
                jid = getattr(job, "id", "") or ""
                tail = jid[-4:] if len(jid) >= 4 else jid
                remaining = getattr(job, "remaining", lambda: 0)()
                box.add_widget(Label(text=f"Egg {tail} • {remaining}s"))
            except Exception:
                box.add_widget(Label(text="Egg ???? • --s"))

    def on_start_breeding(self) -> None:
        st = _state()
        if not st:
            return
        dad_id = self._parse_id(self.ids.dad_spinner.text)
        mom_id = self._parse_id(self.ids.mom_spinner.text)
        if not dad_id or not mom_id or dad_id == mom_id:
            _toast("Pick a male and a female adult.")
            return
        try:
            job = st.start_breeding(dad_id, mom_id, duration_s=Economy.DEFAULT_INCUBATION_S)
        except TypeError:
            job = st.start_breeding(dad_id, mom_id, Economy.DEFAULT_INCUBATION_S)
        _toast("Incubation started!" if job else "Invalid pair.")
        self.refresh()


class DexScreen(BaseScreen):
    """Dex: show discovered colors (simple labels in a 3-col grid)."""
    def refresh(self) -> None:
        st = _state()
        if not st:
            return
        grid = self.ids.dex_grid
        grid.clear_widgets()
        colors = sorted(getattr(st, "dex_colors", set()))
        for color in colors:
            if HAS_MD:
                w = MDLabel(text=color, halign="center", size_hint_y=None, height=dp(28),
                            theme_text_color="Primary")
            else:
                w = Label(text=color, halign="center", size_hint_y=None, height=dp(28))
                w.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            grid.add_widget(w)


class ShopScreen(BaseScreen):
    def on_buy_food(self) -> None:
        st = _state()
        if not st:
            return
        ok = st.buy("food", Economy.COST_FOOD)
        _toast("Bought food!" if ok else "Not enough coins.")
        self.refresh()

    def on_buy_toy(self) -> None:
        st = _state()
        if not st:
            return
        ok = st.buy("toy", Economy.COST_TOY)
        _toast("Bought toy!" if ok else "Not enough coins.")
        self.refresh()

    def refresh(self) -> None:
        st = _state()
        if not st:
            return
        inv = getattr(st, "inventory", {})
        food = inv.get("food", 0)
        toy = inv.get("toy", 0)
        self.ids.shop_inv.text = f"Food: {food} • Toys: {toy}"
