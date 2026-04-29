import customtkinter as ctk
import tkinter as tk


class ToolTip:
    def __init__(self, widget, text, delay=500, max_width=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.max_width = max_width
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self._schedule)
        self.widget.bind("<Leave>", self.hide_tip)

    def _schedule(self, _event=None):
        self.id = self.widget.after(self.delay, self.show_tip)

    def show_tip(self, _event=None):
        if self.tip_window or not self.text:
            return

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.attributes("-topmost", True)

        frame = ctk.CTkFrame(self.tip_window, fg_color="#181818", border_color="#5AC8FA", border_width=1,
                             corner_radius=6)
        frame.pack(fill="both", expand=True)

        label = ctk.CTkLabel(
            frame, text=self.text, corner_radius=0,
            fg_color="transparent", text_color="white", padx=10, pady=5,
            wraplength=self.max_width, justify="left"
        )
        label.pack()

        self.tip_window.update_idletasks()

        tip_w = self.tip_window.winfo_width()
        tip_h = self.tip_window.winfo_height()

        mouse_x = self.widget.winfo_pointerx()
        mouse_y = self.widget.winfo_pointery()

        screen_w = self.widget.winfo_screenwidth()
        screen_h = self.widget.winfo_screenheight()

        pos_x = mouse_x + 15
        pos_y = mouse_y + 10

        # SCREEN BOUNDARY CHECK (Right edge)
        if pos_x + tip_w > screen_w:
            pos_x = mouse_x - tip_w - 5  # Flip to left of cursor

        # SCREEN BOUNDARY CHECK (Bottom edge)
        if pos_y + tip_h > screen_h:
            pos_y = mouse_y - tip_h - 5  # Flip to top of cursor

        self.tip_window.wm_geometry(f"+{pos_x}+{pos_y}")

    def hide_tip(self, _event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class SearchableComboBox(ctk.CTkComboBox):
    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.all_values = kwargs.get("values", [])
        self.set(self.placeholder)

        # Bindings
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<KeyRelease>", self._on_key_release)
        self._entry.bind("<Down>", self._on_down_key)

        # Initialize Color
        self.after(300, self._check_and_set_color)

    def _dropdown_callback(self, value):
        """Overrides the internal CTk hook for dropdown selections."""
        super()._dropdown_callback(value)
        self._check_and_set_color()

    def _check_and_set_color(self, *args):
        """Sets placeholder color to gray."""
        if self.get() == self.placeholder:
            self._entry.configure(foreground="gray")
        else:
            self._entry.configure(foreground="white")

    def _on_focus_in(self, _event):
        """Clears the placeholder and sets value color."""
        if self.get() == self.placeholder:
            self.set("")
            self._entry.configure(foreground="white")

    def _on_focus_out(self, _event):
        """Sets the placeholder and its color."""
        if self.get() == "":
            self.set(self.placeholder)
            self._entry.configure(foreground="gray")

    def _on_key_release(self, event):
        """Filters the dropdown values based on user input."""
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return

        typed = self.get().lower()
        if typed == "" or typed == self.placeholder.lower():
            filtered = self.all_values
        else:
            filtered = [v for v in self.all_values if typed in v.lower()]

        self.configure(values=filtered)

    def _on_down_key(self, _event):
        """Manually opens the filtered list when the user hits the Down arrow."""
        try:
            if self.get() == self.placeholder:
                self.set("")
                self._entry.configure(foreground="white")

            self._open_dropdown_menu()
        except Exception:
            pass

    def inject_value(self, value):
        """Pre-fills data for Copy/Edit modes."""
        if value and str(value).strip() != "":
            self.set(str(value))
            self._entry.configure(foreground="white")
        else:
            self.reset()

    def reset(self):
        """Resets the combobox to its placeholder state."""
        self.set(self.placeholder)
        self._entry.configure(foreground="gray")

class TransactionRow(ctk.CTkFrame):
    def __init__(self, master, main_app, data, char_limit, ent_char_limit):
        super().__init__(master, fg_color="gray15")
        self.main_app = main_app
        self.data = data
        self.pack(fill="x", pady=2, padx=5)

        colors = {
            "expense": {"text": "#FF6B6B", "prefix": "-"},
            "gain": {"text": "#4CD964", "prefix": "+"},
            "transfer_out": {"text": "#5AC8FA", "prefix": "-"},
            "transfer_in":  {"text": "#5AC8FA", "prefix": "+"}
        }
        style = colors.get(data.type, {"text": "white", "prefix": ""})

        # Render Columns
        # Date
        self._add_lbl(data.ts.strftime("%Y-%m-%d"), width=100)
        # Vendor or Stream
        if data.entity and len(data.entity) > ent_char_limit:
            display_ent = data.entity[:ent_char_limit].strip() + "..."
        else:
            display_ent = data.entity
        lbl_ent = self._add_lbl(display_ent or "Unknown", width=150, anchor="w", bold=True)
        if data.entity: ToolTip(lbl_ent, data.entity)
        # Category
        self._add_lbl(data.category, width=120)
        # Account or PM
        self._add_lbl(data.pm_or_acc or "???", width=100, anchor="w", color="gray60")
        # Project
        self._add_lbl(data.proj_name or "", width=100, anchor="w", color="#5AC8FA")
        # Description
        desc_px_width = char_limit * 7
        display_desc = (data.desc[:char_limit] + "...") if data.desc and len(data.desc) > char_limit else data.desc
        lbl_desc = self._add_lbl(display_desc or "", width=desc_px_width, anchor="w", color="gray50")
        if data.desc: ToolTip(lbl_desc, data.desc)
        # Row Actions (Buttons will be packed only when cursor hovers over row)
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent", width=96, height=24)
        self.actions_frame.pack_propagate(False)
        self.actions_frame.pack(side="left", padx=(10, 10))

        btn_kwargs = {
            "width": 24,
            "height": 24,
            "fg_color": "transparent",
            "text_color": "gray60",
            "hover_color": "gray40",
            "font": ("JetBrains Mono", 11)
        }

        # Copy Button
        self.btn_copy = ctk.CTkButton(self.actions_frame, text="C", command=self._trigger_copy, **btn_kwargs)
        ToolTip(self.btn_copy, "Copy Transaction")

        # Edit Button
        self.btn_edit = ctk.CTkButton(self.actions_frame, text="E", command=self._trigger_edit, **btn_kwargs)
        ToolTip(self.btn_edit, "Edit Transaction")

        # Delete Button
        del_kwargs = btn_kwargs.copy()
        del_kwargs["hover_color"] = "#8b2525"

        self.btn_del = ctk.CTkButton(self.actions_frame, text="X", command=self._trigger_delete, **del_kwargs)
        ToolTip(self.btn_del, "Delete Transaction")
        # Amount
        amt_str = f"{style['prefix']}{data.amount:,.2f} {data.currency}"
        lbl_amt = self._add_lbl(amt_str, width=120, anchor="e", color=style['text'], bold=True)
        if data.currency != 'EUR': ToolTip(lbl_amt, f"Converted: {style['prefix']}{data.eur_val:,.2f} EUR (Rate: {data.fx_rate})")

        # Hover Effect
        self.is_locked = False
        self._is_hovered = False

        def check_hover():
            if not self.winfo_exists(): return

            if self.is_locked:
                self.after(100, check_hover)
                return

            x, y = self.winfo_pointerxy()
            widget_under_mouse = self.winfo_containing(x, y)

            curr = widget_under_mouse
            is_inside = False
            while curr:
                if curr == self:
                    is_inside = True
                    break
                curr = getattr(curr, 'master', None)

            if is_inside:
                self.after(100, check_hover)
            else:
                self._is_hovered = False
                self.configure(fg_color="gray15")
                self.btn_copy.pack_forget()
                self.btn_edit.pack_forget()
                self.btn_del.pack_forget()

        def on_enter(_e=None, r=self):
            if not r._is_hovered:
                r._is_hovered = True
                r.configure(fg_color="gray25")
                if not r.btn_copy.winfo_ismapped():
                    r.btn_copy.pack(side="left", padx=2)
                    r.btn_edit.pack(side="left", padx=2)
                    r.btn_del.pack(side="left", padx=2)
                r.after(50, check_hover)

        self.on_enter_action = on_enter
        self.on_leave_action = lambda: setattr(self, 'is_locked', False)

        def bind_enter(widget):
            if isinstance(widget, ctk.CTkButton): return
            widget.bind("<Enter>", on_enter, add="+")
            for c in widget.winfo_children():
                bind_enter(c)

        bind_enter(self)
        self._bind_mouse_scroll(self)

    def _add_lbl(self, text, width=0, anchor="center", expand=False, color="white", bold=False, side="left"):
        font = ("JetBrains Mono", 11, "bold") if bold else ("JetBrains Mono", 11)
        lbl = ctk.CTkLabel(self, text=text, width=width, anchor=anchor, text_color=color, font=font)
        lbl.pack(side=side, padx=10, fill="x" if expand else None, expand=expand)
        return lbl

    def _bind_mouse_scroll(self, widget):
        """Forces scroll events to bubble up to the parent scrollable frame."""
        # Windows & Mac
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        # Linux
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")

        widget.bind("<Button-2>", self._start_pan, add="+")
        widget.bind("<B2-Motion>", self._pan, add="+")

        for child in widget.winfo_children():
            self._bind_mouse_scroll(child)

    def _on_mousewheel(self, event):
        """Passes the scroll math to the internal canvas."""
        canvas = getattr(self.master, '_parent_canvas', None)

        if hasattr(canvas, 'yview_scroll'):
            if event.num == 4:  # Linux Up
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:  # Linux Down
                canvas.yview_scroll(1, "units")
            else:  # Windows / Mac
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _start_pan(self, event):
        """Records the starting anchor point for a middle-click drag."""
        canvas = getattr(self.master, '_parent_canvas', None)
        if hasattr(canvas, 'scan_mark'):
            canvas.scan_mark(0, event.y_root)

    def _pan(self, event):
        """Executes the drag based on the anchor point."""
        canvas = getattr(self.master, '_parent_canvas', None)
        if hasattr(canvas, 'scan_dragto'):
            canvas.scan_dragto(0, event.y_root, gain=1)

    def _trigger_copy(self):
        self.main_app.open_copy_transaction(self.data)

    def _trigger_edit(self):
        self.main_app.open_edit_transaction(self.data)

    def _trigger_delete(self):
        self.is_locked = True

        amt_str = f"{self.data.amount:,.2f} {self.data.currency}"
        ent_str = self.data.entity or self.data.proj_name or "Unknown"
        context_str = f"[{self.data.ts.strftime('%Y-%m-%d')}] {ent_str} | {amt_str}"

        def on_cancel():
            self.is_locked = False
            self.on_leave_action()

        self.main_app.delete_transaction_prompt(self.data.id, self.data.type, context_str, on_cancel)