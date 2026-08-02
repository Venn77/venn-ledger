import customtkinter as ctk
from tkcalendar import Calendar
from utils.icon_manager import set_app_window_icon
from utils.ctk_utils import calculate_dialog_geometry
import datetime


def open_calendar(parent, target_var, include_time=False):
    """Pops up a calendar window to select a date."""
    if hasattr(parent, 'cal_window') and parent.cal_window is not None and parent.cal_window.winfo_exists():
        parent.cal_window.deiconify()
        parent.cal_window.lift()
        parent.cal_window.focus_force()
        return
    parent.cal_window = ctk.CTkToplevel(parent)
    set_app_window_icon(parent.cal_window)
    parent.cal_window.title("Select Date")
    parent.cal_window.attributes("-topmost", True)

    parent.cal_window.geometry(calculate_dialog_geometry(parent, 300, 300))

    # noinspection PyTypeChecker
    parent.cal_window.after(10, lambda: ctk.set_appearance_mode("dark"))
    # noinspection PyTypeChecker
    parent.cal_window.after(90, lambda: force_focus(parent.cal_window))

    try:
        raw_val = target_var.get().strip()
        date_part = raw_val.split(" ")[0]
        start_date = datetime.datetime.strptime(date_part, "%Y-%m-%d")
    except (ValueError, IndexError, AttributeError):
        start_date = datetime.datetime.now()

    cal = Calendar(parent.cal_window, selectmode='day',
                   year=start_date.year,
                   month=start_date.month,
                   day=start_date.day)
    cal.pack(pady=20, padx=10)

    def force_focus(window):
        window.focus_force()
        window.lift()

    def set_date():
        selected_date = cal.selection_get()
        if include_time:
            current_val = target_var.get().strip()
            if " " in current_val:
                active_time = current_val.split(" ")[1]
            else:
                active_time = getattr(parent, 'session_time', datetime.datetime.now().strftime("%H:%M:%S"))

            target_var.set(f"{selected_date} {active_time}")
        else:
            target_var.set(f"{selected_date}")

        parent.cal_window.destroy()

    ctk.CTkButton(parent.cal_window, text="Confirm", command=set_date).pack(pady=10)

def show_popup(parent, title, message, is_error=False, show_ok=True, show_cancel=False, ok_command=None, cancel_command=None, width=400, height=180, message_wraplength=350):
    """
    Shows a dark-mode popup message.
    May include OK, Continue, or Cancel actions.
    """
    root_window = parent.winfo_toplevel()

    if is_error:
        border_color = "#FF6B6B"
    elif not show_ok and not show_cancel:
        border_color = "#5AC8FA" # Blue for loading
    elif show_cancel:
        border_color = "#FF9F0A" # Orange for warnings/prompts
    else:
        border_color = "#4CD964" # Green for success

    popup = ctk.CTkFrame(root_window, width=width, height=height, corner_radius=0, fg_color=border_color)
    popup.place(relx=0.5, rely=0.5, anchor="center")
    popup.pack_propagate(False)

    main_container = ctk.CTkFrame(popup, corner_radius=0)
    main_container.pack(fill="both", expand=True, padx=1, pady=1)

    ctk.CTkLabel(main_container, text=title, font=("JetBrains Mono", 16, "bold"), text_color=border_color).pack(
        pady=(15, 5))
    ctk.CTkLabel(main_container, text=message, font=("JetBrains Mono", 12), wraplength=message_wraplength).pack(pady=(0, 15))

    btn_frame = ctk.CTkFrame(main_container, fg_color="transparent")
    btn_frame.pack(pady=(0, 10))

    def cleanup_and_execute(command_to_run):
        """Releases the app lock and destroys the internal frame."""
        popup.grab_release()
        popup.destroy()
        if command_to_run:
            command_to_run()

    if show_cancel:
        ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="gray40", hover_color="gray50",
                      command=lambda: cleanup_and_execute(cancel_command)).pack(side="left", padx=10)

    if show_ok:
        btn_text = "Continue" if show_cancel else "OK"
        ctk.CTkButton(btn_frame, text=btn_text, width=100, fg_color="#1f538d", hover_color="#14375e",
                      command=lambda: cleanup_and_execute(ok_command)).pack(side="left", padx=10)

    popup.wait_visibility()
    popup.focus_set()
    popup.grab_set()

    return popup

