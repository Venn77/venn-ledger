import customtkinter as ctk
import tkinter as tk
import datetime
from utils.io_utils import extract_exchange_rate, validate_parsed_record
from utils.ctk_utils import apply_dynamic_ellipsis
from gui.dialogs import SearchableListDialog
from config import UI_SCALE


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
        self.widget.bind("<ButtonPress>", self.hide_tip, add="+")

    def _schedule(self, _event=None):
        if self.id is not None:
            self.widget.after_cancel(self.id)
            self.id = None
        self.id = self.widget.after(self.delay, self.show_tip)

    def show_tip(self, _event=None):
        if self.tip_window or not self.text:
            return

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.configure(bg="#1a1a1a")
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
        if self.id is not None:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class MonthYearSelector(ctk.CTkFrame):
    """A reusable, self-contained date navigator with dialog selection."""
    def __init__(self, parent, initial_date=None, command=None, show_month=True):
        super().__init__(parent, fg_color="transparent")

        self.current_date: datetime.datetime = initial_date or datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0,
                                                                            microsecond=0)
        self.command = command
        self.show_month = show_month

        overlap = 1 if UI_SCALE == 0.9 else 0

        self.year_frame = ctk.CTkFrame(self, fg_color="gray13", height=28, corner_radius=0)
        self.year_frame.configure(width=140)
        self.year_frame.pack_propagate(False)

        self.btn_year_lbl = ctk.CTkButton(
            self.year_frame, text="", font=("JetBrains Mono", 12, "bold"),
            fg_color="#1f538d", hover_color="#14375e", corner_radius=0,
            width=80 + (overlap * 2), height=28, command=self._select_year
        )
        self.btn_year_lbl.place(x=30 - overlap, y=0)

        self.btn_prev_year = ctk.CTkButton(self.year_frame, text="‹", width=30, height=28, corner_radius=0,
                                           hover_color="#14375e", command=self.go_prev_year)
        self.btn_prev_year.place(x=0, y=0)

        self.btn_next_year = ctk.CTkButton(self.year_frame, text="›", width=30, height=28, corner_radius=0,
                                           hover_color="#14375e", command=self.go_next_year)
        self.btn_next_year.place(x=110, y=0)

        self.month_frame = ctk.CTkFrame(self, fg_color="gray13", height=28, corner_radius=0)
        self.month_frame.configure(width=140)
        self.month_frame.pack_propagate(False)

        self.btn_month_lbl = ctk.CTkButton(
            self.month_frame, text="", font=("JetBrains Mono", 12, "bold"),
            fg_color="#1f538d", hover_color="#14375e", corner_radius=0,
            width=80 + (overlap * 2), height=28, command=self._select_month
        )
        self.btn_month_lbl.place(x=30 - overlap, y=0)

        self.btn_prev_month = ctk.CTkButton(self.month_frame, text="‹", width=30, height=28, corner_radius=0,
                                            hover_color="#14375e", command=self.go_prev_month)
        self.btn_prev_month.place(x=0, y=0)

        self.btn_next_month = ctk.CTkButton(self.month_frame, text="›", width=30, height=28, corner_radius=0,
                                            hover_color="#14375e", command=self.go_next_month)
        self.btn_next_month.place(x=110, y=0)

        self.year_frame.pack(side="left", padx=(0, 5))
        if self.show_month:
            self.month_frame.pack(side="left")

        self.update_display()

    def set_mode(self, show_month):
        """Toggles between showing just the Year, or both Year & Month."""
        self.show_month = show_month
        if self.show_month:
            self.month_frame.pack(side="left")
        else:
            self.month_frame.pack_forget()

    def set_date(self, new_date):
        """Allows parent to force an external date reset."""
        self.current_date = new_date.replace(day=1)
        self.update_display()

    def update_display(self):
        self.btn_year_lbl.configure(text=self.current_date.strftime("%Y"))
        self.btn_month_lbl.configure(text=self.current_date.strftime("%B"))

    def _notify_parent(self):
        """Updates internal UI and triggers the callback to fetch data."""
        self.update_display()
        if self.command:
            self.command(self.current_date)

    def go_prev_year(self):
        self.current_date = self.current_date.replace(year=self.current_date.year - 1)
        self._notify_parent()

    def go_next_year(self):
        self.current_date = self.current_date.replace(year=self.current_date.year + 1)
        self._notify_parent()

    def go_prev_month(self):
        last_month = self.current_date - datetime.timedelta(days=1)
        self.current_date = last_month.replace(day=1)
        self._notify_parent()

    def go_next_month(self):
        next_month = self.current_date + datetime.timedelta(days=32)
        self.current_date = next_month.replace(day=1)
        self._notify_parent()

    def _select_year(self):
        current_yr = self.current_date.year
        # Generate -10 to +10 years
        years = [str(y) for y in range(current_yr - 10, current_yr + 11)]
        dialog = SearchableListDialog(self.btn_year_lbl, "Select Year", years, show_search=True, allow_custom=True)
        try:
            res = dialog.get_result()
            if res:
                self.current_date = self.current_date.replace(year=int(res))
                self._notify_parent()
        except ValueError:
            pass

    def _select_month(self):
        months = [datetime.date(2000, m, 1).strftime('%B') for m in range(1, 13)]
        dialog = SearchableListDialog(self.btn_month_lbl, "Select Month", months, show_search=False)
        res = dialog.get_result()
        if res:
            m_idx = months.index(res) + 1
            self.current_date = self.current_date.replace(month=m_idx)
            self._notify_parent()

