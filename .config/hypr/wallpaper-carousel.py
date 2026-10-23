#!/usr/bin/env python3
import cairo
import gi
import hashlib
import math
import os
import subprocess
import sys

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GdkPixbuf

WALL_DIR   = os.path.expanduser("~/Pictures/Wallpapers")
CACHE_DIR  = os.path.expanduser("~/.cache/marshmellow-wave-thumbs")
STATE_FILE = os.path.expanduser("~/.config/hypr/.current_wallpaper")
VALID_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

WIN_W, WIN_H = 1800, 480
VISIBLE_HALF = 7  # 15 vertical slices total
CORNER_RADIUS = 16.0

CSS = """
window, window.background {
    background-color: transparent;
    background-image: none;
    border: none;
    box-shadow: none;
}
"""

def rounded_rect(cr, x, y, w, h, r):
    r = min(r, w / 2.0, h / 2.0)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()

def get_vertical_pair(img_path):
    """Return the paired image in ~/Pictures/Wallpapers/vertical/ if one exists."""
    vert_dir = os.path.join(WALL_DIR, "vertical")
    base_name = os.path.basename(img_path)
    stem, _ = os.path.splitext(base_name)

    # 1. Exact filename match
    exact = os.path.join(vert_dir, base_name)
    if os.path.exists(exact):
        return exact

    # 2. Match same name even if saved with a different extension (.png vs .jpg)
    for ext in VALID_EXTS:
        alt = os.path.join(vert_dir, stem + ext)
        if os.path.exists(alt):
            return alt

    return img_path