class SimpleDataDialog(ctk.CTkToplevel):
    """Generic popup form for creating/editing Master Data."""
    def __init__(self, parent, title, initial_name="", initial_desc="", has_desc=False, on_submit=None):
        super().__init__(parent)
        self.withdraw()
        self.title(title)

        height = 220 if has_desc else 160
        width = 300
        self.geometry(f"{width}x{height}")
        set_app_window_icon(self)
        self.attributes("-topmost", True)

        self.on_submit = on_submit
        self.has_desc = has_desc

        self.geometry(calculate_dialog_geometry(parent, width, height))

        ctk.CTkLabel(self, text="Name:", font=("JetBrains Mono", 12, "bold")).pack(pady=(15, 0))
        self.name_entry = ctk.CTkEntry(self, width=240)
        self.name_entry.insert(0, initial_name)
        self.name_entry.pack(pady=(5, 10))

        if self.has_desc:
            ctk.CTkLabel(self, text="Description:", font=("JetBrains Mono", 12, "bold")).pack()
            self.desc_entry = ctk.CTkEntry(self, width=240)
            self.desc_entry.insert(0, initial_desc or "")
            self.desc_entry.pack(pady=(5, 10))

        self.err_lbl = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 10), height=15)
        self.err_lbl.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)

        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=self.destroy).pack(side="left",
                                                                                                        padx=10)
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self.submit).pack(side="left", padx=10)

        self.name_entry.focus_set()
        self.bind("<Return>", lambda e: self.submit())

        self.deiconify()
        self.wait_visibility()
        self.grab_set()

    def submit(self):
        name_val = self.name_entry.get().strip()
        desc_val = self.desc_entry.get().strip() if self.has_desc else None

        if not name_val:
            self.err_lbl.configure(text="Name cannot be empty.")
            return

        if self.on_submit:
            success, msg = self.on_submit(name_val, desc_val)
            if success:
                self.destroy()
            else:
                self.err_lbl.configure(text=msg)

