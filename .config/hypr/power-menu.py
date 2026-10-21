#!/usr/bin/env python3
import gi
import subprocess
import sys

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk

CSS = """
window {
    background-color: rgba(50, 42, 50, 0.88);
    border: none;
    border-radius: 0px;
}

.main-box {
    padding: 28px 34px;
}

.title-label {
    font-family: "Josefin Sans", sans-serif;
    font-size: 20px;
    font-weight: bold;
    color: #fee4ff;
    margin-bottom: 14px;
}

button.power-pill {
    background-image: none;
    background-color: rgba(254, 228, 255, 0.90);
    color: #322a32;
    border: none;
    border-radius: 999px;
    min-width: 130px;
    min-height: 170px;
    margin: 10px;
    padding: 16px;
    transition: all 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

button.power-pill:hover,
button.power-pill:focus {
    background-color: #e975ca;
    border-color: #fee4ff;
    color: #fee4ff;
    transform: scale(1.08);
    outline: none;
}

.pill-icon {
    font-family: "JetBrainsMono Nerd Font", monospace;
    font-size: 44px;
    margin-bottom: 10px;
}

.pill-text {
    font-family: "Josefin Sans", sans-serif;
    font-size: 16px;
    font-weight: bold;
}
"""

ACTIONS = [
    ("", "Shutdown", "systemctl poweroff"),
    ("󰜉", "Reboot",   "systemctl reboot"),
    ("󰤄", "Suspend",  "systemctl suspend"),
    ("󰍃", "Logout",   "hyprctl dispatch exit"),
]

class PowerMenuApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.marshmellow.powermenu")

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        win = Gtk.ApplicationWindow(application=self, title="Marshmellow Power Menu")
        win.set_decorated(False)
        win.set_resizable(False)

        # Close on Escape key
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self.on_key_pressed)
        win.add_controller(key_ctrl)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.add_css_class("main-box")
        win.set_child(outer)

        hdr = Gtk.Label(label="🌸  Power Menu  (Esc to cancel)")
        hdr.add_css_class("title-label")
        outer.append(hdr)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_halign(Gtk.Align.CENTER)
        outer.append(row)

        for icon, label, cmd in ACTIONS:
            btn = Gtk.Button()
            btn.add_css_class("power-pill")

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_valign(Gtk.Align.CENTER)
            box.set_halign(Gtk.Align.CENTER)

            lbl_icon = Gtk.Label(label=icon)
            lbl_icon.add_css_class("pill-icon")

            lbl_text = Gtk.Label(label=label)
            lbl_text.add_css_class("pill-text")

            box.append(lbl_icon)
            box.append(lbl_text)
            btn.set_child(box)

            btn.connect("clicked", self.on_action, cmd)
            row.append(btn)

        win.present()

    def on_action(self, btn, cmd):
        subprocess.Popen(cmd, shell=True)
        self.quit()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

if __name__ == "__main__":
    # Toggle behavior: if already open, close it
    res = subprocess.run(["pgrep", "-f", "power-menu.py"], capture_output=True, text=True)
    pids = [p for p in res.stdout.split() if int(p) != subprocess.os.getpid()]
    if pids:
        for p in pids:
            subprocess.run(["kill", p])
        sys.exit(0)

    app = PowerMenuApp()
    app.run(None)