class CompoundDropdown(ctk.CTkFrame):
    """Custom fake Dropdown built with two buttons, designed to trigger calls to the SearchableListDialog modal."""
    def __init__(self, master, variable, command=None, width=200, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.command = command
        self.variable = variable
        self.is_disabled = False

        display_width = width - 30

        self.display_btn = ctk.CTkButton(
            self, textvariable=self.variable, width=display_width, height=28,
            anchor="w", fg_color=("gray80", "gray20"),
            hover_color=("gray80", "gray20"),
            border_width=1, border_color=("gray60", "gray50"),
            text_color=("black", "white"),
            cursor="hand2", command=self._on_click
        )
        self.display_btn.pack(side="left", padx=(0, 2))

        self.btn = ctk.CTkButton(
            self, text="▼", width=28, height=28,
            fg_color=("gray80", "gray20"), hover_color=("gray70", "gray30"),
            border_width=1, border_color=("gray60", "gray50"),
            cursor="hand2", command=self._on_click
        )
        self.btn.pack(side="left")

    def _on_click(self):
        if not self.is_disabled and self.command:
            self.command()

    def set_disabled(self, disabled: bool):
        """Grays out both sub-widgets when locked."""
        self.is_disabled = disabled
        if disabled:
            self.display_btn.configure(state="disabled", cursor="arrow", fg_color=("gray90", "gray15"),
                                       text_color=("gray50", "gray50"))
            self.btn.configure(state="disabled", cursor="arrow", fg_color=("gray90", "gray15"))
        else:
            self.display_btn.configure(state="normal", cursor="hand2", fg_color=("gray80", "gray20"),
                                       text_color=("black", "white"))
            self.btn.configure(state="normal", cursor="hand2", fg_color=("gray80", "gray20"))

class SearchableComboBox(ctk.CTkComboBox):
    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.all_values = kwargs.get("values", [])

        self.reset()

        # Bindings
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<KeyRelease>", self._on_key_release)
        self._entry.bind("<Down>", self._on_down_key)

    def _clicked(self, event=None):
        """
        Overrides the CTk chevron click.
        Shows full list, but spawns dialog if > 20 items.
        """
        if self._state == "disabled":
            return

        if self.get() == self.placeholder:
            self.set("")
            self.configure(text_color="white")

        if len(self.all_values) > 20:
            self._spawn_dialog(self.all_values, prefill_text="")
        else:
            self.configure(values=self.all_values)
            super()._clicked(event)

    def _spawn_dialog(self, items_to_show, prefill_text=""):
        """Spawns the modal dialog with controlled initial search text."""
        dialog = SearchableListDialog(
            self.winfo_toplevel(),
            "Select Option",
            items_to_show,
            show_search=True,
            allow_custom=True,
            initial_search=prefill_text
        )

        res = dialog.get_result()
        if res:
            self.set(res)
            self.configure(text_color="white")
            if hasattr(self, "_command") and self._command:
                self._command(res)

    def _dropdown_callback(self, value):
        """Overrides the internal CTk hook for dropdown selections."""
        super()._dropdown_callback(value)
        self._check_and_set_color()

    def _check_and_set_color(self, *_):
        """Sets placeholder color to gray."""
        if self.get() == self.placeholder:
            self.configure(text_color="gray")
        else:
            self.configure(text_color="white")

    def _on_focus_in(self, _event):
        """Clears the placeholder and sets value color."""
        if self.get() == self.placeholder:
            self.set("")
            self.configure(text_color="white")

    def _on_focus_out(self, _event):
        """Sets the placeholder and its color."""
        if self.get() == "":
            self.set(self.placeholder)
            self.configure(text_color="gray")

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
        """Forces filtering on the typed string, then opens menu or dialog."""
        if self._state == "disabled":
            return

        if self.get() == self.placeholder:
            self.set("")
            self.configure(text_color="white")

        typed = self.get().lower()
        if typed == "":
            filtered = self.all_values
        else:
            filtered = [v for v in self.all_values if typed in v.lower()]

        if len(filtered) > 20:
            self._spawn_dialog(filtered, prefill_text=self.get().strip())
        else:
            self.configure(values=filtered)
            if hasattr(self, "_open_dropdown_menu"):
                self._open_dropdown_menu()

    def inject_value(self, value):
        """Pre-fills data for Copy/Edit modes."""
        if value and str(value).strip() != "":
            self.set(str(value))
            self.configure(text_color="white")
        else:
            self.reset()

    def reset(self):
        """Resets the combobox to its placeholder state."""
        self.set(self.placeholder)
        self.configure(text_color="gray")

class AIStagingRow(ctk.CTkFrame):
    """Represents one parsed transaction in a single row, with real-time validation."""
    def __init__(self, parent, data, active_cats, active_pms, active_vendors, active_currencies, app_ref, year, grid_ref):
        super().__init__(parent, fg_color="gray20", corner_radius=6)
        self.data = data
        self.app = app_ref
        self.year = year
        self.grid_ref = grid_ref

        self.cat_names = [c.name for c in active_cats]
        self.pm_names = [p.name for p in active_pms]
        self.ven_names = [v.name for v in active_vendors]
        self.curr_names = [c.code for c in active_currencies]

        self.pm_dict = {p.name: p.account.currency_code for p in active_pms}

        # Expand Vendor & Description
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(8, weight=2)

        # 0. Status Indicator
        self.status_frame = ctk.CTkFrame(self, width=16, height=16, corner_radius=10, fg_color="#1B5E20", border_color="#81C784", border_width=2)
        self.status_frame.grid(row=0, column=0, padx=10, pady=(10, 10))
        self.status_frame.grid_propagate(False)
        self.status_tooltip = ToolTip(self.status_frame, "Initializing...")

        # 1. Date
        ctk.CTkLabel(self, text=data['date'], width=45, font=("JetBrains Mono", 11, "bold")).grid(row=0, column=1,
                                                                                                  padx=5, sticky="w")

        # 2. Vendor (Combo)
        self.ven_combo = SearchableComboBox(self, placeholder="Vendor...", values=self.ven_names, height=24,
                                            command=lambda _: self.validate())
        self.ven_combo.inject_value(data['vendor'])
        self.ven_combo.grid(row=0, column=2, padx=5, sticky="ew")

        # noinspection PyProtectedMember
        self.ven_combo._entry.bind("<KeyRelease>", lambda e: self.validate(), add="+")

        # 3. Amount
        self.amt_var = ctk.StringVar(self, value=str(data['amount']))
        self.amt_entry = ctk.CTkEntry(self, textvariable=self.amt_var, width=80, height=24)
        self.amt_entry.grid(row=0, column=3, padx=5)

        # 4. Currency
        parsed_curr = data['currency']
        combo_currencies = self.curr_names.copy()
        if parsed_curr not in combo_currencies:
            combo_currencies.append(parsed_curr)
        self.currency_combo = ctk.CTkComboBox(self, values=combo_currencies, width=80, height=24, state="readonly",
                                          command=self._on_currency_change)
        self.currency_combo.set(parsed_curr)
        self.currency_combo.grid(row=0, column=4, padx=5)

        # 5. FX Rate
        self.fx_var = ctk.StringVar(self)
        self.fx_entry = ctk.CTkEntry(self, textvariable=self.fx_var, width=80, height=24, placeholder_text="FX")
        self.fx_entry.grid(row=0, column=5, padx=5)
        self.fx_tooltip = ToolTip(self.fx_entry, "")

        self._calculate_fx(self.currency_combo.get(), initial_load=True)

        # 6. Category (Combo)
        self.cat_combo = SearchableComboBox(self, placeholder="Category...", values=self.cat_names, width=120, height=24,
                                         command=lambda _: self.validate())
        self.cat_combo.inject_value(data['category'])
        self.cat_combo.grid(row=0, column=6, padx=5, sticky="ew")

        self.cat_combo.configure(command=lambda _: self.validate())
        # noinspection PyProtectedMember
        self.cat_combo._entry.bind("<KeyRelease>", lambda e: self.validate(), add="+")

        # 7. Payment Method (Combo)
        valid_pms = [name for name, c_code in self.pm_dict.items() if c_code == self.currency_combo.get()]

        self.pm_combo = ctk.CTkComboBox(self, values=valid_pms if valid_pms else ["None"], width=140, height=24,
                                        state="readonly", command=lambda _: self.validate())

        if valid_pms:
            if data['payment_method'] in valid_pms:
                self.pm_combo.set(data['payment_method'])
            else:
                self.pm_combo.set("--- Select ---")
        else:
            self.pm_combo.set("None")
            self.pm_combo.configure(state="disabled")

        self.pm_combo.grid(row=0, column=7, padx=5, sticky="ew")

        # 8. Description (Editable)
        self.desc_var = ctk.StringVar(self, value=data['description'])
        self.desc_entry = ctk.CTkEntry(self, textvariable=self.desc_var, height=24)
        self.desc_entry.grid(row=0, column=8, padx=5, sticky="ew")

        # 9. Discard Button
        self.btn_discard = ctk.CTkButton(self, text="✕", width=30, height=24, fg_color="transparent",
                                         text_color="gray50", hover_color="#b13e3e", command=self.discard_row)
        self.btn_discard.grid(row=0, column=9, padx=(5, 10))

        def on_x_hover(_event):
            # Red
            self.configure(fg_color="#332424")

        def on_x_leave(_event):
            self.configure(fg_color="gray20")

        # Binds
        self.btn_discard.bind("<Enter>", on_x_hover, add="+")
        self.btn_discard.bind("<Leave>", on_x_leave, add="+")
        self.amt_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.desc_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.fx_entry.bind("<KeyRelease>", self._on_fx_manual_edit)

        self.is_valid = False
        self.status_type = ""
        self.validate()

    def _set_fx_tooltip(self, text):
        """Sets the FX rate tooltip."""
        self.fx_tooltip.text = text

    def _on_fx_manual_edit(self, _event):
        """Flags the FX source as Manual if the user types in it."""
        self._set_fx_tooltip("Source: Manual Entry")
        self.validate()

    def _calculate_fx(self, curr_code, initial_load=False):
        """Determines the FX rate and sets the appropriate Tooltip."""
        self.fx_var.set("")

        if curr_code == self.app.manager.base_currency:
            self.fx_entry.configure(state="normal", fg_color="gray15", text_color="gray50", font=("JetBrains Mono", 11))
            self.fx_var.set(f"{self.app.manager.base_currency} Base")
            self.fx_entry.configure(state="disabled")
            self._set_fx_tooltip(f"{self.app.manager.base_currency} is the Base Currency")
            return

        self.fx_entry.configure(state="normal", fg_color=["#F9F9FA", "#343638"], text_color="white", font=("JetBrains Mono", 12))

        if initial_load:
            if 'fx_rate' in self.data:
                saved_val = str(self.data['fx_rate'])
                self.fx_var.set(saved_val)
                if saved_val.strip() == "":
                    self._set_fx_tooltip("Source: Manual Entry Required")
                else:
                    self._set_fx_tooltip("Source: Saved Entry")
                return

            extracted_fx = extract_exchange_rate(self.data['description'])
            if extracted_fx:
                self.fx_var.set(str(extracted_fx))
                self._set_fx_tooltip("Source: Extracted from Description")
                return

        day_str, month_str = self.data['date'].split('/')
        target_dt = datetime.datetime(int(self.year), int(month_str), int(day_str), 12, 0, 0, 0)
        fx_data = self.app.manager.get_historical_fx_rate(curr_code, target_dt)

        if fx_data:
            db_fx, db_ts = fx_data
            self.fx_var.set(str(db_fx))
            self._set_fx_tooltip(f"Source: Historical DB\nLogged: {db_ts.strftime('%Y-%m-%d')}")
        else:
            self._set_fx_tooltip("Source: Manual Entry Required")

    def _on_currency_change(self, new_curr):
        self.data['currency'] = new_curr

        valid_pms = [name for name, c_code in self.pm_dict.items() if c_code == new_curr]

        self.pm_combo.configure(state="readonly", values=valid_pms if valid_pms else ["None"])

        if valid_pms:
            if self.pm_combo.get() not in valid_pms:
                self.pm_combo.set("--- Select ---")
        else:
            self.pm_combo.set("None")
            self.pm_combo.configure(state="disabled")

        self._calculate_fx(new_curr, initial_load=False)
        self.validate()

    def discard_row(self):
        """Marks the item as discarded in memory and marks it discarded in memory."""
        self.data['discarded'] = True

        self.btn_discard.unbind("<Enter>")
        self.btn_discard.unbind("<Leave>")

        self.destroy()
        if hasattr(self.grid_ref, 'update_pagination_state'):
            self.app.after(10, self.grid_ref.update_pagination_state)

    def validate(self):
        """Syncs UI to memory, calls validator, and applies visuals."""
        self.data['description'] = self.desc_var.get().strip()
        self.data['amount'] = self.amt_var.get().strip()
        self.data['payment_method'] = self.pm_combo.get()

        if self.currency_combo.get() != self.app.manager.base_currency:
            self.data['fx_rate'] = self.fx_var.get().strip()

        ven_val = self.ven_combo.get().strip()
        if ven_val == self.ven_combo.placeholder:
            ven_val = ""
        self.data['vendor'] = ven_val

        cat_val = self.cat_combo.get().strip()
        if cat_val == self.cat_combo.placeholder:
            cat_val = ""
        self.data['category'] = cat_val

        errors, warnings = validate_parsed_record(
            data=self.data,
            manager=self.app.manager,
            year=self.year,
            pm_currency_map=self.pm_dict,
            cat_names=self.cat_names,
            ven_names=self.ven_names,
            curr_names=self.curr_names
        )

        if errors:
            self.status_frame.configure(fg_color="#8C2D2D", border_color="#FF8A80") # Red
        elif warnings:
            self.status_frame.configure(fg_color="#8C710A", border_color="#FFF176") # Yellow
        else:
            self.status_frame.configure(fg_color="#1B5E20", border_color="#81C784") # Green

        self.status_tooltip.text = self.data.get('tooltip', "")
        self.is_valid = self.data.get('is_valid', False)

        if self.currency_combo.get() not in self.curr_names:
            self.fx_var.set("")
            self.fx_entry.configure(state="disabled", fg_color="gray15", text_color="gray50")
            self._set_fx_tooltip("Invalid Currency: Cannot apply FX rate.")

        if hasattr(self.grid_ref, 'check_master_validation'):
            self.grid_ref.check_master_validation()

class TransactionRow(ctk.CTkFrame):
    def __init__(self, master, main_app, data, dec_map):
        super().__init__(master, fg_color="gray15")
        self.main_app = main_app
        self.data = data
        self.dec_map = dec_map
        self._hover_timer = None
        self.pack(fill="x", pady=2, padx=5)

        colors = {
            "expense": {"text": "#FF6B6B", "prefix": "-"},
            "gain": {"text": "#4CD964", "prefix": "+"},
            "transfer_out": {"text": "#5AC8FA", "prefix": "-"},
            "transfer_in":  {"text": "#5AC8FA", "prefix": "+"}
        }
        style = colors.get(data.type, {"text": "white", "prefix": ""})

        # Render Columns
        self.grid_columnconfigure(5, weight=1)
        # Date
        self._grid_lbl(data.ts.strftime("%Y-%m-%d"), col=0, width=75)
        # Vendor or Stream
        entity = data.entity or "Unknown"
        lbl_ent = self._grid_lbl(entity, col=1, width=180, anchor="w", bold=True)
        if entity != "Unknown": ToolTip(lbl_ent, entity)
        # Category
        category = data.category or "Not Set"
        lbl_cat = self._grid_lbl(category, col=2, width=120)
        ToolTip(lbl_cat, category)
        # Account or PM
        lbl_acc = self._grid_lbl(data.pm_or_acc or "???", col=3, width=100, anchor="w", color="gray60")
        ToolTip(lbl_acc, data.pm_or_acc or "Unknown Account")
        # Project
        proj = data.proj_name or ""
        lbl_proj = self._grid_lbl(proj, col=4, width=100, anchor="w", color="#5AC8FA")
        if proj: ToolTip(lbl_proj, proj)
        # Description
        desc = data.desc or ""
        lbl_desc = self._grid_lbl(desc, col=5, anchor="w", color="gray50", sticky="ew")
        if desc: ToolTip(lbl_desc, desc)

        # Row Actions (visible when hovering over row)
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent", width=96, height=24)
        self.actions_frame.pack_propagate(False)
        self.actions_frame.grid(row=0, column=6, padx=(10, 10))

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
        amt_str = f"{style['prefix']}{data.amount:,.{dec_map.get(data.currency, 2)}f} {data.currency}"
        lbl_amt = self._grid_lbl(amt_str, col=7, width=170, anchor="e", color=style['text'], bold=True, sticky="e")
        if data.currency != main_app.manager.base_currency and "transfer" not in data.type:
            ToolTip(lbl_amt, f"Converted: {style['prefix']}{data.base_val:,.{main_app.manager.base_currency_decimals}f} {main_app.manager.base_currency} (Rate: {data.fx_rate})")

        # Hover Effect
        self.is_locked = False
        self._is_hovered = False

        def check_hover():
            if not self.winfo_exists(): return

            if self.is_locked:
                self._hover_timer = self.after(100, check_hover)
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
                self._hover_timer = self.after(100, check_hover)
            else:
                self._is_hovered = False
                self._hover_timer = None
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

                if r._hover_timer is not None:
                    r.after_cancel(r._hover_timer)
                r._hover_timer = r.after(50, check_hover)

        self.on_enter_action = on_enter
        self.on_leave_action = lambda: setattr(self, 'is_locked', False)

        def bind_enter(widget):
            if isinstance(widget, ctk.CTkButton): return
            widget.bind("<Enter>", on_enter, add="+")
            for c in widget.winfo_children():
                bind_enter(c)

        bind_enter(self)
        self._bind_mouse_scroll(self)

    def _grid_lbl(self, text, col, width=0, anchor="center", color="white", bold=False, sticky="w"):
        font = ("JetBrains Mono", 11, "bold") if bold else ("JetBrains Mono", 11)
        frame = ctk.CTkFrame(self, fg_color="transparent", height=24)
        if width > 0:
            frame.configure(width=width)
            frame.pack_propagate(False)
        frame.grid(row=0, column=col, padx=10, pady=2, sticky=sticky)
        lbl = ctk.CTkLabel(frame, text=text, text_color=color, font=font, anchor=anchor)
        lbl.place(relx=0, rely=0.5, relwidth=1.0, anchor="w")
        apply_dynamic_ellipsis(frame, lbl, text)
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

        amt_str = f"{self.data.amount:,.{self.dec_map.get(self.data.currency, 2)}f} {self.data.currency}"
        ent_str = self.data.entity or self.data.proj_name or "Unknown"
        context_str = f"[{self.data.ts.strftime('%Y-%m-%d')}] {ent_str} | {amt_str}"

        def on_cancel():
            self.is_locked = False
            self.on_leave_action()

        self.main_app.delete_transaction_prompt(self.data.id, self.data.type, context_str, on_cancel)

    def destroy(self):
        """Safely cleans up pending hover timers before destroying the widget."""
        if self._hover_timer is not None:
            self.after_cancel(self._hover_timer)
            self._hover_timer = None
        super().destroy()

# Monkey Patch: turns regular dropdowns into smart ones! OptionMenu now steals focus on click and supports keyboard interactions!
def _enable_smart_dropdown(cls):
    """Dynamically upgrades any CTk dropdown class to use SearchableListDialog when its contents exceed 20 items."""
    original_clicked = cls._clicked
    original_init = cls.__init__

    def _smart_clicked(self: ctk.CTkComboBox | ctk.CTkOptionMenu, event=None):
        if self._state == "disabled":
            return

        if self.winfo_toplevel():
            self.winfo_toplevel().focus_set()

        values = self._values or []
        if len(values) > 20:
            dialog = SearchableListDialog(
                self,
                "Select Option",
                values,
                show_search=True,
                allow_custom=False,
                initial_search=""
            )

            res = dialog.get_result()
            if res:
                self.set(res)
                if self._command:
                    self._command(res)
        else:
            bound_method = original_clicked.__get__(self, cls)
            bound_method(event)

    def _smart_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        def _open_menu(_event):
            if self._state != "disabled":
                self._clicked()
            return "break"

        target = self._entry if hasattr(self, '_entry') else self

        target.bind("<Down>", _open_menu, add="+")
        if not hasattr(self, '_entry'):
            target.bind("<space>", _open_menu, add="+")
            target.bind("<Return>", _open_menu, add="+")

    cls._clicked = _smart_clicked
    cls.__init__ = _smart_init

_enable_smart_dropdown(ctk.CTkComboBox)
_enable_smart_dropdown(ctk.CTkOptionMenu)


