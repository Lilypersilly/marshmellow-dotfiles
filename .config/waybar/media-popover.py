#!/usr/bin/env python3
import gi
import subprocess
import sys
import os
import threading
import urllib.request
from urllib.parse import unquote

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango, GLib

CSS = b"""
window, window:backdrop, window.background {
    font-family: "Josefin Sans", "JetBrainsMono Nerd Font", sans-serif;
    background-color: rgba(254, 228, 255, 0.35);
    background-image: none;
    border: none;
    border-radius: 0;
}
.header { font-size: 15px; font-weight: bold; color: #bf40a1; }
.title { font-size: 16px; font-weight: bold; color: #322a32; }
.artist { font-size: 13px; color: #856d8a; font-weight: bold; }
button.ctrl-btn {
    background-image: none;
    background-color: rgba(255, 194, 255, 0.8);
    color: #322a32;
    border: 2px solid #e975ca;
    border-radius: 999px;
    min-width: 46px;
    min-height: 46px;
    font-size: 20px;
    margin: 4px;
}
button.ctrl-btn:hover {
    background-color: #ef96d9;
    border-color: #bf40a1;
}
"""

class MediaDropdown(Gtk.Window):
    def __init__(self):
        super().__init__(title="Media Control")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_default_size(320, -1)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.connect("key-press-event", self.on_key)

        self.current_title = None
        self.current_artist = None
        self.current_art_url = None
        self.current_status = None

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_margin_top(16)
        self.main_box.set_margin_bottom(16)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)
        self.add(self.main_box)

        self.build_ui()
        self.refresh_metadata()
        # Check for track/art changes every 400ms while the popup is open
        GLib.timeout_add(400, self.refresh_metadata)

    def build_ui(self):
        # --- HEADER ---
        hdr_lbl = Gtk.Label(label="  Now Playing", xalign=0)
        hdr_lbl.get_style_context().add_class("header")
        self.main_box.pack_start(hdr_lbl, False, False, 0)

        # --- HORIZONTAL BOX FOR ART + TEXT ---
        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.main_box.pack_start(info_box, False, False, 6)

        # --- ALBUM ART CONTAINER ---
        self.art_holder = Gtk.Box()
        self.art_holder.set_size_request(80, 80)
        info_box.pack_start(self.art_holder, False, False, 0)

        # --- TITLE & ARTIST ---
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_box.set_valign(Gtk.Align.CENTER)
        info_box.pack_start(text_box, True, True, 0)

        self.lbl_title = Gtk.Label(label="Loading...", xalign=0)
        self.lbl_title.get_style_context().add_class("title")
        self.lbl_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_title.set_max_width_chars(20)
        text_box.pack_start(self.lbl_title, False, False, 0)

        self.lbl_artist = Gtk.Label(label="", xalign=0)
        self.lbl_artist.get_style_context().add_class("artist")
        self.lbl_artist.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_artist.set_max_width_chars(20)
        text_box.pack_start(self.lbl_artist, False, False, 0)

        # --- CONTROLS ---
        ctrl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        ctrl_box.set_halign(Gtk.Align.CENTER)
        self.main_box.pack_start(ctrl_box, False, False, 6)

        btn_prev = Gtk.Button(label="󰒮")
        btn_prev.get_style_context().add_class("ctrl-btn")
        btn_prev.connect("clicked", lambda x: subprocess.Popen(["playerctl", "previous"]))
        ctrl_box.pack_start(btn_prev, False, False, 0)

        self.btn_play = Gtk.Button(label="󰐊")
        self.btn_play.get_style_context().add_class("ctrl-btn")
        self.btn_play.connect("clicked", self.on_play_click)
        ctrl_box.pack_start(self.btn_play, False, False, 0)

        btn_next = Gtk.Button(label="󰒭")
        btn_next.get_style_context().add_class("ctrl-btn")
        btn_next.connect("clicked", lambda x: subprocess.Popen(["playerctl", "next"]))
        ctrl_box.pack_start(btn_next, False, False, 0)

        self.show_all()

    def on_play_click(self, btn):
        subprocess.Popen(["playerctl", "play-pause"])
        btn.set_label("󰐊" if btn.get_label() == "󰏤" else "󰏤")

    def refresh_metadata(self):
        try:
            out = subprocess.check_output(
                ['playerctl', 'metadata', '--format', '{{title}}|||{{artist}}|||{{mpris:artUrl}}|||{{status}}'],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            title, artist, art_url, status = out.split('|||')
        except Exception:
            title, artist, art_url, status = "No Media Playing", "Play something first!", "", "Stopped"

        if title != self.current_title or artist != self.current_artist:
            self.current_title = title
            self.current_artist = artist
            self.lbl_title.set_text(title)
            self.lbl_artist.set_text(artist)

        if status != self.current_status:
            self.current_status = status
            self.btn_play.set_label("󰏤" if status == "Playing" else "󰐊")

        if art_url != self.current_art_url:
            self.current_art_url = art_url
            threading.Thread(target=self.fetch_art, args=(art_url,), daemon=True).start()

        return True

    def fetch_art(self, art_url):
        art_path = None
        if art_url.startswith("file://"):
            art_path = unquote(art_url[7:])
        elif art_url.startswith("http"):
            try:
                req = urllib.request.Request(art_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=2.0) as res:
                    art_path = "/tmp/waybar_art.jpg"
                    with open(art_path, "wb") as f:
                        f.write(res.read())
            except Exception:
                pass
        GLib.idle_add(self.update_art_widget, art_path, art_url)

    def update_art_widget(self, art_path, requested_url):
        if requested_url != self.current_art_url:
            return False
        for child in self.art_holder.get_children():
            self.art_holder.remove(child)
        widget = None
        if art_path and os.path.exists(art_path):
            try:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(art_path, 80, 80, True)
                widget = Gtk.Image.new_from_pixbuf(pix)
            except Exception:
                pass
        if widget is None:
            widget = Gtk.Label(label="")
            widget.set_size_request(80, 80)
        self.art_holder.pack_start(widget, True, True, 0)
        self.art_holder.show_all()
        return False

    def on_key(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()

if __name__ == "__main__":
    res = subprocess.run(["pgrep", "-f", "media-popover.py"], capture_output=True, text=True)
    pids = [p for p in res.stdout.split() if int(p) != subprocess.os.getpid()]
    if pids:
        for p in pids:
            subprocess.run(["kill", p])
        sys.exit(0)
    win = MediaDropdown()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