class CurrencyDialog(ctk.CTkToplevel):
    """Custom popup for creating Currencies (requires a 10-letter code)."""
    def __init__(self, parent, title, initial_code="", initial_name="", is_edit=False, on_submit=None, base_currency="BASE"):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.is_edit = is_edit
        self.on_submit = on_submit
        self.base_currency = base_currency
        self._example_timer = None

        height = 220 if is_edit else 440
        width = 300
        self.geometry(f"{width}x{height}")
        set_app_window_icon(self)
        self.attributes("-topmost", True)

        self.geometry(calculate_dialog_geometry(parent, width, height))

        ctk.CTkLabel(self, text="Currency Code (Max 10 chars):", font=("JetBrains Mono", 11, "bold")).pack(pady=(15, 0))
        self.code_entry = ctk.CTkEntry(self, width=240)
        self.code_entry.insert(0, initial_code)
        if is_edit:
            self.code_entry.configure(state="disabled")
        else:
            self.code_entry.bind("<KeyRelease>", self._schedule_example_update)

        self.code_entry.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Currency Name:", font=("JetBrains Mono", 11, "bold")).pack()
        self.name_entry = ctk.CTkEntry(self, width=240)
        self.name_entry.insert(0, initial_name)
        self.name_entry.pack(pady=(2, 10))

        if not is_edit:
            ctk.CTkLabel(self, text="# of Decimals:", font=("JetBrains Mono", 11, "bold")).pack()
            self.precision_var = ctk.StringVar(value="2 (Standard Fiat)")
            self.precision_dropdown = ctk.CTkOptionMenu(
                self,
                values=["0 (Whole Numbers)", "2 (Standard Fiat)", "8 (Crypto/Tokens)"],
                variable=self.precision_var,
                width=240
            )
            self.precision_dropdown.pack(pady=(2, 10))

            ctk.CTkLabel(self, text="Conversion Math:", font=("JetBrains Mono", 11, "bold")).pack()
            self.quote_var = ctk.StringVar(value="Divide (Foreign ÷ Rate = Base)")
            self.quote_dropdown = ctk.CTkOptionMenu(
                self,
                values=["Divide (Foreign ÷ Rate = Base)", "Multiply (Foreign × Rate = Base)"],
                variable=self.quote_var,
                width=240,
                command=self._force_example_update
            )
            self.quote_dropdown.pack(pady=(2, 0))

            self.example_lbl = ctk.CTkLabel(
                self,
                text="",
                text_color="#5AC8FA",
                font=("JetBrains Mono", 10)
            )
            self.example_lbl.pack(pady=(0, 10))
            self._render_example_text()

        self.err_lbl = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 10), height=15)
        self.err_lbl.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)

        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=self.destroy).pack(side="left",
                                                                                                        padx=10)
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self.submit).pack(side="left", padx=10)

        self.deiconify()
        self.wait_visibility()
        self.grab_set()

    def _schedule_example_update(self, _event=None):
        """Debounces the text entry so the example can be updated."""
        if self._example_timer:
            self.after_cancel(self._example_timer)
        self._example_timer = self.after(300, self._render_example_text)

    def _force_example_update(self, _selection=None):
        """Immediately updates the label when the dropdown is clicked."""
        self._render_example_text()

    def _render_example_text(self):
        """Dynamically injects the typed code and base currency into the math example."""
        if self.is_edit:
            return

        typed_code = self.code_entry.get().strip().upper()
        if not typed_code:
            typed_code = "XXX"

        selection = self.quote_var.get()
        if "Multiply" in selection:
            msg = (
                f"\nUse this if your rate looks like:\n"
                f"1 {typed_code} = [Rate] {self.base_currency}\n\n"
                f"Math: 100 {typed_code} × 1.15 Rate = 115 {self.base_currency}"
            )
        else:
            msg = (
                f"\nUse this if your rate looks like:\n"
                f"1 {self.base_currency} = [Rate] {typed_code}\n\n"
                f"Math: 1500 {typed_code} ÷ 150 Rate = 10 {self.base_currency}"
            )

        self.example_lbl.configure(text=msg)

    def submit(self):
        code_val = self.code_entry.get().strip().upper()
        name_val = self.name_entry.get().strip()

        if not code_val or len(code_val) > 10:
            self.err_lbl.configure(text="Code must be 1-10 characters.")
            return
        if not name_val:
            self.err_lbl.configure(text="Name cannot be empty.")
            return

        if self.on_submit:
            if self.is_edit:
                success, msg = self.on_submit(code_val, name_val)
            else:
                q_method = "multiply" if "Multiply" in self.quote_var.get() else "divide"

                p_str = self.precision_var.get()
                if p_str.startswith("0"):
                    decimals = 0
                elif p_str.startswith("8"):
                    decimals = 8
                else:
                    decimals = 2

                success, msg = self.on_submit(code_val, name_val, q_method, decimals)

            if success:
                self.destroy()
            else:
                self.err_lbl.configure(text=msg)

