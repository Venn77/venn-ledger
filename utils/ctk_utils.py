import sys
import customtkinter as ctk
import tkinter as tk
from typing import Optional


def create_ellipsis_label(container, text, width, font, color="white", height=24):
    """
    Create a bounded frame with dynamic text ellipsis.
    'container' is the parent widget holding the fixed-width frame.
    """
    frame = ctk.CTkFrame(container, fg_color="transparent", width=width, height=height)
    frame.pack_propagate(False)

    lbl = ctk.CTkLabel(frame, text=text, anchor="w", font=font, text_color=color)
    lbl.place(relx=0, rely=0.5, relwidth=1.0, anchor="w")

    apply_dynamic_ellipsis(frame, lbl, text)
    return frame, lbl

def apply_dynamic_ellipsis(container_frame, label_widget, full_text):
    """
    Binds a resize listener to the container_frame to dynamically truncate
    the label_widget's text with an ellipsis when it exceeds the frame's width.
    Automatically detects the widget's font for accurate cross-platform scaling.
    """
    if not full_text:
        return

    font_config = label_widget.cget("font")
    font_family = "JetBrains Mono"
    font_size = 11
    font_weight = "normal"

    if isinstance(font_config, tuple):
        if len(font_config) >= 1: font_family = font_config[0]
        if len(font_config) >= 2: font_size = font_config[1]
        if len(font_config) >= 3: font_weight = font_config[2]

    elif isinstance(font_config, ctk.CTkFont):
        font_family = font_config.cget("family")
        font_size = font_config.cget("size")
        font_weight = font_config.cget("weight")

    font_metric = ctk.CTkFont(family=font_family, size=font_size, weight=font_weight)

    def _resize_text(event):
        frame_w = event.width
        if frame_w < 10:
            return

        full_width = font_metric.measure(full_text)

        if full_width <= frame_w:
            label_widget.configure(text=full_text)
        else:
            avg_char_w = full_width / len(full_text)
            max_chars = int(frame_w / avg_char_w)

            slice_len = max(0, max_chars - 3)
            label_widget.configure(text=full_text[:slice_len] + "...")

    container_frame.bind("<Configure>", _resize_text, add="+")

