import customtkinter as ctk


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