class FXDialog(ctk.CTkToplevel):
    """Custom popup for adding a new Exchange Rate."""
    def __init__(self, parent, currency_data, base_currency, base_decimals, on_submit=None):
        super().__init__(parent)
        self.withdraw()
        self.title("New Exchange Rate")
        height = 410
        width = 300
        self.geometry(f"{width}x{height}")
        set_app_window_icon(self)
        self.attributes("-topmost", True)

        self.currency_data = currency_data
        self.base_code = base_currency
        self.base_decimals = base_decimals
        self.on_submit = on_submit

        self.geometry(calculate_dialog_geometry(parent, width, height))

        ctk.CTkLabel(self, text="Foreign Currency:", font=("JetBrains Mono", 11, "bold")).pack(pady=(15, 0))
        self.code_var = ctk.StringVar(value=list(currency_data.keys())[0])
        self.code_dropdown = ctk.CTkOptionMenu(
            self,
            values=list(currency_data.keys()),
            variable=self.code_var,
            width=240,
            command=self._update_preview,
            dynamic_resizing=False
        )
        self.code_dropdown.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Exchange Rate:", font=("JetBrains Mono", 11, "bold")).pack()
        self.rate_entry = ctk.CTkEntry(self, width=240, placeholder_text="e.g. 1.2500")
        self.rate_entry.pack(pady=(2, 0))

        self.preview_lbl = ctk.CTkLabel(self, text="Enter a rate to see preview...", text_color="gray50",
                                        font=("JetBrains Mono", 10))
        self.preview_lbl.pack(pady=(0, 10))

        self.rate_entry.bind("<KeyRelease>", self._update_preview)

        ctk.CTkLabel(self, text="Date (YYYY-MM-DD):", font=("JetBrains Mono", 11, "bold")).pack()
        self.date_entry = ctk.CTkEntry(self, width=240)
        self.date_entry.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(pady=(2, 5))

        ctk.CTkLabel(self, text="Time (HH:MM):", font=("JetBrains Mono", 11, "bold")).pack()
        self.time_entry = ctk.CTkEntry(self, width=240)
        self.time_entry.insert(0, datetime.datetime.now().strftime("%H:%M"))
        self.time_entry.pack(pady=(2, 5))

        self.err_lbl = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 10), height=15)
        self.err_lbl.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)

        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=self.destroy).pack(side="left",
                                                                                                        padx=10)
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self.submit).pack(side="left", padx=10)

        self._update_preview()

        self.deiconify()
        self.wait_visibility()
        self.grab_set()

    def _update_preview(self, _event=None):
        code = self.code_var.get()
        raw_rate = self.rate_entry.get().strip().replace(",", ".")

        try:
            rate = float(raw_rate)
            if rate <= 0: raise ValueError
        except ValueError:
            self.preview_lbl.configure(text="Enter a valid rate to see preview...", text_color="gray50")
            return

        method = self.currency_data[code]["method"]

        if method == "multiply":
            result = 100.0 * rate
            math_sym = "×"
            msg = f"\n1 {code} = {rate:,.4f} {self.base_code}\n"
        else:
            result = 100.0 / rate
            math_sym = "÷"
            msg = f"\n1 {self.base_code} = {rate:,.4f} {code}\n"

        msg += f"Math: 100 {code} {math_sym} {rate} = {result:,.{self.base_decimals}f} {self.base_code}"

        self.preview_lbl.configure(
            text=msg,
            text_color="#5AC8FA"
        )

    def submit(self):
        code = self.code_var.get()
        raw_rate = self.rate_entry.get().strip().replace(",", ".")
        date_val = self.date_entry.get().strip()
        time_val = self.time_entry.get().strip()

        try:
            rate = float(raw_rate)
            if rate <= 0: raise ValueError
        except ValueError:
            self.err_lbl.configure(text="Rate must be a positive number.")
            return

        try:
            dt_str = f"{date_val} {time_val}"
            try:
                timestamp = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                timestamp = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            self.err_lbl.configure(text="Invalid date/time format.")
            return

        if self.on_submit:
            success, msg = self.on_submit(code, rate, timestamp)
            if success:
                self.destroy()
            else:
                self.err_lbl.configure(text=msg)

