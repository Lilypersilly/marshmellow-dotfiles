use gdk::prelude::*;
use gtk::prelude::*;
use std::fs;
use std::path::PathBuf;
use regex::Regex;
use std::cell::{Cell, RefCell};
use std::process::Command;
use std::rc::Rc;
use std::time::Duration;
use sysinfo::{Pid, ProcessRefreshKind, RefreshKind, System};

const CSS: &[u8] = br#"
window, window:backdrop, window.background {
background-color: rgba(254, 228, 255, 0.35);
background-image: none;
border: none;
border-radius: 0px;
font-family: "Josefin Sans", "JetBrainsMono Nerd Font", sans-serif;
color: #333933;
}
.header {
font-size: 15px;
font-weight: bold;
color: #bf40a1;
margin-top: 6px;
margin-bottom: 4px;
}
scale trough {
background-color: #322a32;
border: none;
border-radius: 8px;
min-height: 10px;
}
scale highlight {
background-color: #e975ca;
border: none;
border-radius: 8px;
}
scale slider {
background-color: #ffc2ff;
border: 2px solid #bf40a1;
border-radius: 50%;
min-width: 18px;
min-height: 18px;
margin: -5px;
}
button.device-btn {
background-image: none;
background-color: rgba(255, 194, 255, 0.45);
color: #333933;
border: 1px solid #f8d4ff;
border-radius: 10px;
padding: 8px 12px;
font-size: 13px;
font-weight: 600;
}
button.device-btn:hover {
background-color: #ef96d9;
border-color: #e975ca;
}
button.device-active {
background-image: none;
background-color: #322a32;
color: #fee4ff;
border: 2px solid #e975ca;
border-radius: 10px;
padding: 8px 12px;
font-size: 13px;
font-weight: bold;
}
"#;

#[derive(Clone, Debug)]
struct Device {
    id: String,
    name: String,
    is_active: bool,
}

fn parse_wpctl() -> (Vec<Device>, Vec<Device>) {
    let output = Command::new("wpctl")
    .arg("status")
    .output()
    .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
    .unwrap_or_default();

    let mut sinks = Vec::new();
    let mut sources = Vec::new();
    let mut current_mode = None;

    let dev_re = Regex::new(r"(\d+)\.\s+(.+?)(?:\s+\[vol:|$)").unwrap();

    for line in output.lines() {
        if line.contains("Sinks:") {
            current_mode = Some("sinks");
            continue;
        } else if line.contains("Sources:") {
            current_mode = Some("sources");
            continue;
        } else if [
            "Sink endpoints:",
            "Source endpoints:",
            "Filters:",
            "Streams:",
            "Video",
        ]
        .iter()
        .any(|header| line.contains(header))
        {
            current_mode = None;
            continue;
        }

        if let Some(mode) = current_mode {
            let active = line.contains('*');
            if let Some(caps) = dev_re.captures(line) {
                let id = caps[1].to_string();
                let name = caps[2].trim().to_string();
                let item = Device {
                    id,
                    name,
                    is_active: active,
                };

                if mode == "sinks" {
                    sinks.push(item);
                } else if mode == "sources" {
                    sources.push(item);
                }
            }
        }
    }

    (sinks, sources)
}

fn get_volume() -> (f64, bool) {
    let output = Command::new("wpctl")
    .args(["get-volume", "@DEFAULT_AUDIO_SINK@"])
    .output()
    .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
    .unwrap_or_default();

    let re = Regex::new(r"([0-9.]+)").unwrap();
    let vol = re
    .captures(&output)
    .and_then(|caps| caps[1].parse::<f64>().ok())
    .map(|v| v * 100.0)
    .unwrap_or(50.0);

    let muted = output.contains("MUTED");
    (vol, muted)
}

