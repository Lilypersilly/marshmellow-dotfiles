#!/usr/bin/env python3
import gi
import os
import re
import subprocess
import sys

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk

CSS = """
window, window.background {
    background-color: rgba(254, 228, 255, 0.97);
    border: none;
    border-radius: 0px;
    box-shadow: none;
    font-family: "Josefin Sans", "JetBrainsMono Nerd Font", sans-serif;
    color: #333933;
}

.main-container {
    padding: 24px 30px;
}

.title-banner {
    font-size: 22px;
    font-weight: bold;
    color: #bf40a1;
}

.subtitle-banner {
    font-size: 13px;
    font-weight: bold;
    color: #856d8a;
    margin-bottom: 10px;
}

.section-card {
    background-color: rgba(255, 194, 255, 0.55);
    border: 1.5px solid #e975ca;
    border-radius: 14px;
    padding: 12px 16px;
}

.section-title {
    font-size: 14px;
    font-weight: bold;
    color: #bf40a1;
    margin-bottom: 6px;
}

.key-badge {
    background-color: #322a32;
    color: #fee4ff;
    border: 1.5px solid #e975ca;
    border-radius: 999px;
    /* Offset Josefin Sans top-ascender space so text sits dead-center! */
    padding: 5px 12px 1px 12px;
    font-size: 12px;
    font-weight: bold;
}

.action-label {
    font-size: 13px;
    font-weight: 600;
    color: #333933;
    padding-bottom: 2px;
}
"""

MODIFIER_KEYS = {
    Gdk.KEY_Super_L, Gdk.KEY_Super_R,
    Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
    Gdk.KEY_Control_L, Gdk.KEY_Control_R,
    Gdk.KEY_Alt_L, Gdk.KEY_Alt_R,
    Gdk.KEY_Meta_L, Gdk.KEY_Meta_R,
    Gdk.KEY_ISO_Level3_Shift, Gdk.KEY_Print,
}

def parse_keybinds_file(filepath):
    sections = []
    current_section = None
    if not os.path.exists(filepath):
        return [("KEYBINDS", [("SUPER + SPACE", "keybinds.txt not found")])]

    with open(filepath, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("===") or "HYPRLAND KEYBINDINGS" in line or line.startswith("Main Modifier") or line.startswith("(Press"):
                continue
            if line.startswith("---") and line.endswith("---"):
                sec_name = line.strip("- ").strip()
                current_section = (sec_name, [])
                sections.append(current_section)
            else:
                parts = re.split(r'\s{2,}', line, maxsplit=1)
                if len(parts) == 2:
                    if current_section is None:
                        current_section = ("GENERAL", [])
                        sections.append(current_section)
                    current_section[1].append((parts[0].strip(), parts[1].strip()))
    return sections

class HelpGuideApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.marshmellow.helpguide")

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        win = Gtk.ApplicationWindow(application=self, title="Hyprland Keybinds")
        win.set_decorated(False)
        win.set_resizable(False)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self.on_key_pressed)
        win.add_controller(key_ctrl)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.add_css_class("main-container")
        win.set_child(outer)

        title = Gtk.Label(label="🌸  Marshmellow Keybindings Guide")
        title.add_css_class("title-banner")
        outer.append(title)

        sub = Gtk.Label(label="SUPER = Windows Key   •   Press any key to close")
        sub.add_css_class("subtitle-banner")
        outer.append(sub)

        sections = parse_keybinds_file(os.path.expanduser("~/.config/hypr/keybinds.txt"))

        columns_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        columns_box.set_halign(Gtk.Align.CENTER)
        outer.append(columns_box)

        col_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        col_right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        columns_box.append(col_left)
        columns_box.append(col_right)

        half = (len(sections) + 1) // 2
        for idx, (sec_name, items) in enumerate(sections):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            card.add_css_class("section-card")

            hdr = Gtk.Label(label=f"✦  {sec_name}", xalign=0)
            hdr.add_css_class("section-title")
            card.append(hdr)

            for key_str, desc_str in items:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row.set_valign(Gtk.Align.CENTER)

                badge = Gtk.Label(label=key_str)
                badge.add_css_class("key-badge")
                badge.set_valign(Gtk.Align.CENTER)

                desc = Gtk.Label(label=desc_str, xalign=0)
                desc.add_css_class("action-label")
                desc.set_valign(Gtk.Align.CENTER)
                desc.set_hexpand(True)

                row.append(badge)
                row.append(desc)
                card.append(row)

            if idx < half:
                col_left.append(card)
            else:
                col_right.append(card)

        win.present()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval in MODIFIER_KEYS:
            return False
        # Ignore if Super is held down (e.g. taking a screenshot with SUPER + P)
        if state & Gdk.ModifierType.SUPER_MASK:
            return False
        self.quit()
        return True

if __name__ == "__main__":
    res = subprocess.run(["pgrep", "-f", "help-guide.py"], capture_output=True, text=True)
    pids = [p for p in res.stdout.split() if int(p) != subprocess.os.getpid()]
    if pids:
        for p in pids:
            subprocess.run(["kill", p])
        sys.exit(0)

    app = HelpGuideApp()
    app.run(None)
