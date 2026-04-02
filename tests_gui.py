import customtkinter as ctk
from models import (
    session, Account, Expense, Gain, Category,
    PaymentMethod, Vendor, Currency, Project,
    Transfer, Payer, Stream
)
from sqlalchemy import desc, or_, func, column, literal_column, union_all, asc, case
from sqlalchemy.orm import aliased
from tkcalendar import Calendar
import finance_manager, datetime, json, os


def open_calendar(parent, target_var, include_time=False):
    """Pops up a calendar window to select a date."""
    if hasattr(parent, 'cal_window') and parent.cal_window is not None and parent.cal_window.winfo_exists():
        parent.cal_window.deiconify()
        parent.cal_window.lift()
        parent.cal_window.focus_force()
        return
    parent.cal_window = ctk.CTkToplevel(parent)
    parent.cal_window.title("Select Date")
    parent.cal_window.attributes("-topmost", True)

    parent.cal_window.after(10, lambda: ctk.set_appearance_mode("dark"))
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
            active_time = getattr(parent, 'session_time', datetime.datetime.now().strftime("%H:%M:%S"))
            target_var.set(f"{selected_date} {active_time}")
        else:
            target_var.set(f"{selected_date}")

        parent.cal_window.destroy()

    ctk.CTkButton(parent.cal_window, text="Confirm", command=set_date).pack(pady=10)

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

class ToolTip:
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self._schedule)
        self.widget.bind("<Leave>", self.hide_tip)

    def _schedule(self, _event=None):
        self.id = self.widget.after(self.delay, self.show_tip)

    def show_tip(self, _event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(tw, text=self.text, corner_radius=5,
                             fg_color="#333333", padx=5, pady=2)
        label.pack()

    def hide_tip(self, _event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class TransactionRow(ctk.CTkFrame):
    def __init__(self, master, data, char_limit, ent_char_limit):
        super().__init__(master, fg_color="gray15")
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
        if len(data.entity) > ent_char_limit:
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
        display_desc = (data.desc[:char_limit] + "...") if data.desc and len(data.desc) > char_limit else data.desc
        lbl_desc = self._add_lbl(display_desc or "", anchor="w", expand=True, color="gray50")
        if data.desc: ToolTip(lbl_desc, data.desc)
        # Amount
        amt_str = f"{style['prefix']}{data.amount:,.2f} {data.currency}"
        lbl_amt = self._add_lbl(amt_str, width=150, anchor="e", color=style['text'], bold=True)
        if data.currency != 'EUR': ToolTip(lbl_amt, f"Converted: {style['prefix']}{data.eur_val:,.2f} EUR (Rate: {data.fx_rate})")
        # Hover Effect
        def on_enter(e, r=self):
            r.configure(fg_color="gray25")

        def on_leave(e, r=self):
            r.configure(fg_color="gray15")

        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)

        # Propagate Hover
        for child in self.winfo_children():
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)

    def _add_lbl(self, text, width=0, anchor="center", expand=False, color="white", bold=False):
        font = ("Arial", 11, "bold") if bold else ("Arial", 11)
        lbl = ctk.CTkLabel(self, text=text, width=width, anchor=anchor, text_color=color, font=font)
        lbl.pack(side="left", padx=10, fill="x" if expand else None, expand=expand)
        return lbl

