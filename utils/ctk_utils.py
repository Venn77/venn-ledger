import sys
import customtkinter as ctk
import tkinter as tk


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