def calculate_dialog_geometry(widget, width, height):
    """
    Calculates X anchored to the reference widget, and Y anchored to the mouse pointer.
    Includes a safety clamp just in case the window is pushed against a screen edge.
    """
    widget.update_idletasks()

    x = widget.winfo_rootx() + (widget.winfo_width() // 2) - (width // 2)

    mouse_y = widget.winfo_pointery()
    y = mouse_y - (height // 2)

    screen_h = widget.winfo_screenheight()
    if y < 40:
        y = 40
    elif y + height > screen_h - 40:
        y = screen_h - height - 40

    return f"{width}x{height}+{x}+{y}"

def apply_placeholder(entry_widget, placeholder_text, normal_color="white", placeholder_color="gray"):
    """Attaches robust placeholder behavior to a CTk widget."""
    entry_widget._placeholder = placeholder_text
    entry_widget._normal_color = normal_color
    entry_widget._placeholder_color = placeholder_color

    if not getattr(entry_widget, "_placeholder_bound", False):
        def on_focus_in(_event):
            # noinspection PyProtectedMember
            if entry_widget.get() == entry_widget._placeholder:
                entry_widget.delete(0, 'end')
                # noinspection PyProtectedMember
                entry_widget.configure(text_color=entry_widget._normal_color)

        def on_focus_out(_event):
            if entry_widget.get().strip() == "":
                entry_widget.delete(0, 'end')
                # noinspection PyProtectedMember
                entry_widget.insert(0, entry_widget._placeholder)
                # noinspection PyProtectedMember
                entry_widget.configure(text_color=entry_widget._placeholder_color)

        entry_widget.bind("<FocusIn>", on_focus_in, add="+")
        entry_widget.bind("<FocusOut>", on_focus_out, add="+")
        entry_widget._placeholder_bound = True

    current_text = entry_widget.get().strip()
    # noinspection PyProtectedMember
    if not current_text or current_text == entry_widget._placeholder:
        entry_widget.delete(0, 'end')
        # noinspection PyProtectedMember
        entry_widget.insert(0, entry_widget._placeholder)
        # noinspection PyProtectedMember
        entry_widget.configure(text_color=entry_widget._placeholder_color)
    else:
        # noinspection PyProtectedMember
        entry_widget.configure(text_color=entry_widget._normal_color)

def apply_linux_emoji_vaccine(app_root):
    """
    An impenetrable global shield against libXft / colored emoji Segfaults on Linux.
    Intercepts and sanitizes text at the lowest Tkinter level before it can crash X11.
    """
    if sys.platform == "win32":
        return

    def sanitize_string(text):
        if not isinstance(text, str):
            return text
        return "".join(c if ord(c) <= 0xFFFF else " " for c in text)

    original_set = tk.StringVar.set

    def safe_set(self, value):
        original_set(self, sanitize_string(value))

    tk.StringVar.set = safe_set

    original_entry_insert = tk.Entry.insert

    def safe_entry_insert(self, index, string):
        original_entry_insert(self, index, sanitize_string(string))

    tk.Entry.insert = safe_entry_insert

    original_text_insert = tk.Text.insert

    def safe_text_insert(self, index, chars, *args):
        original_text_insert(self, index, sanitize_string(chars), *args)

    tk.Text.insert = safe_text_insert

    def block_emoji_keys(event):
        if event.char and len(event.char) > 0:
            if ord(event.char[0]) > 0xFFFF:
                try:
                    event.widget.insert(tk.INSERT, " ")
                except (tk.TclError, AttributeError):
                    pass
                return "break"
        return None

    app_root.bind_all("<KeyPress>", block_emoji_keys, add="+")

    def safe_paste(event):
        try:
            widget = event.widget
            clean_text = sanitize_string(widget.clipboard_get())

            if isinstance(widget, tk.Entry):
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert(tk.INSERT, clean_text)
                return "break"

            elif isinstance(widget, tk.Text):
                try:
                    widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert(tk.INSERT, clean_text)
                return "break"
        except (tk.TclError, AttributeError):
            pass

    app_root.bind_class("Entry", "<<Paste>>", safe_paste)
    app_root.bind_class("Text", "<<Paste>>", safe_paste)

def apply_linux_ui_vaccine():
    """
    Globally patches CustomTkinter rendering artifacts on Linux/SteamOS.
    Sets corner radii to 0 to prevent the 'bleeding pixel' canvas bug
    when using fractional scaling on external monitors.
    """
    if sys.platform not in ["win32", "darwin"]:
        widgets_to_flatten = [
            "CTkButton", "CTkFrame", "CTkEntry",
            "CTkOptionMenu", "CTkComboBox", "CTkCheckBox",
            "CTkProgressBar", "CTkSlider", "CTkTextbox"
        ]

        for widget in widgets_to_flatten:
            if widget in ctk.ThemeManager.theme:
                ctk.ThemeManager.theme[widget]["corner_radius"] = 0

def patch_linux_scrolling(widget_container):
    """
    Recursively fixes the Linux X11 scroll deadlock on any CTkScrollableFrame
    by binding <Button-4> (up) and <Button-5> (down) to every child widget.
    """
    if sys.platform in ["win32", "darwin"]:
        return

    def _find_canvas(w) -> Optional[tk.Canvas]:
        curr = w
        while curr:
            if hasattr(curr, '_parent_canvas'):
                # noinspection PyProtectedMember
                return curr._parent_canvas
            curr = getattr(curr, 'master', None)
        return None

    target_canvas = _find_canvas(widget_container)

    if target_canvas is None or not hasattr(target_canvas, 'yview_scroll'):
        return

    canvas: tk.Canvas = target_canvas

    def _on_mousewheel(event):
        current_yview = canvas.yview()
        if event.num == 4:
            if current_yview[0] > 0.0:
                canvas.yview_scroll(-1, "units")

        elif event.num == 5:
            if current_yview[1] < 1.0:
                canvas.yview_scroll(1, "units")

    def _bind_recursive(w):
        w.bind("<Button-4>", _on_mousewheel, add="+")
        w.bind("<Button-5>", _on_mousewheel, add="+")
        for child in w.winfo_children():
            _bind_recursive(child)

    _bind_recursive(widget_container)

def install_canvas_engine_patch():
    """
    Engine-level monkeypatch for Tkinter Canvas.
    Interceptions to scrollregion globally prevent negative-Y overscroll
    whenever content height is smaller than the physical window viewport.
    """
    orig_configure = tk.Canvas.configure

    def patched_configure(self, cnf=None, **kw):
        options = dict(cnf) if cnf else {}
        options.update(kw)

        if 'scrollregion' in options:
            region = options['scrollregion']
            if region:
                if isinstance(region, (list, tuple)) and len(region) == 4:
                    try:
                        x1, y1, x2, y2 = map(float, region)
                        canvas_height = self.winfo_height()
                        if canvas_height > 1 and (y2 - y1) < canvas_height:
                            y2 = y1 + canvas_height
                            options['scrollregion'] = (x1, y1, x2, y2)
                    except (ValueError, TypeError):
                        pass
                elif isinstance(region, str) and region.strip():
                    parts = region.strip().split()
                    if len(parts) == 4:
                        try:
                            x1, y1, x2, y2 = map(float, parts)
                            canvas_height = self.winfo_height()
                            if canvas_height > 1 and (y2 - y1) < canvas_height:
                                y2 = y1 + canvas_height
                                options['scrollregion'] = f"{x1} {y1} {x2} {y2}"
                        except ValueError:
                            pass

        return orig_configure(self, cnf, **options)

    tk.Canvas.configure = patched_configure
    tk.Canvas.config = patched_configure