fn build_ui(vbox: &gtk::Box) {
    for child in vbox.children() {
        vbox.remove(&child);
    }

    let (vol, muted) = get_volume();
    let (sinks, sources) = parse_wpctl();

    let vol_text = if muted {
        "󰝟   Muted".to_string()
    } else {
        format!("   Output Volume ({}%)", vol.round() as i32)
    };
    let lbl_vol = gtk::Label::new(Some(&vol_text));
    lbl_vol.set_xalign(0.0);
    lbl_vol.style_context().add_class("header");
    vbox.pack_start(&lbl_vol, false, false, 0);

    let scale = gtk::Scale::with_range(gtk::Orientation::Horizontal, 0.0, 100.0, 1.0);
    scale.set_draw_value(false);
    scale.set_value(vol);

    {
        let lbl_vol_clone = lbl_vol.clone();
        scale.connect_value_changed(move |s| {
            let val = s.value().round() as i32;
            let _ = Command::new("wpctl")
            .args(["set-volume", "@DEFAULT_AUDIO_SINK@", &format!("{val}%")])
            .spawn();
            lbl_vol_clone.set_text(&format!("   Output Volume ({val}%)"));
        });
    }
    vbox.pack_start(&scale, false, false, 4);

    let lbl_out = gtk::Label::new(Some("󰋋   Output Device"));
    lbl_out.set_xalign(0.0);
    lbl_out.style_context().add_class("header");
    vbox.pack_start(&lbl_out, false, false, 0);

    for dev in sinks {
        let prefix = if dev.is_active { "●  " } else { "○  " };
        let btn = gtk::Button::with_label(&format!("{}{}", prefix, dev.name));
        if let Some(child) = btn.child().and_downcast::<gtk::Label>() {
            child.set_xalign(0.0);
        }
        btn.style_context().add_class(if dev.is_active {
            "device-active"
        } else {
            "device-btn"
        });

        let vbox_clone = vbox.clone();
        let dev_id = dev.id.clone();
        btn.connect_clicked(move |_| {
            let _ = Command::new("wpctl")
            .args(["set-default", &dev_id])
            .status();
            build_ui(&vbox_clone);
        });
        vbox.pack_start(&btn, false, false, 0);
    }

    let lbl_in = gtk::Label::new(Some("   Input Device (Mic)"));
    lbl_in.set_xalign(0.0);
    lbl_in.style_context().add_class("header");
    vbox.pack_start(&lbl_in, false, false, 0);

    for dev in sources {
        let prefix = if dev.is_active { "●  " } else { "○  " };
        let btn = gtk::Button::with_label(&format!("{}{}", prefix, dev.name));
        if let Some(child) = btn.child().and_downcast::<gtk::Label>() {
            child.set_xalign(0.0);
        }
        btn.style_context().add_class(if dev.is_active {
            "device-active"
        } else {
            "device-btn"
        });

        let vbox_clone = vbox.clone();
        let dev_id = dev.id.clone();
        btn.connect_clicked(move |_| {
            let _ = Command::new("wpctl")
            .args(["set-default", &dev_id])
            .status();
            build_ui(&vbox_clone);
        });
        vbox.pack_start(&btn, false, false, 0);
    }

    vbox.show_all();
}

fn get_pid_file() -> PathBuf {
    let runtime_dir = std::env::var("XDG_RUNTIME_DIR").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(runtime_dir).join("audio-popover.pid")
}

fn toggle_single_instance() {
    let pid_file = get_pid_file();

    if pid_file.exists() {
        if let Ok(content) = fs::read_to_string(&pid_file) {
            if let Ok(old_pid) = content.trim().parse::<i32>() {
                // Check if the process is actually running (kill -0)
                let is_running = Command::new("kill")
                .args(["-0", &old_pid.to_string()])
                .status()
                .map(|s| s.success())
                .unwrap_or(false);

                if is_running {
                    // It is currently open: kill it to close it, delete the PID file, and exit
                    let _ = Command::new("kill").arg(old_pid.to_string()).status();
                    let _ = fs::remove_file(&pid_file);
                    std::process::exit(0);
                }
            }
        }
        // Stale PID file (crashed before), clean it up
        let _ = fs::remove_file(&pid_file);
    }

    // Save our current PID so the next click can toggle/kill us
    let my_pid = std::process::id();
    let _ = fs::write(&pid_file, my_pid.to_string());
}