class AddExpenseWindow(ctk.CTkToplevel):
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.title("Add New Expense")
        self.geometry("450x585")
        self.minsize(450,585)
        self.maxsize(450,585)
        self.manager = manager
        mem = self.manager.last_used

        self.after(100, self.force_focus)
        self.attributes('-topmost', False)

        self.grid_columnconfigure(0, weight=0, minsize=120)
        self.grid_columnconfigure(1, weight=1)

        # UI Form label
        ctk.CTkLabel(self, text="New Expense", font=("Arial", 20, "bold")).grid(row=0, column=0, padx=20, pady=20)

        # Placeholders
        self.cat_placeholder = "Search or type Category..."
        self.ven_placeholder = "Search or type Vendor..."
        self.amount_placeholder = "Amount (e.g. 15.50)"
        self.desc_placeholder = "Description (Optional)"
        self.fx_placeholder = "Rate (e.g. 1.15)"

        # Error label
        self.error_label = ctk.CTkLabel(self, text="", text_color="orange", font=("Arial", 12))
        self.error_label.grid(row=10, column=0, columnspan=2, pady=(10, 5))

        # Clear All & Save Button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=11, column=0, columnspan=2, pady=30)
        self.clear_btn = ctk.CTkButton(btn_frame, text="Clear All", fg_color="gray30", command=self.clear_all)
        self.clear_btn.pack(side="left", padx=10)

        self.save_btn = ctk.CTkButton(btn_frame, text="Save Expense", command=self.submit_data, fg_color="green")
        self.save_btn.pack(side="left", padx=10)

        # Initial values
        # 1. Amount
        self.amount_entry = ctk.CTkEntry(self)
        self.amount_entry.insert(0, self.amount_placeholder)
        self.amount_entry.configure(text_color="gray")
        self.amount_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.amount_entry, self.amount_placeholder))
        self.amount_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.amount_entry, self.amount_placeholder))
        self.amount_entry.bind("<KeyRelease>", self.validate_form)

        # 2. Currency (Dropdown)
        currencies = [c.code for c in session.query(Currency).filter_by(active_bool=True).order_by(Currency.code.asc()).all()]
        self.currency_var = ctk.StringVar(value=mem["currency"])
        self.currency_menu = ctk.CTkOptionMenu(self, values=currencies, variable=self.currency_var, command=self.update_pm_list)

        # 3. Exchange Rate (Automatically changes based on Date and Currency)
        self.fx_label = ctk.CTkLabel(self, text="Exchange Rate", font=("Arial", 13, "bold"), anchor="w")
        self.fx_entry = ctk.CTkEntry(self)
        self.fx_entry.insert(0, self.fx_placeholder)
        self.fx_entry.configure(text_color="gray")
        self.fx_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.fx_entry, self.fx_placeholder))
        self.fx_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.fx_entry, self.fx_placeholder))
        # When the user types, clear the "Suggested" tooltip because the data is now manual
        self.fx_entry.bind("<KeyRelease>", lambda e: self._clear_fx_tooltip())
        self.fx_entry.bind("<KeyRelease>", self.validate_form)

        # 4. Category (SearchableComboBox so we can find existing or type new ones)
        self.all_categories = [c.name for c in session.query(Category).filter_by(active_bool=True).order_by(Category.name.asc()).all()]
        self.category_combo = SearchableComboBox(self,placeholder=self.cat_placeholder,values=self.all_categories)

        # 5. Vendor (ditto)
        self.all_vendors = [v.name for v in session.query(Vendor).filter_by(active_bool=True).order_by(Vendor.name.asc()).all()]
        self.vendor_combo = SearchableComboBox(self, placeholder=self.ven_placeholder, values=self.all_vendors)

        # 6. Datetime
        self.cal_window = None
        date_frame = ctk.CTkFrame(self, fg_color="transparent")
        date_frame.grid(row=7, column=0, padx=20, pady=10, sticky="ew")
        date_frame.grid(row=7, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.session_time = datetime.datetime.now().strftime("%H:%M:%S")
        initial_date = f"{mem['date']} {self.session_time}"
        self.date_var = ctk.StringVar(value=initial_date)
        self.date_entry = ctk.CTkEntry(date_frame, textvariable=self.date_var, width=150)
        self.date_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.today_btn = ctk.CTkButton(date_frame, text="T", width=30, command=lambda: self.set_relative_date(0))
        self.today_btn.pack(side="left", padx=2)

        self.yesterday_btn = ctk.CTkButton(date_frame, text="Y", width=30, command=lambda: self.set_relative_date(1))
        self.yesterday_btn.pack(side="left", padx=2)

        self.date_btn = ctk.CTkButton(date_frame, text="📅", width=40, command=lambda: open_calendar(self, self.date_var, include_time=True))
        self.date_btn.pack(side="left", padx=2)

        # 7. Payment Method
        self.pm_menu = ctk.CTkOptionMenu(self, values=[])
        self.update_pm_list(mem["currency"])
        if mem["pm"] in self.pm_menu.cget("values"):
            self.pm_menu.set(mem["pm"])

        # 8. Description
        self.desc_entry = ctk.CTkEntry(self)
        self.desc_entry.insert(0, self.desc_placeholder)
        self.desc_entry.configure(text_color="gray")
        self.desc_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.desc_entry, self.desc_placeholder))
        self.desc_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.desc_entry, self.desc_placeholder))

        # 9. Project
        projects = [p.name for p in session.query(Project).filter_by(active_bool=True).order_by(Project.name.asc()).all()]
        self.project_var = ctk.StringVar(value=mem["project"])
        self.project_menu = ctk.CTkOptionMenu(self, values=projects, variable=self.project_var)

        # Draw label + fields
        def add_row(label_text, widget, row_idx):
            lbl = ctk.CTkLabel(self, text=label_text, font=("Arial", 13, "bold"), anchor="w")
            lbl.grid(row=row_idx, column=0, padx=(20, 10), pady=8, sticky="w")
            widget.grid(row=row_idx, column=1, padx=(0, 20), pady=8, sticky="ew")

        add_row("Amount", self.amount_entry, 1)
        add_row("Currency", self.currency_menu, 2)
        add_row("Category", self.category_combo, 4)
        add_row("Vendor", self.vendor_combo, 5)
        add_row("Payment Method", self.pm_menu, 6)

        # Date container is special
        date_lbl = ctk.CTkLabel(self, text="Date & Time", font=("Arial", 13, "bold"), anchor="w")
        date_lbl.grid(row=7, column=0, padx=(20, 10), pady=8, sticky="w")

        add_row("Description", self.desc_entry, 8)
        add_row("Project", self.project_menu, 9)

        # Tooltips
        ToolTip(self.today_btn, "Set to Today")
        ToolTip(self.yesterday_btn, "Set to Yesterday")
        ToolTip(self.date_btn, "Open Calendar")
        self.fx_tooltip = ToolTip(self.fx_entry, "Latest known rate will appear here")

        # Keep an eye out! These get updated fx rate as... something changes
        # 1. Trace the Currency Variable
        self.currency_var.trace_add("write", lambda *args: self.update_fx_list(self.currency_var.get()))
        self.currency_var.trace_add("write", self.validate_form)

        # 2. Trace the Date Variable
        self.date_var.trace_add("write", lambda *args: self.update_fx_list(self.currency_var.get()))
        self.date_var.trace_add("write", self.validate_form)

        # 3. Initial Trigger
        self.update_fx_list()
        self.validate_form()

    def _entry_focus_in(self, widget, placeholder):
        """Clears the placeholder and sets value color."""
        if widget.get() == placeholder:
            widget.delete(0, 'end')
            widget.configure(text_color="white")

    def _entry_focus_out(self, widget, placeholder):
        """Sets the placeholder and its color."""
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.configure(text_color="gray")

    def _clear_fx_tooltip(self):
        """Clears the 'Historical' tooltip if the user starts typing a manual rate."""
        if self.fx_entry.get() != self.fx_placeholder:
            self.fx_tooltip.text = "Manual rate entered"

    def force_focus(self):
        self.focus_force()
        self.lift()
        self.amount_entry.focus()

    def get_current_time_part(self):
        """Extracts the HH:MM:SS part from the current entry, falling back to session_time."""
        current_val = self.date_var.get()
        try:
            if " " in current_val:
                return current_val.split(" ")[1]
            return self.session_time
        except:
            return self.session_time

    def clear_all(self):
        """Resets the form to default values."""
        self.amount_entry.delete(0, 'end')
        self.amount_entry.insert(0, self.amount_placeholder)
        self.amount_entry.configure(text_color="gray")
        self.desc_entry.delete(0, 'end')
        self.desc_entry.insert(0, self.desc_placeholder)
        self.desc_entry.configure(text_color="gray")

        for combo in [self.category_combo, self.vendor_combo]:
            combo.set(combo.placeholder)
            # noinspection PyProtectedMember
            combo._entry.configure(foreground="gray")

        # Reset Menus and Date
        self.currency_var.set("EUR")
        self.update_pm_list("EUR")
        self.project_var.set("")
        self.date_var.set(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.update_fx_list()

        # Put focus back at the start
        self.force_focus()
        self.amount_entry.focus()

    def set_relative_date(self, days_ago):
        """
        Sets the date_var to Today (0) or Yesterday (1).
        Keeps the time.
        """
        active_time = self.get_current_time_part()
        target_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        date_part = target_date.strftime("%Y-%m-%d")
        formatted_date = f"{date_part} {active_time}"
        self.date_var.set(formatted_date)

    def update_fx_list(self, *args):
        """Refreshes FX rate based on currency and date."""
        selected_currency = self.currency_var.get()
        if selected_currency == "EUR":
            self.fx_label.grid_forget()
            self.fx_entry.grid_forget()
            return

        # 1. Show the fields
        self.fx_label.grid(row=3, column=0, padx=(20, 10), pady=8, sticky="w")
        self.fx_entry.grid(row=3, column=1, padx=(0, 20), pady=8, sticky="ew")

        # 2. Extract Date (Handling potential empty/malformed strings)
        try:
            full_date = self.date_var.get()
            if not full_date or len(full_date) < 10:
                return

            result = self.manager.get_historical_fx_rate(
                currency_code=selected_currency,
                target_date=full_date
            )

            if result:
                rate_val, ts = result
                self.fx_entry.delete(0, 'end')
                self.fx_entry.insert(0, str(rate_val))
                self.fx_entry.configure(text_color="white")
                self.fx_tooltip.text = f"Suggested rate from: {ts.strftime('%Y-%m-%d')}"
            else:
                self.fx_entry.delete(0, 'end')
                self.fx_entry.insert(0, self.fx_placeholder)
                self.fx_entry.configure(text_color="gray")
                self.fx_tooltip.text = "No historical rate found."
        except Exception as e:
            print(f"FX Sync Error: {e}")

    def update_pm_list(self, selected_currency):
        """Filters Payment Methods based on the account's currency."""
        valid_pms = (
            session.query(PaymentMethod)
            .join(Account)
            .filter(Account.currency_code == selected_currency)
            .filter(PaymentMethod.active_bool == True)
            .order_by(PaymentMethod.name.asc())
            .all()
        )

        pm_names = [p.name for p in valid_pms]

        if pm_names:
            self.pm_menu.configure(values=pm_names)
            self.pm_menu.set(pm_names[0])
        else:
            self.pm_menu.configure(values=["No valid PM found"])
            self.pm_menu.set("No valid PM found")

        self.validate_form()

    def is_float(self, val):
        """Checks if a string can be a valid currency float."""
        try:
            float(val.replace(",", "."))
            return True
        except ValueError:
            return False

    def is_valid_date(self, val):
        """Checks if the date string matches the YYYY-MM-DD HH:MM format."""
        try:
            datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
            return True
        except ValueError:
            return False

    def validate_form(self, *args):
        """Checks if all required fields are filled to enable the Save button."""
        # 1. Required: Amount (Must not be placeholder or empty)
        amt_val = self.amount_entry.get()
        amt_ok = (amt_val != self.amount_placeholder and
                  amt_val.strip() != "" and
                  self.is_float(amt_val))

        # 2. Required: Date
        date_val = self.date_var.get()
        date_ok = self.is_valid_date(date_val)

        # 2. Required: Currency & PM (OptionMenus usually always have a value, but just in case)
        cur_ok = self.currency_var.get() != ""
        pm_ok = self.pm_menu.get() not in ["", "No valid PM found"]

        # 3. Required: FX Rate (ONLY if Currency != EUR)
        if self.currency_var.get() != "EUR":
            fx_val = self.fx_entry.get()
            fx_ok = (fx_val != self.fx_placeholder and fx_val.strip() != "" and self.is_float(fx_val))
        else:
            fx_ok = True  # Not required for EUR

        # 4. Toggle Button State
        if amt_ok and date_ok and cur_ok and pm_ok and fx_ok:
            try:
                current_amt = float(self.amount_entry.get().replace(",", "."))
                current_vendor = self.vendor_combo.get().strip()
                current_date = self.date_var.get()

                is_duplicate = self.manager.check_for_duplicate(current_amt, current_vendor, current_date)

                if is_duplicate:
                    self.save_btn.configure(state="normal", fg_color="#EBCB8B", text_color="black")
                    self.error_label.configure(text="⚠ Potential duplicate detected!", text_color="orange")
                else:
                    self.save_btn.configure(state="normal", fg_color="green", text_color="white")
                    self.error_label.configure(text="")
            except:
                self.save_btn.configure(state="normal", fg_color="green", text_color="white")
        else:
            self.save_btn.configure(state="disabled", fg_color="gray30", text_color="white")
            if not amt_ok:
                self.error_label.configure(text="⚠ Check Amount (must be a number)")
            elif not date_ok:
                self.error_label.configure(text="⚠ Check Date format (YYYY-MM-DD HH:MM:SS)")
            elif not fx_ok:
                self.error_label.configure(text="⚠ Check Exchange Rate (must be a number)")
            elif not pm_ok:
                self.error_label.configure(text="⚠ Select a valid Payment Method")
            elif not cur_ok:
                self.error_label.configure(text="⚠ Select a valid Currency")

    def submit_data(self):
        """Invokes the finance manager to submit to DB."""
        try:
            # 1. Mandatory Fields
            amt = float(self.amount_entry.get().replace(",", "."))
            cur = self.currency_var.get()
            pm = self.pm_menu.get()
            ts = datetime.datetime.strptime(self.date_var.get(), "%Y-%m-%d %H:%M:%S")

            # 2. FX Rate Logic
            if cur == "EUR":
                fx_rate = None
            else:
                fx_rate = float(self.fx_entry.get().replace(",", "."))

            # 3. Handle Optional Fields (Convert placeholders to empty strings)
            cat = self.category_combo.get()
            if cat == self.cat_placeholder: cat = ""

            ven = self.vendor_combo.get()
            if ven == self.ven_placeholder: ven = ""

            descr = self.desc_entry.get()
            if descr == self.desc_placeholder: descr = ""

            proj = self.project_var.get()

            # 4. Execute the manager
            self.manager.add_expense(
                amount=amt,
                currency_code=cur,
                category_name=cat,
                vendor_name=ven,
                payment_method_name=pm,
                project_name=proj,
                description=descr,
                exchange_rate=fx_rate,
                timestamp=ts
            )

            # 5. Success Flash
            self.save_btn.configure(text="✔ Added!", fg_color="darkgreen", state="disabled")
            self.error_label.configure(text="Expense saved successfully", text_color="green")

            # 6. Wait & Refresh Main
            self.after(1000, self.finalize_and_refresh)

        except Exception as e:
            self.error_label.configure(text=f"⚠ Database Error: {str(e)}", text_color="red")
            print(f"Submission Error: {e}")

    def finalize_and_refresh(self):
        """Kills the popup and triggers the main app reload."""
        main_app = self.master

        self.destroy()

        if hasattr(main_app, "refresh_accounts") and hasattr(main_app, "load_transactions"):
            main_app.after(10, main_app.refresh_accounts)
            main_app.after(50, main_app.load_transactions)

class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Venn Ledger 2026")
        self.geometry("1300x700")
        self.minsize(1300, 700)
        self.maxsize(1300,980)
        ctk.set_appearance_mode("dark")
        self.manager = finance_manager.TransactionManager(session)
        self.cal_window = None

        # 1. Grid Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 2. Sidebar (Accounts & Quick Actions)
        self.reorder_mode = False
        self.selected_account_id = None
        self.filter_account_id = None

        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo = ctk.CTkLabel(self.sidebar, text="FINANCE", font=("Arial", 24, "bold"))
        self.logo.pack(pady=30, padx=20)

        self.add_btn = ctk.CTkButton(self.sidebar, text="+ Add Expense", command=self.open_add_expense)
        self.add_btn.pack(pady=20, padx=20)

        self.nw_frame = ctk.CTkFrame(self.sidebar, fg_color="gray15", corner_radius=8)
        self.nw_frame.pack(fill="x", pady=(0, 15), padx=15)

        self.reorder_btn = ctk.CTkButton(self.sidebar, text="⇅ Reorder Accounts", fg_color="transparent",
                                         border_width=1, command=self.toggle_reorder_mode)
        self.reorder_btn.pack(pady=(10, 20), padx=20, fill="x")

        self.acc_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", label_text="Accounts")
        self.acc_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # Account List
        self.refresh_accounts()

        # 3. Main Content Area
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_bar.pack(fill="x", pady=(0, 20))

        self.header = ctk.CTkLabel(self.top_bar, text="Transactions", font=("Arial", 22, "bold"))
        self.header.pack(side="left", anchor="w")

        self.search_group = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        self.search_group.pack(side="right", padx=(20, 0))

        self.search_placeholder = "Search vendor, payer, description, category or stream..."
        self.search_entry = ctk.CTkEntry(self.search_group, width=350, text_color="gray")
        self.search_entry.insert(0, self.search_placeholder)
        self.search_entry.pack(side="left")

        self.clear_search_btn = ctk.CTkButton(
            self.search_group,
            text="×",
            width=30,
            fg_color="transparent",
            text_color="gray60",
            hover_color="gray25",
            command=self.clear_search_action
        )
        self.clear_search_btn.pack(side="left", padx=(5, 0))

        # 4. Filter Bar
        self.date_filter_var = ctk.StringVar(value="All Time")

        self.filter_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.filter_bar.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(self.filter_bar, text="Date Range:", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 10))

        self.date_menu = ctk.CTkOptionMenu(
            self.filter_bar,
            values=["All Time", "Today", "Last 7 Days", "This Month", "Last Month", "This Year", "Custom..."],
            variable=self.date_filter_var,
            command=self.on_date_filter_change,
            width=140
        )
        self.date_menu.pack(side="left")

        self.start_date_var = ctk.StringVar(value=(datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"))
        self.end_date_var = ctk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))

        self.custom_date_frame = ctk.CTkFrame(self.filter_bar, fg_color="transparent")

        ctk.CTkLabel(self.custom_date_frame, text="From:").pack(side="left", padx=2)
        self.start_entry = ctk.CTkEntry(self.custom_date_frame, textvariable=self.start_date_var, width=90)
        self.start_entry.pack(side="left", padx=2)

        self.start_cal_btn = ctk.CTkButton(
            self.custom_date_frame, text="📅", width=30,
            command=lambda: open_calendar(self, self.start_date_var, include_time=False)
        )
        self.start_cal_btn.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(self.custom_date_frame, text="To:").pack(side="left", padx=2)
        self.end_entry = ctk.CTkEntry(self.custom_date_frame, textvariable=self.end_date_var, width=90)
        self.end_entry.pack(side="left", padx=2)

        self.end_cal_btn = ctk.CTkButton(
            self.custom_date_frame, text="📅", width=30,
            command=lambda: open_calendar(self, self.end_date_var, include_time=False)
        )
        self.end_cal_btn.pack(side="left", padx=(0, 10))

        self.apply_date_btn = ctk.CTkButton(self.custom_date_frame, text="Apply", width=60, command=self.load_transactions)
        self.apply_date_btn.pack(side="left", padx=5)

        self.search_entry.bind("<FocusIn>", lambda e: self._search_focus_in())
        self.search_entry.bind("<FocusOut>", lambda e: self._search_focus_out())
        self.search_entry.bind("<KeyRelease>", self.on_search_key_release)

        # 4. Transaction Counter
        self.transaction_counter_lbl = ctk.CTkLabel(
            self.top_bar,
            text="Showing 0 of 0 transactions",
            font=("Arial", 11),
            text_color="gray50"
        )
        self.transaction_counter_lbl.pack(pady=(0, 5), anchor="e", padx=20)

        # 5. Scrollable Table
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="History")
        self.scroll_frame.pack(fill="both", expand=True)

        # 6. Navigation Bar
        self.nav_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=50)
        self.nav_bar.pack(fill="x", pady=5)

        self.totals_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.totals_frame.pack(pady=(0, 10), padx=20, side="right")

        self.in_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("Arial", 12, "bold"), text_color="#4CD964", anchor="e")
        self.in_lbl.pack(fill="x")

        self.out_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("Arial", 12, "bold"), text_color="#b13e3e", anchor="e")
        self.out_lbl.pack(fill="x")

        self.balance_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("Arial", 13, "bold"), anchor="e")
        self.balance_lbl.pack(fill="x")

        ToolTip(self.search_entry,self.search_placeholder)

        self.selected_account_id = None

        self.current_page = 0
        self.page_size = 40
        self.total_pages = 0
        self.jump_entry = None
        self.search_timer = None
        self.current_search_text = ""

        self.load_transactions()

    def _search_focus_in(self):
        if self.search_entry.get() == self.search_placeholder:
            self.search_entry.delete(0, "end")
            self.search_entry.configure(text_color="white")

    def _search_focus_out(self):
        if not self.search_entry.get():
            self.search_entry.insert(0, self.search_placeholder)
            self.search_entry.configure(text_color="gray")

    def on_search_key_release(self, _event):
        val = self.search_entry.get()

        if val == self.search_placeholder:
            return

        if hasattr(self, 'search_timer') and self.search_timer:
            self.after_cancel(self.search_timer)

        self.search_timer = self.after(500, self.execute_search)

    def execute_search(self):
        self.search_timer = None

        current_val = self.search_entry.get()
        if current_val == self.search_placeholder:
            search_text = ""
        else:
            search_text = current_val

        self.current_search_text = search_text
        self.current_page = 0
        self.load_transactions()

    def clear_search_action(self):
        if self.search_entry.get() == self.search_placeholder or self.search_entry.get() == "":
            return

        self.search_entry.delete(0, "end")
        self.search_entry.focus_set()

        self.current_search_text = ""
        self.current_page = 0

        if hasattr(self, 'search_timer') and self.search_timer:
            self.after_cancel(self.search_timer)
            self.search_timer = None

        self.load_transactions()
        self.reset_scroll_to_top()

    def on_date_filter_change(self, selection):
        if selection == "Custom...":
            self.custom_date_frame.pack(side="left", padx=20)
        else:
            self.custom_date_frame.pack_forget()
            self.current_page = 0
            self.load_transactions()
            self.reset_scroll_to_top()

    def get_date_limit(self, selection):
        """Calculates the 'start' date for the SQL query."""
        now = datetime.datetime.now()
        if selection == "Today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif selection == "Last 7 Days":
            return now - datetime.timedelta(days=7)
        elif selection == "This Month":
            return now.replace(day=1, hour=0, minute=0, second=0)
        elif selection == "Last Month":
            first_of_this = now.replace(day=1)
            last_of_prev = first_of_this - datetime.timedelta(days=1)
            return last_of_prev.replace(day=1, hour=0, minute=0, second=0)
        elif selection == "This Year":
            return now.replace(month=1, day=1, hour=0, minute=0, second=0)
        return None

    def get_dynamic_char_limit(self):
        """Calculates how many characters can fit in the Description gap."""
        self.update_idletasks()
        current_width = 1300
        # Sum of static widths + sidebar:
        static_space = 800+250

        available_pixels = current_width - static_space

        char_limit = int(available_pixels / 7)

        return max(20, char_limit)

    def refresh_accounts(self):
        """Builds the account buttons and the Net Worth summary."""
        for widget in self.nw_frame.winfo_children():
            widget.destroy()

        # Net Worth
        net_worth = self.manager.get_net_worth()

        ctk.CTkLabel(self.nw_frame, text="TOTAL NET WORTH", font=("Arial", 10, "bold"), text_color="gray").pack(pady=(8, 0))
        ctk.CTkLabel(self.nw_frame, text=f"€ {net_worth:,.2f}", font=("Arial", 18, "bold"), text_color="#4CD964").pack(
            pady=(0, 8))

        # Account cards
        for widget in self.acc_scroll.winfo_children():
            widget.destroy()

        accounts = {a.id: a for a in session.query(Account).order_by(Account.name.asc()).all()}
        saved_order = self.load_account_order()

        ordered_ids = [aid for aid in saved_order if aid in accounts]
        new_ids = [aid for aid in accounts.keys() if aid not in ordered_ids]
        final_order = ordered_ids + new_ids

        if new_ids:
            self.save_account_order(final_order)

        for acc_id in final_order:
            acc = accounts[acc_id]

            is_filtered = (not self.reorder_mode and acc.id == self.filter_account_id)
            is_selected_swap = (self.reorder_mode and acc.id == self.selected_account_id)

            # Base colors
            if is_selected_swap:
                base_bg = "gray25"
                border_col = "#4CD964"  # Green
                border_w = 2
            elif is_filtered:
                base_bg = "#1f538d"  # Blue
                border_col = base_bg
                border_w = 0
            else:
                base_bg = "gray20"
                border_col = base_bg
                border_w = 0

            # Hover colors
            hover_bg = "#2c5d8f" if is_filtered else "gray30"

            # Compact Card
            acc_card = ctk.CTkFrame(self.acc_scroll, fg_color=base_bg, border_color=border_col, border_width=border_w, corner_radius=4)
            acc_card.pack(pady=2, padx=5, fill="x")

            # Hover Effect
            def on_enter(e, card=acc_card, h_bg=hover_bg):
                card.configure(fg_color=h_bg)

            def on_leave(e, card=acc_card, b_bg=base_bg):
                card.configure(fg_color=b_bg)

            # Bind to the frame itself
            acc_card.bind("<Enter>", on_enter)
            acc_card.bind("<Leave>", on_leave)
            acc_card.bind("<Button-1>", lambda e, aid=acc.id: self.handle_account_click(aid))

            # Row 1: Name
            ctk.CTkLabel(acc_card, text=acc.name.upper(),
                         font=("Arial", 10),
                         anchor="w", height=15).pack(fill="x", padx=10, pady=(5, 0))

            # Row 2: Balance
            bal_color = "#FF6B6B" if acc.balance < 0 else "white"
            ctk.CTkLabel(acc_card, text=f"{acc.balance:,.2f} {acc.currency_code}",
                         font=("Arial", 12, "bold"), text_color=bal_color,
                         anchor="w", height=20).pack(fill="x", padx=10, pady=(0, 5))

            for child in acc_card.winfo_children():
                child.bind("<Button-1>", lambda e, aid=acc.id: self.handle_account_click(aid))
                child.bind("<Enter>", on_enter)
                child.bind("<Leave>", on_leave)

    def toggle_reorder_mode(self):
        self.reorder_mode = not self.reorder_mode
        self.selected_account_id = None
        color = "#1f538d" if self.reorder_mode else "transparent"
        self.reorder_btn.configure(fg_color=color)
        self.refresh_accounts()

    def load_account_order(self):
        """Loads the account ID order from a local JSON file."""
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    return json.load(f).get("account_order", [])
        except (json.decoder.JSONDecodeError, IOError):
            return[]
        return []

    def save_account_order(self, order_list):
        """Saves the current list of account IDs to JSON."""
        config = {}
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)

        config["account_order"] = order_list
        with open("config.json", "w") as f:
            json.dump(config, f)

    def handle_account_click(self, account_id):
        if self.reorder_mode:
            # Swap
            if self.selected_account_id is None:
                self.selected_account_id = account_id
                self.refresh_accounts()
            else:
                order = self.load_account_order()
                if self.selected_account_id not in order: order.append(self.selected_account_id)
                if account_id not in order: order.append(account_id)

                idx1, idx2 = order.index(self.selected_account_id), order.index(account_id)
                order[idx1], order[idx2] = order[idx2], order[idx1]

                self.save_account_order(order)
                self.selected_account_id = None
                self.refresh_accounts()
        else:
            # Filter
            if self.filter_account_id == account_id:
                self.filter_account_id = None
            else:
                self.filter_account_id = account_id
            self.current_page = 0
            self.reset_scroll_to_top()

            self.refresh_accounts()
            self.load_transactions()

    def load_transactions(self):
        """Fetches a page of transactions and renders them as rows."""
        self.update_idletasks()

        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        query = self.get_unified_transaction_query(session)

        selection = self.date_filter_var.get()

        if selection == "Custom...":
            try:
                start = datetime.datetime.strptime(self.start_date_var.get(), "%Y-%m-%d").replace(hour=0, minute=0)
                end = datetime.datetime.strptime(self.end_date_var.get(), "%Y-%m-%d").replace(hour=23, minute=59)
                query = query.filter(column("ts").between(start, end))
            except ValueError:
                pass
        else:
            date_limit = self.get_date_limit(selection)
            if date_limit:
                query = query.filter(column("ts") >= date_limit)

        date_limit = self.get_date_limit(self.date_filter_var.get())
        if date_limit:
            query = query.filter(column("ts") >= date_limit)

        if self.filter_account_id:
            query = query.filter(column("acc_id") == self.filter_account_id)

        search_text = str(getattr(self, 'current_search_text', "")).strip()
        if search_text:
            search_pattern = f"%{search_text}%"
            query = query.filter(
                or_(
                    column("entity").ilike(search_pattern),
                    column("desc").ilike(search_pattern),
                    column("category").ilike(search_pattern)
                )
            )

        total_count = query.count()

        self.total_pages = (total_count + self.page_size - 1) // self.page_size

        offset = self.current_page * self.page_size

        results = query.order_by(desc(column("ts")),asc(column("type")),desc(column("id"))).offset(offset).limit(self.page_size).all()

        char_limit = self.get_dynamic_char_limit()

        ent_char_limit = char_limit - 17

        for row_data in results:
            TransactionRow(self.scroll_frame, row_data, char_limit, ent_char_limit)

        self.update_pagination_ui(total_count, query)

    def get_unified_transaction_query(self, current_session):
        # 1. EXPENSES
        q1 = current_session.query(
            Expense.id.label("id"),
            Expense.timestamp.label("ts"),
            Expense.amount.label("amount"),
            Expense.currency_code.label("currency"),
            Expense.converted_amount.label("eur_val"),
            Expense.fx_rate.label("fx_rate"),
            Expense.description.label("desc"),
            literal_column("'expense'").label("type"),
            Vendor.name.label("entity"),
            Category.name.label("category"),
            PaymentMethod.account_id.label("acc_id"),
            PaymentMethod.name.label("pm_or_acc"),
            Project.name.label("proj_name")
        ).outerjoin(Vendor).outerjoin(Category).join(PaymentMethod).outerjoin(Project)

        # 2. GAINS
        q2 = current_session.query(
            Gain.id.label("id"),
            Gain.timestamp.label("ts"),
            Gain.amount.label("amount"),
            Gain.currency_code.label("currency"),
            Gain.converted_amount.label("eur_val"),
            Gain.fx_rate.label("fx_rate"),
            Gain.description.label("desc"),
            literal_column("'gain'").label("type"),
            Payer.name.label("entity"),
            Stream.name.label("category"),
            Gain.account_id.label("acc_id"),
            Account.name.label("pm_or_acc"),
            Project.name.label("proj_name")
        ).outerjoin(Payer).outerjoin(Stream).join(Account).outerjoin(Project)

        # 3a. TRANSFERS (Outbound)
        origin_account = aliased(Account)
        q3_out = (session.query(
            Transfer.id.label("id"),
            Transfer.timestamp.label("ts"),
            Transfer.amount_origin.label("amount"),
            origin_account.currency_code.label("currency"),
            Transfer.amount_destination.label("eur_val"),
            literal_column("NULL").label("fx_rate"),
            Transfer.description.label("desc"),
            literal_column("'transfer_out'").label("type"),
            (literal_column("'To: '") + Account.name).label("entity"),
            literal_column("'Transfer Out'").label("category"),
            Transfer.origin_account_id.label("acc_id"),
            origin_account.name.label("pm_or_acc"),
            literal_column("''").label("proj_name")
        ).join(Account, Transfer.destination_account_id == Account.id)
        .join(origin_account, Transfer.origin_account_id == origin_account.id))

        # 3b. TRANSFERS (Inbound)
        dest_account = aliased(Account)
        q3_in = (session.query(
            Transfer.id.label("id"),
            Transfer.timestamp.label("ts"),
            Transfer.amount_destination.label("amount"),
            dest_account.currency_code.label("currency"),
            Transfer.amount_origin.label("eur_val"),
            literal_column("NULL").label("fx_rate"),
            Transfer.description.label("desc"),
            literal_column("'transfer_in'").label("type"),
            (literal_column("'From: '") + Account.name).label("entity"),
            literal_column("'Transfer In'").label("category"),
            Transfer.destination_account_id.label("acc_id"),
            dest_account.name.label("pm_or_acc"),
            literal_column("''").label("proj_name")
        ).join(Account, Transfer.origin_account_id == Account.id)
                 .join(dest_account, Transfer.destination_account_id == dest_account.id))

        unified_stmt = union_all(q1, q2, q3_out, q3_in).alias("unified")

        final_query = current_session.query(unified_stmt)

        return final_query

    def update_pagination_ui(self, total_count, current_query):
        """Updates the counter and the footer totals."""
        start_idx = (self.current_page * self.page_size) + 1
        end_idx = min(start_idx + self.page_size - 1, total_count)

        count_text = f"Showing {start_idx}-{end_idx} of {total_count} transactions"

        if total_count == 0:
            count_text = "No transactions found"
        self.transaction_counter_lbl.configure(text=count_text)

        if total_count > 0:
            (in_eur, in_dict), (out_eur, out_dict), net_bal = self.calculate_totals(current_query)

            in_brk = " | ".join([f"{amt:,.2f} {c}" for c, amt in in_dict.items()]) or "0.00 EUR"
            self.in_lbl.configure(text=f"In: {in_brk}  (Combined: ≈ {in_eur:,.2f} EUR)")

            out_brk = " | ".join([f"{amt:,.2f} {c}" for c, amt in out_dict.items()]) or "0.00 EUR"
            self.out_lbl.configure(text=f"Out: {out_brk}  (Combined: ≈ {out_eur:,.2f} EUR)")

            self.balance_lbl.configure(text=f"Balance: (≈ {net_bal:,.2f} EUR)")

            bal_color = "#4CD964" if net_bal >= 0 else "#b13e3e"
            self.balance_lbl.configure(text_color=bal_color)
        else:
            for lbl in [self.in_lbl, self.out_lbl, self.balance_lbl]:
                lbl.configure(text="")

        self.render_pagination_controls()

    def calculate_totals(self, base_query):
        """
        Calculates In, Out, and Balance.
        Ignores Transfers.
        """
        sub = base_query.subquery()

        totals_eur = session.query(
            func.sum(case((sub.c.type == 'gain', sub.c.eur_val), else_=0)).label("in_eur"),
            func.sum(case((sub.c.type == 'expense', sub.c.eur_val), else_=0)).label("out_eur")
        ).one()

        in_eur = totals_eur[0] or 0
        out_eur = totals_eur[1] or 0
        net_balance = in_eur - out_eur

        raw_breakdown = (session.query(
            sub.c.type,
            sub.c.currency,
            func.sum(sub.c.amount)
        )
                    .filter(sub.c.type.in_(['gain', 'expense']))
                    .group_by(sub.c.type, sub.c.currency).all())

        in_dict = {}
        out_dict = {}
        for r_type, curr, amt in raw_breakdown:
            if r_type == 'gain':
                in_dict[curr] = amt
            else:
                out_dict[curr] = amt

        return (in_eur, in_dict), (out_eur, out_dict), net_balance

    def render_pagination_controls(self):
        """Creates the Navigation buttons bar at the bottom."""
        for widget in self.nav_bar.winfo_children():
            widget.destroy()

        if self.total_pages <= 1:
            return

        self.nav_bar.grid_columnconfigure((0, 2), weight=1)
        self.nav_bar.grid_columnconfigure(1, weight=0)

        # First & Previous Buttons
        left_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        left_group.grid(row=0, column=0, sticky="e", padx=20)

        first_state = "normal" if self.current_page > 0 else "disabled"
        btn_first = ctk.CTkButton(left_group, text="« First", width=60, state=first_state, fg_color="gray30", command=self.go_to_first_page)
        btn_first.pack(side="left", padx=2)

        prev_state = "normal" if self.current_page > 0 else "disabled"
        btn_prev = ctk.CTkButton(
            left_group, text="‹ Prev", width=70, state=prev_state,
            command=self.prev_page, fg_color="gray30"
        )
        btn_prev.pack(side="left", padx=2)

        # Jump to Page & Page Indicator Buttons
        center_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        center_group.grid(row=0, column=1, sticky="n")

        ctk.CTkLabel(center_group, text="Page").pack(side="left", padx=2)

        self.jump_entry = ctk.CTkEntry(center_group, width=45, height=28, justify="center")
        self.jump_entry.insert(0, str(self.current_page + 1))
        self.jump_entry.pack(side="left", padx=5)
        self.jump_entry.bind("<Return>", self.jump_to_page)

        lbl_page = ctk.CTkLabel(center_group, text=f"of {self.total_pages}")
        lbl_page.pack(side="left", padx=2)

        # Next & Last Buttons
        right_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        right_group.grid(row=0, column=2, sticky="w", padx=20)

        next_state = "normal" if self.current_page < self.total_pages - 1 else "disabled"
        btn_next = ctk.CTkButton(right_group, text="Next ›", width=70, state=next_state,
                      command=self.next_page, fg_color="gray30")
        btn_next.pack(side="left", padx=2)

        last_state = "normal" if self.current_page < self.total_pages - 1 else "disabled"
        btn_last = ctk.CTkButton(right_group, text="Last »", width=60, state=last_state, fg_color="gray30",
                      command=self.go_to_last_page)
        btn_last.pack(side="left", padx=2)

        # Back to Top Button
        ctk.CTkButton(self.scroll_frame, text="▲ Back to Top", width=120, height=24,
                      fg_color="transparent", text_color="gray60", hover_color="gray25",
                      command=lambda: self.after(20,self.reset_scroll_to_top)
                      ).pack(pady=(0, 20))

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.load_transactions()
            if self.current_page == self.total_pages - 1:
                self.reset_scroll_to_top()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_transactions()

    def go_to_first_page(self):
        if self.current_page != 0:
            self.current_page = 0
            self.load_transactions()

    def go_to_last_page(self):
        last_page = max(0, self.total_pages - 1)
        if self.current_page != last_page:
            self.current_page = last_page
            self.load_transactions()
            self.reset_scroll_to_top()

    def reset_scroll_to_top(self):
        """Forces the canvas back to coordinate 0."""
        self.update_idletasks()
        if hasattr(self.scroll_frame, "_parent_canvas"):
            # noinspection PyProtectedMember
            self.scroll_frame._parent_canvas.yview_moveto(0)

    def jump_to_page(self, event=None):
        try:
            target = int(self.jump_entry.get()) - 1  # UI is 1-indexed
            if 0 <= target < self.total_pages:
                self.current_page = target
                self.load_transactions()
                if self.current_page == self.total_pages - 1:
                    self.reset_scroll_to_top()
            else:
                # Reset entry if number is out of bounds
                self.jump_entry.delete(0, "end")
                self.jump_entry.insert(0, str(self.current_page + 1))
        except ValueError:
            self.jump_entry.delete(0, "end")
            self.jump_entry.insert(0, str(self.current_page + 1))

    def open_add_expense(self):
        AddExpenseWindow(self, self.manager)


if __name__ == "__main__":
    app = FinanceApp()
    app.mainloop()