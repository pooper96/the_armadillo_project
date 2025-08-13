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

from services.economy import Economy

# ---------------------------------------------------------------------------
# KivyMD detection + fallbacks
# ---------------------------------------------------------------------------
HAS_MD = False
try:
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.card import MDCard
    from kivymd.uix.snackbar import Snackbar
    from kivymd.uix.screen import MDScreen
    from kivymd.uix.screenmanager import MDScreenManager
    from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
    from kivymd.uix.label import MDLabel as _MDLabel
    from kivymd.toast import toast as _md_toast
    HAS_MD = True
except Exception:
    # Fallbacks so the app still runs without KivyMD installed
    MDBoxLayout = BoxLayout          # type: ignore
    MDCard = BoxLayout               # type: ignore
    MDScreen = Screen                # type: ignore
    MDScreenManager = ScreenManager  # type: ignore
    MDBottomNavigation = TabbedPanel # type: ignore
    MDBottomNavigationItem = BoxLayout  # type: ignore

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
        self._label = MDLabel(
            text=title,
            halign="center",
            valign="middle",
            size_hint=(1, 1),
            theme_text_color="Custom" if HAS_MD else "Primary",
            text_color=(1, 1, 1, 1) if HAS_MD else (1, 1, 1, 1),
            font_size="15sp",
        )
        self._card.add_widget(self._label)
        self.add_widget(self._card)

    def move_to(self, pos: Tuple[float, float]) -> None:
        x, y = pos
        self._card.pos = (x - self._card.width / 2, y - self._card.height / 2)


# ---------------------------------------------------------------------------
# ArmadilloCard (tap to select, long-press to drag)
# ---------------------------------------------------------------------------
class ArmadilloCard(MDCard):
    """
    Tap to select; long-press (~0.35s) to start drag to a habitat.
    Drag shows a floating shadow, highlights habitats while hovering,
    and drops into the card under the pointer on release.
    """

    def __init__(self, armadillo_id: str, name: str, subtitle: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.armadillo_id = armadillo_id
        self.armadillo_name = name
        # visuals
        self.radius = [12]
        self.padding = dp(10)
        self.size_hint_y = None
        self.height = dp(96)
        if hasattr(self, "md_bg_color"):
            self.md_bg_color = (0.16, 0.16, 0.16, 1)  # KivyMD
        # content
        row = MDBoxLayout(orientation="vertical", spacing=dp(2))
        row.add_widget(MDLabel(text=name, halign="left", font_size="15sp"))
        if subtitle:
            row.add_widget(
                MDLabel(
                    text=subtitle,
                    halign="left",
                    font_size="12sp",
                    theme_text_color="Secondary" if HAS_MD else "Primary",
                )
            )
        self.add_widget(row)
        # drag state
        self._lp_ev = None
        self._dragging = False
        self._shadow: Optional[DragShadow] = None

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
                # prefer `select()` if available; fall back to `select_armadillo()`
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
    def refresh(self) -> None:  # overridden by children
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
        # simple rebuild for correctness; optimize later if needed
        lst.clear_widgets()
        for d in getattr(st, "armadillos", []):
            subtitle = f"{d.sex} • {d.color} • Hunger {d.hunger}% • Happy {d.happiness}%"
            lst.add_widget(ArmadilloCard(d.id, d.name, subtitle))

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


class HabitatsScreen(BaseScreen):
    """
    Handles highlighting and accepting drops, upgrades, and label refresh.
    Expects ids: hab_card_1..3, hab_cap_1..3, hab_occ_1..3 (from KV).
    """

    # ---- dropzone plumbing ----
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
                # convert window coords to local
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

        # state API: move_selected_to_habitat(habitat_id: str) -> bool or (bool,msg)
        result = st.move_selected_to_habitat(target_hid)
        ok, msg = (
            result if isinstance(result, tuple) else (bool(result), "Moved" if result else "Cannot move")
        )
        _toast(msg)
        if ok:
            self.refresh()
        return ok

    # ---- UI sync / actions ----
    def refresh(self) -> None:
        st = _state()
        if not st:
            return
        habitats: List = getattr(st, "habitats", [])[:3]

        def name_lookup(aid: str) -> str:
            # prefer get_by_id(); fallback to get_name_by_id() if you implemented it
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
        """Upgrade the Nth (1-based) habitat card shown."""
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

        # Populate spinners with adult M/F options as "Name (id)"
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

        # Rebuild queue list: "Egg #### • XXs"
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
        # start job (support either signature variant)
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