fn cleanup_pid_file() {
    let pid_file = get_pid_file();
    let _ = fs::remove_file(pid_file);
}

fn main() {
    toggle_single_instance();

    if gtk::init().is_err() {
        eprintln!("Failed to initialize GTK.");
        cleanup_pid_file();
        std::process::exit(1);
    }

    let window = gtk::Window::new(gtk::WindowType::Toplevel);
    window.set_title("Audio Control");
    window.set_decorated(false);
    window.set_keep_above(true);
    window.set_default_size(340, -1);

    // Alpha channel / transparent visual support
    if let Some(screen) = gtk::prelude::GtkWindowExt::screen(&window) {
        if screen.is_composited() {
            if let Some(visual) = screen.rgba_visual() {
                window.set_visual(Some(&visual));
            }
        }

        let provider = gtk::CssProvider::new();
        let _ = provider.load_from_data(CSS);
        gtk::StyleContext::add_provider_for_screen(
            &screen,
            &provider,
            gtk::STYLE_PROVIDER_PRIORITY_APPLICATION,
        );
    }

    let vbox = gtk::Box::new(gtk::Orientation::Vertical, 8);
    vbox.set_margin_top(14);
    vbox.set_margin_bottom(14);
    vbox.set_margin_start(16);
    vbox.set_margin_end(16);
    window.add(&vbox);

    let close_timer: Rc<RefCell<Option<glib::SourceId>>> = Rc::new(RefCell::new(None));
    let has_entered = Rc::new(Cell::new(false));

    window.add_events(gdk::EventMask::ENTER_NOTIFY_MASK | gdk::EventMask::LEAVE_NOTIFY_MASK);

    let start_close_timer = {
        let close_timer = close_timer.clone();
        move || {
            let mut timer = close_timer.borrow_mut();
            if timer.is_none() {
                *timer = Some(glib::timeout_add_local(Duration::from_millis(500), || {
                    gtk::main_quit();
                    glib::ControlFlow::Break
                }));
            }
        }
    };

    let cancel_close_timer = {
        let close_timer = close_timer.clone();
        move || {
            let mut timer = close_timer.borrow_mut();
            if let Some(source_id) = timer.take() {
                source_id.remove();
            }
        }
    };

    // Arm close only after initial 2.5 seconds
    {
        let has_entered = has_entered.clone();
        glib::timeout_add_local(Duration::from_millis(2500), move || {
            has_entered.set(true);
            glib::ControlFlow::Break
        });
    }

    // Pointer Enter
    {
        let has_entered = has_entered.clone();
        let cancel_close_timer = cancel_close_timer.clone();
        window.connect_enter_notify_event(move |_, _| {
            has_entered.set(true);
            cancel_close_timer();
            glib::Propagation::Proceed
        });
    }

    // Pointer Leave
    {
        let has_entered = has_entered.clone();
        let start_close_timer = start_close_timer.clone();
        window.connect_leave_notify_event(move |_, event| {
            if event.detail() == gdk::NotifyType::Inferior {
                return glib::Propagation::Proceed;
            }
            if has_entered.get() {
                start_close_timer();
            }
            glib::Propagation::Proceed
        });
    }

    // Focus Out
    {
        let has_entered = has_entered.clone();
        let start_close_timer = start_close_timer.clone();
        window.connect_focus_out_event(move |_, _| {
            if has_entered.get() {
                start_close_timer();
            }
            glib::Propagation::Proceed
        });
    }

    // Key press (Escape to exit)
    window.connect_key_press_event(|_, event| {
        if event.keyval() == gdk::keys::constants::Escape {
            gtk::main_quit();
        }
        glib::Propagation::Proceed
    });

    // When the window closes / gets destroyed, clean up the PID file:
    window.connect_destroy(|_| {
        cleanup_pid_file();
        gtk::main_quit();
    });

    // Build UI immediately, then show
    build_ui(&vbox);
    window.show_all();

    gtk::main();
    cleanup_pid_file();
}
