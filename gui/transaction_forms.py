import customtkinter as ctk
import datetime
from database.models import (
    Currency, Project, Category, Vendor,
    PaymentMethod, Account, Stream, Payer
)
from gui.widgets import SearchableComboBox, ToolTip
from gui.dialogs import open_calendar


class BaseTransactionWindow(ctk.CTkToplevel):
    def __init__(self, parent, manager, title, transaction_data = None, db_session = None):
        super().__init__(parent)
        self.title(title)
        self.db_session = db_session
        self.center_relative_to_parent(width=450, height=585)

        self.minsize(450, 585)
        self.maxsize(450, 585)
        self.manager = manager
        self.transaction_data = transaction_data
        self.is_edit_mode = transaction_data is not None and transaction_data.get("id") is not None
        self.mem = self.manager.last_used.copy()
        if transaction_data:
            self.mem.update(transaction_data)

        self.after(50, lambda: self.attributes('-topmost', True))
        self.after(75, lambda: self.attributes('-topmost', False))
        self.after(100, self.force_focus)

        self.grid_columnconfigure(0, weight=0, minsize=120)
        self.grid_columnconfigure(1, weight=1)

        # 1. Variables & Placeholders
        self.amount_placeholder = "Amount (e.g. 15.50)"
        self.desc_placeholder = "Description (Optional)"
        self.fx_placeholder = "Rate (e.g. 1.15)"
        self.session_time = datetime.datetime.now().strftime("%H:%M:%S")

        mem_date = self.mem.get("date", "")
        if " " in mem_date:
            initial_date = mem_date
        else:
            initial_date = f"{mem_date} {self.session_time}"

        self.currency_var = ctk.StringVar(value=self.mem.get("currency", "EUR"))
        self.date_var = ctk.StringVar(value=initial_date)
        self.project_var = ctk.StringVar(value=self.mem.get("project", ""))

        self.cal_window = None
        self.fx_tooltip = None
        self._val_timer = None
        self.tab_widgets = None

        # 2. Create Shared Widgets (Top & Bottom)
        self.title_lbl = ctk.CTkLabel(self, text=title, font=("JetBrains Mono", 20, "bold"))

        self.lbl_amount = ctk.CTkLabel(self, text="Amount", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.amount_entry = ctk.CTkEntry(self)

        currencies = [c.code for c in
                      self.db_session.query(Currency).filter_by(active_bool=True).order_by(Currency.code.asc()).all()]
        self.lbl_currency = ctk.CTkLabel(self, text="Currency", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.currency_menu = ctk.CTkOptionMenu(self, values=currencies, variable=self.currency_var,
                                               command=self.on_currency_change)

        self.lbl_fx = ctk.CTkLabel(self, text="Exchange Rate", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.fx_entry = ctk.CTkEntry(self)

        self.lbl_date = ctk.CTkLabel(self, text="Date & Time", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.date_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.date_entry = ctk.CTkEntry(self.date_frame, textvariable=self.date_var, width=150)
        self.today_btn = ctk.CTkButton(self.date_frame, text="T", width=30, command=lambda: self.set_relative_date(0))
        self.yesterday_btn = ctk.CTkButton(self.date_frame, text="Y", width=30, command=lambda: self.set_relative_date(1))
        self.date_btn = ctk.CTkButton(self.date_frame, text="📅", width=40, command=lambda: open_calendar(self, self.date_var, include_time=True))

        self.lbl_desc = ctk.CTkLabel(self, text="Description", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.desc_entry = ctk.CTkEntry(self)

        projects = [p.name for p in self.db_session.query(Project).filter_by(active_bool=True).order_by(Project.name.asc()).all()]
        self.lbl_project = ctk.CTkLabel(self, text="Project", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.project_menu = ctk.CTkOptionMenu(self, values=projects, variable=self.project_var)

        self.error_label = ctk.CTkLabel(self, text="", text_color="orange", font=("JetBrains Mono", 12))
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.clear_btn = ctk.CTkButton(self.btn_frame, text="Clear All", fg_color="gray30", command=self.clear_all)
        self.save_btn_ring = ctk.CTkFrame(self.btn_frame, fg_color="transparent", corner_radius=6)
        self.save_btn = ctk.CTkButton(self.save_btn_ring, text="Save", command=self.submit_data, fg_color="green", border_width=0)

    def center_relative_to_parent(self, width, height):
        """Calculates coordinates to center this window over its parent."""
        self.master.update_idletasks()

        p_width = self.master.winfo_width()
        p_height = self.master.winfo_height()
        p_x = self.master.winfo_rootx()
        p_y = self.master.winfo_rooty()

        center_x = p_x + (p_width // 2) - (width // 2)
        center_y = p_y + (p_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{center_x}+{center_y}")

    def finalize_initialization(self):
        """Subclasses call it after creating their specific widgets."""
        self.layout_shared_top()
        self.layout_shared_bottom()
        self.layout_specific_widgets()
        self.setup_bindings()

        self.update_fx_list()
        self.validate_form()

        self.setup_tab_order()

    # Layout Methods
    def layout_shared_top(self):
        self.title_lbl.grid(row=0, column=0, padx=20, pady=20)

        # Amount (Row 1)
        self.lbl_amount.grid(row=1, column=0, padx=(20, 10), pady=8, sticky="w")
        self.amount_entry.grid(row=1, column=1, padx=(0, 20), pady=8, sticky="ew")
        self._apply_entry_state(self.amount_entry, self.mem.get("amount"), self.amount_placeholder)

        # Currency (Row 2)
        self.lbl_currency.grid(row=2, column=0, padx=(20, 10), pady=8, sticky="w")
        self.currency_menu.grid(row=2, column=1, padx=(0, 20), pady=8, sticky="ew")

        # FX Rate (Row 3)
        self.fx_entry.insert(0, self.fx_placeholder)
        self.fx_entry.configure(text_color="gray")
        self.fx_tooltip = ToolTip(self.fx_entry, "Latest known rate will appear here")

    def layout_shared_bottom(self):
        # Date (Row 7)
        self.lbl_date.grid(row=7, column=0, padx=(20, 10), pady=8, sticky="w")
        self.date_frame.grid(row=7, column=1, padx=(0, 20), pady=8, sticky="ew")
        self.date_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.today_btn.pack(side="left", padx=2)
        self.yesterday_btn.pack(side="left", padx=2)
        self.date_btn.pack(side="left", padx=2)

        ToolTip(self.today_btn, "Set to Today")
        ToolTip(self.yesterday_btn, "Set to Yesterday")
        ToolTip(self.date_btn, "Open Calendar")

        # Description (Row 8)
        self.lbl_desc.grid(row=8, column=0, padx=(20, 10), pady=8, sticky="w")
        self.desc_entry.grid(row=8, column=1, padx=(0, 20), pady=8, sticky="ew")
        self._apply_entry_state(self.desc_entry, self.mem.get("desc"), self.desc_placeholder)

        # Project (Row 9)
        self.lbl_project.grid(row=9, column=0, padx=(20, 10), pady=8, sticky="w")
        self.project_menu.grid(row=9, column=1, padx=(0, 20), pady=8, sticky="ew")

        # Footer (Row 10 & 11)
        self.error_label.grid(row=10, column=0, columnspan=2, pady=(10, 5))
        self.btn_frame.grid(row=11, column=0, columnspan=2, pady=10)
        self.clear_btn.pack(side="left", padx=10)
        self.save_btn_ring.pack(side="left", padx=10)
        self.save_btn.pack(padx=2, pady=2)

    def setup_bindings(self):
        self.amount_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.amount_entry, self.amount_placeholder))
        self.amount_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.amount_entry, self.amount_placeholder))
        self.amount_entry.bind("<KeyRelease>", self.schedule_validation)

        self.fx_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.fx_entry, self.fx_placeholder))
        self.fx_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.fx_entry, self.fx_placeholder))
        self.fx_entry.bind("<KeyRelease>", lambda e: self._clear_fx_tooltip())
        self.fx_entry.bind("<KeyRelease>", self.schedule_validation, add="+")

        self.desc_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.desc_entry, self.desc_placeholder))
        self.desc_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.desc_entry, self.desc_placeholder))

        self.save_btn.bind("<FocusIn>", self._save_btn_focus_in)
        self.save_btn.bind("<FocusOut>", self._save_btn_focus_out)
        self.save_btn.bind("<Return>", self._save_btn_enter)

        self.currency_var.trace_add("write", self._handle_currency_change)
        self.date_var.trace_add("write", self._handle_date_change)

    def _save_btn_focus_in(self, _event):
        """Shows a bright border when the button receives keyboard focus."""
        if self.save_btn.cget("state") == "normal":
            self.save_btn_ring.configure(fg_color="white")

    def _save_btn_focus_out(self, _event):
        """Hides the border when focus moves away."""
        self.save_btn_ring.configure(fg_color="transparent")

    def _save_btn_enter(self, _event):
        """Executes the save command if the user hits Enter while focused."""
        if self.save_btn.cget("state") == "normal":
            self.submit_data()
            return "break"
        else:
            return None

    def setup_tab_order(self):
        """Binds custom Tab traversal strictly enforcing visual layout order."""
        self.tab_widgets = self.get_tab_order()

        for w in self.tab_widgets:
            # noinspection PyProtectedMember
            target = w._entry if hasattr(w, '_entry') else w

            target.bind("<Tab>", lambda e, widget=w: self._handle_tab(e, widget, 1), add="+")
            target.bind("<Shift-Tab>", lambda e, widget=w: self._handle_tab(e, widget, -1), add="+")

    def _handle_tab(self, _event, widget, direction):
        """
        Forces sequential focus.
        Automatically skips hidden widgets.
        """
        try:
            start_idx = self.tab_widgets.index(widget)
        except ValueError:
            return "break"

        idx = (start_idx + direction) % len(self.tab_widgets)
        while idx != start_idx:
            w = self.tab_widgets[idx]
            # noinspection PyProtectedMember
            target = w._entry if hasattr(w, '_entry') else w

            if target.winfo_ismapped():
                state = "normal"
                try:
                    state = w.cget("state")
                except:
                    pass

                if state != "disabled":
                    # noinspection PyProtectedMember
                    focus_target = w._entry if hasattr(w, '_entry') else w
                    focus_target.focus()
                    return "break"

            idx = (idx + direction) % len(self.tab_widgets)

        return "break"

    # Shared Methods
    @staticmethod
    def _apply_placeholder(widget, placeholder):
        """Clears an entry, applies a placeholder, and styles it gray."""
        widget.delete(0, 'end')
        widget.insert(0, placeholder)
        widget.configure(text_color="gray")

    @staticmethod
    def _apply_entry_state(widget, value, placeholder):
        """Applies either injected data or a gray placeholder."""
        widget.delete(0, 'end')
        if value is not None and str(value).strip() != "":
            widget.insert(0, str(value))
            widget.configure(text_color="white")
        else:
            widget.insert(0, placeholder)
            widget.configure(text_color="gray")

    @staticmethod
    def _entry_focus_in(widget, placeholder):
        """Clears the placeholder and sets value color."""
        if widget.get() == placeholder:
            widget.delete(0, 'end')
            widget.configure(text_color="white")

    @staticmethod
    def _entry_focus_out(widget, placeholder):
        """Sets the placeholder and its color."""
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.configure(text_color="gray")

    def _clear_fx_tooltip(self):
        """Clears the 'Historical' tooltip if the user starts typing a manual rate."""
        if self.fx_entry.get() != self.fx_placeholder:
            self.fx_tooltip.text = "Manual rate entered"

    def _handle_date_change(self, *args):
        """Ensures correct execution sequence when the user changes the Date."""
        self.update_fx_list()
        if hasattr(self, 'error_label'):
            self.validate_form()

    def _handle_currency_change(self, *args):
        """Ensures correct execution sequence when the user changes the Currency."""
        self.update_fx_list()
        self.on_currency_change(self.currency_var.get())
        if hasattr(self, 'error_label'):
            self.validate_form()

    def force_focus(self):
        self.focus_force()
        self.lift()
        self.amount_entry.focus()

    def get_current_time_part(self):
        """Extracts the HH:MM:SS part from the current entry, falling back to session_time."""
        try:
            return self.date_var.get().split(" ")[1] if " " in self.date_var.get() else self.session_time
        except:
            return self.session_time

    def set_relative_date(self, days_ago):
        """
        Sets the date_var to Today (0) or Yesterday (1).
        Keeps the time.
        """
        active_time = self.get_current_time_part()
        target_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        self.date_var.set(f"{target_date.strftime('%Y-%m-%d')} {active_time}")

    def update_fx_list(self):
        """Refreshes FX rate based on currency and date."""
        selected_currency = self.currency_var.get()
        if selected_currency == "EUR":
            self.lbl_fx.grid_forget()
            self.fx_entry.grid_forget()
            return

        self.lbl_fx.grid(row=3, column=0, padx=(20, 10), pady=8, sticky="w")
        self.fx_entry.grid(row=3, column=1, padx=(0, 20), pady=8, sticky="ew")

        try:
            full_date = self.date_var.get()
            if not full_date or len(full_date) < 10: return

            injected_fx = self.mem.get("fx_rate")
            if injected_fx:
                self.fx_entry.delete(0, 'end')
                self.fx_entry.insert(0, str(injected_fx))
                self.fx_entry.configure(text_color="white", font=("JetBrains Mono", 13))
                self.fx_tooltip.text = "Injected rate from original transaction"
                self.mem["fx_rate"] = None
                return

            result = self.manager.get_historical_fx_rate(selected_currency, full_date)
            if result:
                self.fx_entry.delete(0, 'end')
                self.fx_entry.insert(0, str(result[0]))
                self.fx_entry.configure(text_color="white", font=("JetBrains Mono", 13))
                self.fx_tooltip.text = f"Suggested rate from: {result[1].strftime('%Y-%m-%d')}"
            else:
                self.fx_entry.delete(0, 'end')
                self.fx_entry.insert(0, self.fx_placeholder)
                self.fx_entry.configure(text_color="gray", font=("JetBrains Mono", 13))
                self.fx_tooltip.text = "No historical rate found."
        except Exception as e:
            print(f"FX Sync Error: {e}")

    @staticmethod
    def is_float(val):
        """Checks if a string can be a valid currency float."""
        try:
            float(val.replace(",", "."))
            return True
        except ValueError:
            return False

    @staticmethod
    def is_valid_date(val):
        """Checks if the date string matches the YYYY-MM-DD HH:MM format."""
        try:
            datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
            return True
        except ValueError:
            return False

    def clear_all(self):
        """Resets the form to default values."""
        self._apply_placeholder(self.amount_entry, self.amount_placeholder)
        self._apply_placeholder(self.desc_entry, self.desc_placeholder)

        self.currency_var.set("EUR")
        self.project_var.set("")
        self.date_var.set(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        self.clear_specific_fields()
        self.update_fx_list()
        self.force_focus()

    def schedule_validation(self, *args):
        """Debounces the validation until user is done typing."""
        if self._val_timer:
            self.after_cancel(self._val_timer)
        self._val_timer = self.after(500, self.validate_form)

    def validate_form(self, *args):
        """Checks if all required fields are filled to enable the Save button."""
        self.error_label.configure(text="", text_color="orange")
        self.save_btn.configure(state="normal", fg_color="green", text_color="white")

        amt_val = self.amount_entry.get()
        amt_ok = amt_val != self.amount_placeholder and amt_val.strip() != "" and self.is_float(amt_val)
        date_ok = self.is_valid_date(self.date_var.get())
        cur_ok = self.currency_var.get() != ""
        fx_val = self.fx_entry.get()
        fx_ok = self.currency_var.get() == "EUR" or (
                    fx_val != self.fx_placeholder and fx_val.strip() != "" and self.is_float(fx_val))

        if not (amt_ok and date_ok and cur_ok and fx_ok):
            self.save_btn.configure(state="disabled", fg_color="gray30", text_color="white")
            if not amt_ok:
                self.error_label.configure(text="⚠ Check Amount (must be a number)")
            elif not date_ok:
                self.error_label.configure(text="⚠ Check Date format (YYYY-MM-DD HH:MM:SS)")
            elif not fx_ok:
                self.error_label.configure(text="⚠ Check Exchange Rate (must be a number)")
            elif not cur_ok:
                self.error_label.configure(text="⚠ Select a valid Currency")
            return

        spec_ok, spec_err = self.validate_specific_fields()
        if not spec_ok:
            self.save_btn.configure(state="disabled", fg_color="gray30", text_color="white")
            self.error_label.configure(text=spec_err)
            return

        warn_msg, is_duplicate = self.get_warnings()
        if is_duplicate:
            self.save_btn.configure(fg_color="#EBCB8B", text_color="black")
            self.error_label.configure(text=warn_msg, text_color="orange")
        elif warn_msg:
            self.error_label.configure(text=warn_msg, text_color="#EBCB8B")

    def submit_data(self):
        """Invokes the finance manager to submit to DB."""
        try:
            amt = float(self.amount_entry.get().replace(",", "."))
            cur = self.currency_var.get()
            ts = datetime.datetime.strptime(self.date_var.get(), "%Y-%m-%d %H:%M:%S")
            fx_rate = None if cur == "EUR" else float(self.fx_entry.get().replace(",", "."))
            descr = "" if self.desc_entry.get() == self.desc_placeholder else self.desc_entry.get()
            proj = self.project_var.get()

            base_data = {
                "amount": amt, "currency_code": cur, "timestamp": ts,
                "exchange_rate": fx_rate, "description": descr, "project_name": proj
            }

            self.execute_db_submission(base_data)

            self.save_btn.configure(text="✔ Added!", fg_color="darkgreen", state="disabled")
            self.error_label.configure(text="Saved successfully", text_color="green")
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

    # Abstract Methods
    def layout_specific_widgets(self):
        pass

    def on_currency_change(self, selected_currency):
        pass

    def clear_specific_fields(self):
        pass

    def validate_specific_fields(self):
        return True, ""

    def get_tab_order(self):
        return []

    def get_warnings(self):
        return "", False

    def execute_db_submission(self, base_data):
        pass

class AddExpenseWindow(BaseTransactionWindow):
    def __init__(self, parent, manager, transaction_data=None, db_session=None):
        title = "Edit Expense" if transaction_data and transaction_data.get("id") else "New Expense"
        super().__init__(parent, manager, title, transaction_data, db_session=db_session)

        self.cat_placeholder = "Search or type Category..."
        self.ven_placeholder = "Search or type Vendor..."

        # Category
        self.lbl_category = ctk.CTkLabel(self, text="Category", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_categories = [c.name for c in
                               self.db_session.query(Category).filter_by(active_bool=True).order_by(Category.name.asc()).all()]
        self.category_combo = SearchableComboBox(self, placeholder=self.cat_placeholder, values=self.all_categories,
                                                 command=lambda _: self.validate_form())
        self.category_combo.inject_value(self.mem.get("category"))
        # noinspection PyProtectedMember
        self.category_combo._entry.bind("<KeyRelease>", self.schedule_validation, add="+")

        # Vendor
        self.lbl_vendor = ctk.CTkLabel(self, text="Vendor", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_vendors = [v.name for v in
                            self.db_session.query(Vendor).filter_by(active_bool=True).order_by(Vendor.name.asc()).all()]
        self.vendor_combo = SearchableComboBox(self, placeholder=self.ven_placeholder, values=self.all_vendors,
                                               command=lambda _: self.validate_form())
        self.vendor_combo.inject_value(self.mem.get("entity"))
        # noinspection PyProtectedMember
        self.vendor_combo._entry.bind("<KeyRelease>", self.schedule_validation, add="+")

        # Payment Method
        self.lbl_pm = ctk.CTkLabel(self, text="Payment Method", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.pm_menu = ctk.CTkOptionMenu(self, values=[])

        # Initialize PM list based on currency
        self.on_currency_change(self.mem["currency"])
        if self.mem["pm"] in self.pm_menu.cget("values"):
            self.pm_menu.set(self.mem["pm"])

        self.finalize_initialization()

    def layout_specific_widgets(self):
        self.lbl_category.grid(row=4, column=0, padx=(20, 10), pady=8, sticky="w")
        self.category_combo.grid(row=4, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.lbl_vendor.grid(row=5, column=0, padx=(20, 10), pady=8, sticky="w")
        self.vendor_combo.grid(row=5, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.lbl_pm.grid(row=6, column=0, padx=(20, 10), pady=8, sticky="w")
        self.pm_menu.grid(row=6, column=1, padx=(0, 20), pady=8, sticky="ew")

    def get_tab_order(self):
        return [
            self.amount_entry, self.currency_menu, self.fx_entry,
            self.category_combo, self.vendor_combo, self.pm_menu,
            self.date_entry, self.desc_entry, self.project_menu, self.save_btn
        ]

    def on_currency_change(self, selected_currency):
        """Filters Payment Methods based on the account's currency."""
        valid_pms = (
            self.db_session.query(PaymentMethod)
            .join(Account).filter(Account.currency_code == selected_currency, PaymentMethod.active_bool == True)
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

    def clear_specific_fields(self):
        self.category_combo.reset()
        self.vendor_combo.reset()
        self.on_currency_change("EUR")

    def validate_specific_fields(self):
        if self.pm_menu.get() in ["", "No valid PM found"]:
            return False, "⚠ Select a valid Payment Method"
        return True, ""

    def get_warnings(self):
        current_amt = float(self.amount_entry.get().replace(",", "."))
        current_category = self.category_combo.get().strip()
        current_vendor = self.vendor_combo.get().strip()

        exclude_id = self.transaction_data.get("id") if self.is_edit_mode and self.transaction_data else None

        is_duplicate = self.manager.check_for_duplicate(amount=current_amt, entity_name=current_vendor, date_str=self.date_var.get(), exclude_id=exclude_id)
        if is_duplicate:
            return "⚠ Potential duplicate detected!", True

        is_new_vendor = current_vendor not in self.all_vendors and current_vendor not in [self.ven_placeholder, ""]
        is_new_category = current_category not in self.all_categories and current_category not in [self.cat_placeholder, ""]

        if is_new_vendor and is_new_category: return "Notice: New Vendor & Category will be created.", False
        if is_new_vendor: return f"Notice: New Vendor '{current_vendor}' will be created.", False
        if is_new_category: return f"Notice: New Category '{current_category}' will be created.", False

        return "", False

    def execute_db_submission(self, base_data):
        cat = "" if self.category_combo.get().strip() == self.cat_placeholder else self.category_combo.get().strip()
        ven = "" if self.vendor_combo.get().strip() == self.ven_placeholder else self.vendor_combo.get().strip()
        pm = self.pm_menu.get()
        exp_id = self.transaction_data.get("id") if self.is_edit_mode and self.transaction_data else None

        self.manager.add_expense(
            **base_data,
            category_name=cat,
            vendor_name=ven,
            payment_method_name=pm,
            expense_id=exp_id
        )

class AddGainWindow(BaseTransactionWindow):
    def __init__(self, parent, manager, transaction_data=None, db_session=None):
        title = "Edit Gain" if transaction_data and transaction_data.get("id") else "New Gain"
        super().__init__(parent, manager, title, transaction_data, db_session=db_session)

        self.stream_placeholder = "Search or type Stream..."
        self.payer_placeholder = "Search or type Payer..."

        # Stream
        self.lbl_stream = ctk.CTkLabel(self, text="Stream", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_streams = [s.name for s in
                               self.db_session.query(Stream).filter_by(active_bool=True).order_by(Stream.name.asc()).all()]
        self.stream_combo = SearchableComboBox(self, placeholder=self.stream_placeholder, values=self.all_streams,
                                                 command=lambda _: self.validate_form())
        self.stream_combo.inject_value(self.mem.get("stream"))
        # noinspection PyProtectedMember
        self.stream_combo._entry.bind("<KeyRelease>", self.schedule_validation, add="+")

        # Payer
        self.lbl_payer = ctk.CTkLabel(self, text="Payer", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_payers = [p.name for p in
                            self.db_session.query(Payer).filter_by(active_bool=True).order_by(Payer.name.asc()).all()]
        self.payer_combo = SearchableComboBox(self, placeholder=self.payer_placeholder, values=self.all_payers,
                                               command=lambda _: self.validate_form())
        self.payer_combo.inject_value(self.mem.get("entity"))
        # noinspection PyProtectedMember
        self.payer_combo._entry.bind("<KeyRelease>", self.schedule_validation, add="+")

        # Account
        self.lbl_acc = ctk.CTkLabel(self, text="Account", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.acc_menu = ctk.CTkOptionMenu(self, values=[])

        # Initialize Account list based on currency
        self.on_currency_change(self.mem["currency"])
        if self.mem["acc"] in self.acc_menu.cget("values"):
            self.acc_menu.set(self.mem["acc"])

        self.finalize_initialization()

    def layout_specific_widgets(self):
        self.lbl_stream.grid(row=4, column=0, padx=(20, 10), pady=8, sticky="w")
        self.stream_combo.grid(row=4, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.lbl_payer.grid(row=5, column=0, padx=(20, 10), pady=8, sticky="w")
        self.payer_combo.grid(row=5, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.lbl_acc.grid(row=6, column=0, padx=(20, 10), pady=8, sticky="w")
        self.acc_menu.grid(row=6, column=1, padx=(0, 20), pady=8, sticky="ew")

    def get_tab_order(self):
        return [
            self.amount_entry, self.currency_menu, self.fx_entry,
            self.stream_combo, self.payer_combo, self.acc_menu,
            self.date_entry, self.desc_entry, self.project_menu, self.save_btn
        ]

    def on_currency_change(self, selected_currency):
        """Filters Accounts based on the selected currency."""
        valid_accounts = (
            self.db_session.query(Account)
            .filter(Account.currency_code == selected_currency, Account.active_bool == True)
            .order_by(Account.name.asc())
            .all()
        )
        acc_names = [a.name for a in valid_accounts]
        if acc_names:
            self.acc_menu.configure(values=acc_names)
            self.acc_menu.set(acc_names[0])
        else:
            self.acc_menu.configure(values=["No valid Account found"])
            self.acc_menu.set("No valid Account found")

    def clear_specific_fields(self):
        self.stream_combo.reset()
        self.payer_combo.reset()
        self.on_currency_change("EUR")

    def validate_specific_fields(self):
        if self.acc_menu.get() in ["", "No valid Account found"]:
            return False, "⚠ Select a valid Account"
        return True, ""

    def get_warnings(self):
        current_amt = float(self.amount_entry.get().replace(",", "."))
        current_stream = self.stream_combo.get().strip()
        current_payer = self.payer_combo.get().strip()

        exclude_id = self.transaction_data.get("id") if self.is_edit_mode and self.transaction_data else None

        is_duplicate = self.manager.check_for_duplicate(amount=current_amt, entity_name=current_payer, date_str=self.date_var.get(), transaction_type="gain", exclude_id=exclude_id)
        if is_duplicate:
            return "⚠ Potential duplicate detected!", True

        is_new_payer = current_payer not in self.all_payers and current_payer not in [self.payer_placeholder, ""]
        is_new_stream = current_stream not in self.all_streams and current_stream not in [self.stream_placeholder, ""]

        if is_new_payer and is_new_stream: return "Notice: New Payer & Stream will be created.", False
        if is_new_payer: return f"Notice: New Payer '{current_payer}' will be created.", False
        if is_new_stream: return f"Notice: New Stream '{current_stream}' will be created.", False

        return "", False

    def execute_db_submission(self, base_data):
        stream = "" if self.stream_combo.get().strip() == self.stream_placeholder else self.stream_combo.get().strip()
        payer = "" if self.payer_combo.get().strip() == self.payer_placeholder else self.payer_combo.get().strip()
        acc_id = self.db_session.query(Account).filter_by(name=self.acc_menu.get()).first().id
        g_id = self.transaction_data.get("id") if self.is_edit_mode and self.transaction_data else None

        self.manager.add_gain(
            **base_data,
            stream_name=stream,
            payer_name=payer,
            account_id=acc_id,
            gain_id=g_id
        )

class AddTransferWindow(BaseTransactionWindow):
    def __init__(self, parent, manager, transaction_data=None, db_session=None):
        self.db_session = db_session
        active_accounts = self.db_session.query(Account).filter_by(active_bool=True).order_by(Account.name.asc()).all()
        self.account_map = {acc.name: acc for acc in active_accounts}
        self.all_acc_names = list(self.account_map.keys())

        title = "Edit Transfer" if transaction_data and transaction_data.get("id") else "New Transfer"
        super().__init__(parent, manager, title, transaction_data, db_session=db_session)

        self.origin_acc = None
        self.dest_acc = None
        self.auto_mirror = True

        self.dest_amount_placeholder = "Received Amount (e.g. 15.50)"

        self.lbl_origin = ctk.CTkLabel(self, text="From Account", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.origin_menu = ctk.CTkOptionMenu(self, values=self.all_acc_names, command=self._sync_account_data)

        self.lbl_destination = ctk.CTkLabel(self, text="To Account", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.dest_menu = ctk.CTkOptionMenu(self, values=self.all_acc_names, command=self._sync_account_data)

        self.swap_btn = ctk.CTkButton(self, text="⇅ Swap", width=50, height=24, fg_color="transparent", text_color="gray60", hover_color="gray25", font=("JetBrains Mono", 12),
                                      command=self.swap_accounts)

        if len(self.all_acc_names) > 1:
            self.origin_menu.set(self.all_acc_names[0])
            self.dest_menu.set(self.all_acc_names[1])

        self.lbl_dest_amt = ctk.CTkLabel(self, text="Received Amount", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.dest_amount_entry = ctk.CTkEntry(self)

        if self.mem["orig_acc"] in self.origin_menu.cget("values"):
            self.origin_menu.set(self.mem["orig_acc"])

        if self.mem["dest_acc"] in self.dest_menu.cget("values"):
            self.dest_menu.set(self.mem["dest_acc"])

        self.finalize_initialization()
        self._sync_account_data()

    def layout_specific_widgets(self):
        self.minsize(450, 515)
        self.maxsize(450, 515)
        self.lbl_amount.configure(text="Sent Amount")
        self.lbl_currency.grid_forget()
        self.currency_menu.grid_forget()

        self.lbl_origin.grid(row=2, column=0, padx=(20, 10), pady=8, sticky="w")
        self.origin_menu.grid(row=2, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.swap_btn.grid(row=3, column=1, padx=(0, 20), pady=0, sticky="w")

        self.lbl_destination.grid(row=4, column=0, padx=(20, 10), pady=8, sticky="w")
        self.dest_menu.grid(row=4, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.lbl_dest_amt.grid(row=5, column=0, padx=(20, 10), pady=8, sticky="w")
        self.dest_amount_entry.grid(row=5, column=1, padx=(0, 20), pady=8, sticky="ew")
        self._apply_entry_state(self.dest_amount_entry, self.mem.get("dest_amount"), self.dest_amount_placeholder)

        self.lbl_project.grid_forget()
        self.project_menu.grid_forget()

    def get_tab_order(self):
        return [
            self.amount_entry, self.origin_menu, self.swap_btn,
            self.dest_menu, self.dest_amount_entry,
            self.date_entry, self.desc_entry, self.save_btn
        ]

    def _sync_account_data(self, _=None):
        """Prepares filtered account lists for Origin/Destination menus."""
        origin_name = self.origin_menu.get()
        dest_name = self.dest_menu.get()
        self.origin_acc = self.account_map.get(origin_name)
        self.dest_acc = self.account_map.get(dest_name)

        to_options = [n for n in self.all_acc_names if n != origin_name]
        self.dest_menu.configure(values=to_options)

        from_options = [n for n in self.all_acc_names if n != dest_name]
        self.origin_menu.configure(values=from_options)

        self.update_fx_list()
        self._handle_mirroring()
        self.validate_form()

    def update_fx_list(self):
        """Overrides base method to permanently hide the FX rate for transfers."""
        self.lbl_fx.grid_forget()
        self.fx_entry.grid_forget()

    def _handle_mirroring(self, _=None):
        """
        Runs if auto mirror is on.
        Mirrors the origin account value to the destination account value.
        Debounces validation.
        """
        if not self.origin_acc or not self.dest_acc or not self.auto_mirror:
            return

        if self.origin_acc.currency_code == self.dest_acc.currency_code:
            current_sent = self.amount_entry.get()
            self.dest_amount_entry.delete(0, 'end')

            if current_sent == self.amount_placeholder or current_sent == "":
                self.dest_amount_entry.insert(0, self.dest_amount_placeholder)
                self.dest_amount_entry.configure(text_color="gray")
            else:
                self.dest_amount_entry.insert(0, current_sent)
                self.dest_amount_entry.configure(text_color="white")
            self.schedule_validation()

    def _on_dest_manual_edit(self, _event):
        """Disables auto-mirroring once the user starts typing in the Received box."""
        if self.dest_amount_entry.get() != self.dest_amount_placeholder:
            self.auto_mirror = False
        self.schedule_validation()

    def setup_bindings(self):
        super().setup_bindings()

        self.amount_entry.bind("<KeyRelease>", self._handle_mirroring, add="+")

        self.dest_amount_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.dest_amount_entry, self.dest_amount_placeholder))
        self.dest_amount_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.dest_amount_entry, self.dest_amount_placeholder))
        self.dest_amount_entry.bind("<KeyRelease>", self._on_dest_manual_edit)

    def swap_accounts(self):
        """Swaps the selected origin and destination accounts."""
        curr_orig = self.origin_menu.get()
        curr_dest = self.dest_menu.get()

        self.origin_menu.set(curr_dest)
        self.dest_menu.set(curr_orig)

        self._sync_account_data()

    def clear_specific_fields(self):
        """Hook called by BaseTransactionWindow's clear_all()"""
        if len(self.all_acc_names) > 1:
            self.origin_menu.set(self.all_acc_names[0])
            self.dest_menu.set(self.all_acc_names[1])
        elif self.all_acc_names:
            self.origin_menu.set(self.all_acc_names[0])
            self.dest_menu.set(self.all_acc_names[0])

        self._apply_placeholder(self.dest_amount_entry, self.dest_amount_placeholder)

        self.auto_mirror = True
        self._sync_account_data()

    def validate_specific_fields(self):
        dest_val = self.dest_amount_entry.get()
        dest_ok = dest_val != self.dest_amount_placeholder and dest_val.strip() != "" and self.is_float(dest_val)

        if not dest_ok:
            return False, "⚠ Check Received Amount"

        return True, ""

    def get_warnings(self):
        """Checks if an identical transfer already exists for this date."""
        try:
            amt_orig = float(self.amount_entry.get().replace(",", "."))
            amt_dest = float(self.dest_amount_entry.get().replace(",", "."))
        except ValueError:
            return "", False

        if not self.origin_acc or not self.dest_acc:
            return "", False

        exclude_id = self.transaction_data.get("id") if self.is_edit_mode and self.transaction_data else None

        is_duplicate = self.manager.check_for_duplicate(
            amount=amt_orig,
            entity_name=None,
            date_str=self.date_var.get(),
            transaction_type="transfer",
            origin_id=self.origin_acc.id,
            destination_id=self.dest_acc.id,
            amount_dest=amt_dest,
            exclude_id=exclude_id
        )

        if is_duplicate:
            return "⚠ Potential duplicate detected!", True

        return "", False

    def execute_db_submission(self, base_data):
        dest_amt = float(self.dest_amount_entry.get().replace(",", "."))
        trf_id = self.transaction_data.get("id") if self.is_edit_mode and self.transaction_data else None

        self.manager.transfer_funds(
            origin_id=self.origin_acc.id,
            destination_id=self.dest_acc.id,
            amount_orig=base_data["amount"],
            amount_dest=dest_amt,
            desc=base_data["description"],
            ts=base_data["timestamp"],
            transfer_id=trf_id
        )