class AccountDialog(ctk.CTkToplevel):
    def __init__(self, parent, currency_data, initial_name="", initial_desc="", initial_curr="", initial_bal="0.00",
                 is_edit=False, on_submit=None):
        super().__init__(parent)
        self.withdraw()
        self.title("Edit Account" if is_edit else "New Account")
        width = 320
        height = 350
        self.geometry(f"{width}x{height}")
        set_app_window_icon(self)
        self.attributes("-topmost", True)
        self.on_submit = on_submit

        self.currency_data = currency_data

        self.geometry(calculate_dialog_geometry(parent, width, height))

        ctk.CTkLabel(self, text="Account Name:", font=("JetBrains Mono", 11, "bold")).pack(pady=(15, 0))
        self.name_entry = ctk.CTkEntry(self, width=260)
        self.name_entry.insert(0, initial_name)
        self.name_entry.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Description:", font=("JetBrains Mono", 11, "bold")).pack()
        self.desc_entry = ctk.CTkEntry(self, width=260)
        self.desc_entry.insert(0, initial_desc or "")
        self.desc_entry.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Currency:", font=("JetBrains Mono", 11, "bold")).pack()
        codes = list(self.currency_data.keys())
        self.curr_combo = ctk.CTkComboBox(self, values=codes, width=260, command=self._reformat_balance)
        if initial_curr: self.curr_combo.set(initial_curr)
        elif codes: self.curr_combo.set(codes[0])
        if is_edit: self.curr_combo.configure(state="disabled")
        self.curr_combo.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Initial Balance:", font=("JetBrains Mono", 11, "bold")).pack()
        self.bal_entry = ctk.CTkEntry(self, width=260)
        self.bal_entry.insert(0, initial_bal)
        self._reformat_balance(self.curr_combo.get())
        if is_edit: self.bal_entry.configure(state="disabled")
        self.bal_entry.pack(pady=(2, 10))

        self.err_lbl = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 10), height=15)
        self.err_lbl.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=self.destroy).pack(side="left",
                                                                                                        padx=10)
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self.submit).pack(side="left", padx=10)

        self.deiconify()
        self.wait_visibility()
        self.grab_set()

    def _reformat_balance(self, selection):
        """Reapplies the correct decimal formatting when the currency dropdown changes."""
        decimals = self.currency_data.get(selection, 2)

        raw = self.bal_entry.get().strip().replace(",", ".")
        try:
            val = float(raw) if raw else 0.0
        except ValueError:
            val = 0.0

        state = self.bal_entry.cget("state")
        if state == "disabled":
            self.bal_entry.configure(state="normal")

        self.bal_entry.delete(0, "end")
        self.bal_entry.insert(0, f"{val:.{decimals}f}")

        if state == "disabled":
            self.bal_entry.configure(state="disabled")

    def submit(self):
        name = self.name_entry.get().strip()
        if not name:
            self.err_lbl.configure(text="Name cannot be empty.")
            return

        try:
            bal = float(self.bal_entry.get().replace(",", "."))
        except ValueError:
            self.err_lbl.configure(text="Invalid balance amount.")
            return

        if self.on_submit:
            success, msg = self.on_submit(name, self.desc_entry.get().strip(), self.curr_combo.get(), bal)
            if success:
                self.destroy()
            else:
                self.err_lbl.configure(text=msg)

class PMDialog(ctk.CTkToplevel):
    def __init__(self, parent, active_accounts, initial_name="", initial_acc="", on_submit=None):
        super().__init__(parent)
        self.withdraw()
        self.title("Payment Method")
        width = 300
        height = 220
        self.geometry(f"{width}x{height}")
        set_app_window_icon(self)
        self.attributes("-topmost", True)
        self.on_submit = on_submit

        self.geometry(calculate_dialog_geometry(parent, width, height))

        ctk.CTkLabel(self, text="Method Name (e.g. Santander Debit):", font=("JetBrains Mono", 11, "bold")).pack(
            pady=(15, 0))
        self.name_entry = ctk.CTkEntry(self, width=260)
        self.name_entry.insert(0, initial_name)
        self.name_entry.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Linked Account:", font=("JetBrains Mono", 11, "bold")).pack()
        self.acc_combo = ctk.CTkComboBox(self, values=active_accounts, width=260)
        if initial_acc: self.acc_combo.set(initial_acc)
        self.acc_combo.pack(pady=(2, 10))

        self.err_lbl = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 10), height=15)
        self.err_lbl.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=self.destroy).pack(side="left",
                                                                                                        padx=10)
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self.submit).pack(side="left", padx=10)

        self.deiconify()
        self.wait_visibility()
        self.grab_set()

    def submit(self):
        name = self.name_entry.get().strip()
        if not name:
            self.err_lbl.configure(text="Name cannot be empty.")
            return
        if self.on_submit:
            success, msg = self.on_submit(name, self.acc_combo.get())
            if success:
                self.destroy()
            else:
                self.err_lbl.configure(text=msg)