def load_cached_surface(img_path, target_w=160, target_h=440):
    os.makedirs(CACHE_DIR, exist_ok=True)
    # Use the vertical crop for the tall carousel slice preview if it exists!
    source_img = get_vertical_pair(img_path)
    mtime = os.path.getmtime(source_img)
    h = hashlib.md5(f"{source_img}-{mtime}-{target_w}x{target_h}".encode()).hexdigest()
    thumb_path = os.path.join(CACHE_DIR, f"{h}.png")

    if not os.path.exists(thumb_path):
        pix = GdkPixbuf.Pixbuf.new_from_file(source_img)
        pw, ph = pix.get_width(), pix.get_height()
        scale = max(target_w / pw, target_h / ph)
        sw, sh = max(target_w, int(pw * scale)), max(target_h, int(ph * scale))
        scaled = pix.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
        ox, oy = max(0, (sw - target_w) // 2), max(0, (sh - target_h) // 2)
        cropped = scaled.new_subpixbuf(ox, oy, target_w, target_h)
        cropped.savev(thumb_path, "png", [], [])

    # Load directly into a native Cairo ImageSurface ONCE at startup for 144Hz rendering!
    surf = cairo.ImageSurface.create_from_png(thumb_path)
    return surf, surf.get_width(), surf.get_height()

class WaveCarousel(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.marshmellow.wallcarousel")
        self.files = []
        self.surfaces = []
        self.scroll_pos = 0.0
        self.target_pos = 0.0
        self.last_frame_time = None
        self.slice_rects = []

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        os.makedirs(WALL_DIR, exist_ok=True)
        self.files = sorted([
            os.path.join(WALL_DIR, f) for f in os.listdir(WALL_DIR)
            if f.lower().endswith(VALID_EXTS)
        ])

        for p in self.files:
            try:
                self.surfaces.append(load_cached_surface(p))
            except Exception:
                pass

        win = Gtk.ApplicationWindow(application=self, title="Marshmellow Wallpapers")
        win.set_decorated(False)
        win.set_default_size(WIN_W, WIN_H)

        self.area = Gtk.DrawingArea()
        self.area.set_content_width(WIN_W)
        self.area.set_content_height(WIN_H)
        self.area.set_draw_func(self.on_draw)
        self.area.add_tick_callback(self.on_tick)
        win.set_child(self.area)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self.on_key)
        win.add_controller(key_ctrl)

        scroll_ctrl = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll_ctrl.connect("scroll", self.on_scroll)
        self.area.add_controller(scroll_ctrl)

        click_ctrl = Gtk.GestureClick()
        click_ctrl.connect("pressed", self.on_click)
        self.area.add_controller(click_ctrl)

        win.present()

    def on_tick(self, widget, frame_clock):
        now = frame_clock.get_frame_time()
        if self.last_frame_time is None:
            dt = 1.0 / 144.0
        else:
            dt = max(0.001, min(0.05, (now - self.last_frame_time) / 1_000_000.0))
        self.last_frame_time = now

        diff = self.target_pos - self.scroll_pos
        if abs(diff) > 0.001:
            # Frame-rate independent exponential smoothing for 144Hz
            alpha = 1.0 - math.exp(-18.0 * dt)
            self.scroll_pos += diff * alpha
            widget.queue_draw()
        else:
            self.scroll_pos = self.target_pos
        return True

    def get_dims(self, dist):
        w = max(54.0, 120.0 - dist * 8.5)
        h = max(100.0, 440.0 - dist * 46.0)
        return w, h

    def on_draw(self, area, cr, width, height):
        self.slice_rects.clear()
        n = len(self.surfaces)
        if n == 0:
            return

        base_idx = int(math.floor(self.scroll_pos))
        frac = self.scroll_pos - base_idx
        gap = 12.0
        center_x = width / 2.0

        for offset in range(-VISIBLE_HALF - 1, VISIBLE_HALF + 2):
            rel = offset - frac
            dist = abs(rel)
            if dist > VISIBLE_HALF + 0.6:
                continue

            w, h = self.get_dims(dist)
            avg_w = (120.0 + w) / 2.0
            cx = center_x + rel * (avg_w + gap)
            x = cx - w / 2.0
            y = (height - h) / 2.0

            file_idx = (base_idx + offset) % n
            surf, pw, ph = self.surfaces[file_idx]

            cr.save()
            rounded_rect(cr, x, y, w, h, CORNER_RADIUS)
            cr.clip()

            scale = max(w / pw, h / ph)
            cr.translate(x + (w - pw * scale) / 2.0, y + (h - ph * scale) / 2.0)
            cr.scale(scale, scale)
            cr.set_source_surface(surf, 0, 0)
            cr.get_source().set_filter(cairo.Filter.BILINEAR)
            cr.paint_with_alpha(max(0.45, 1.0 - dist * 0.06))
            cr.restore()

            # Rounded border on the center active slice (#e975ca / #fee4ff)
            if dist < 0.5:
                cr.save()
                rounded_rect(cr, x + 1, y + 1, w - 2, h - 2, CORNER_RADIUS)
                cr.set_source_rgba(0.914, 0.459, 0.792, 0.95)  # Berry Pink #e975ca
                cr.set_line_width(2.5)
                cr.stroke()
                cr.restore()

            self.slice_rects.append((x, y, w, h, base_idx + offset, file_idx))

    def on_scroll(self, controller, dx, dy):
        step = 1 if (dy > 0 or dx > 0) else -1
        self.target_pos = round(self.target_pos + step)
        self.area.queue_draw()
        return True

    def on_click(self, gesture, n_press, x, y):
        for sx, sy, sw, sh, slot_idx, file_idx in self.slice_rects:
            if sx <= x <= sx + sw and sy <= y <= sy + sh:
                if abs(slot_idx - self.target_pos) > 0.5:
                    self.target_pos = float(slot_idx)
                    self.area.queue_draw()
                else:
                    self.apply_wallpaper(self.files[file_idx])
                return

    def on_key(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_l):
            self.target_pos = round(self.target_pos + 1)
            self.area.queue_draw()
            return True
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_h):
            self.target_pos = round(self.target_pos - 1)
            self.area.queue_draw()
            return True
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            if self.files:
                idx = int(round(self.target_pos)) % len(self.files)
                self.apply_wallpaper(self.files[idx])
            return True
        return False

    def apply_wallpaper(self, path):
        import json
        with open(STATE_FILE, "w") as f:
            f.write(path)
        vert_path = get_vertical_pair(path)
        try:
            mons = json.loads(subprocess.check_output(["hyprctl", "monitors", "-j"], text=True))
            cmds = ["(pgrep -x swww-daemon >/dev/null || pgrep -x awww-daemon >/dev/null || swww-daemon --format xrgb &);"]
            for m in mons:
                name = m["name"]
                is_vert = (m.get("transform", 0) in (1, 3)) or (m.get("height", 0) > m.get("width", 0))
                pos = "top-left" if is_vert else "top-right"
                target_img = vert_path if is_vert else path
                cmds.append(
                    f"swww img -o '{name}' '{target_img}' --resize crop --transition-type grow "
                    f"--transition-pos {pos} --transition-fps 144 --transition-step 200 "
                    f"--transition-bezier .25,.1,.25,1 --transition-duration 1.4 &"
                )
            subprocess.Popen(" ".join(cmds), shell=True)
        except Exception:
            subprocess.Popen(f"swww img '{path}' --resize crop --transition-type grow --transition-pos top-right --transition-fps 144", shell=True)
        self.quit()

if __name__ == "__main__":
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        WaveCarousel().apply_wallpaper(os.path.abspath(sys.argv[1]))
        sys.exit(0)

    res = subprocess.run(["pgrep", "-f", "wallpaper-carousel.py"], capture_output=True, text=True)
    pids = [p for p in res.stdout.split() if int(p) != subprocess.os.getpid()]
    if pids:
        for p in pids:
            subprocess.run(["kill", p])
        sys.exit(0)
    app = WaveCarousel()
    app.run(None)
