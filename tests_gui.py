import customtkinter as ctk
from models import (
    session, Account, Expense, Gain, Category,
    PaymentMethod, Vendor, Currency, Project
)
from sqlalchemy import desc
from tkcalendar import Calendar
import finance_manager, datetime


class SearchableComboBox(ctk.CTkComboBox):
    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.all_values = kwargs.get("values", [])

        # Bindings
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<KeyRelease>", self._on_key_release)
        self._entry.bind("<Down>", self._on_down_key)

        # # Initialize Placeholder State
        self.after(300, self._force_placeholder_startup)

    def _force_placeholder_startup(self):
        self.set(self.placeholder)
        self._entry.configure(foreground="gray")

    def _on_focus_in(self, _event):
        if self.get() == self.placeholder:
            self.set("")
            self._entry.configure(foreground="white")

    def _on_focus_out(self, _event):
        if self.get() == "":
            self.set(self.placeholder)
            self._entry.configure(foreground="gray")

    def _on_key_release(self, event):
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

    def _schedule(self, event=None):
        self.id = self.widget.after(self.delay, self.show_tip)

    def show_tip(self, event=None):
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

    def hide_tip(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class AddExpenseWindow(ctk.CTkToplevel):
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.title("Add New Expense")
        self.geometry("450x550")
        self.manager = manager

        # Ensure it stays on top and grabs focus
        self.after(100, self.force_focus)
        self.attributes('-topmost', False)

        self.grid_columnconfigure(0, weight=0, minsize=120)
        self.grid_columnconfigure(1, weight=1)

        # UI Form label
        ctk.CTkLabel(self, text="New Expense", font=("Arial", 20, "bold")).grid(row=0, column=0, pady=20)

        # Placeholders
        self.cat_placeholder = "Search or type Category..."
        self.ven_placeholder = "Search or type Vendor..."
        self.amount_placeholder = "Amount (e.g. 15.50)"
        self.desc_placeholder = "Description (Optional)"

        # Initial values
        # 1. Amount
        self.amount_entry = ctk.CTkEntry(self)
        self.amount_entry.insert(0, self.amount_placeholder)
        self.amount_entry.configure(text_color="gray")
        self.amount_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.amount_entry, self.amount_placeholder))
        self.amount_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.amount_entry, self.amount_placeholder))

        # 2. Currency (Dropdown)
        currencies = [c.code for c in session.query(Currency).filter_by(active_bool=True).order_by(Currency.code.asc()).all()]
        self.currency_var = ctk.StringVar(value="EUR")
        self.currency_menu = ctk.CTkOptionMenu(self, values=currencies, variable=self.currency_var, command=self.update_pm_list)

        # 3. Category (SearchableComboBox so we can find existing or type new ones)
        self.all_categories = [c.name for c in session.query(Category).filter_by(active_bool=True).order_by(Category.name.asc()).all()]
        self.category_combo = SearchableComboBox(self,placeholder=self.cat_placeholder,values=self.all_categories)

        # 4. Vendor (ditto)
        self.all_vendors = [v.name for v in session.query(Vendor).filter_by(active_bool=True).order_by(Vendor.name.asc()).all()]
        self.vendor_combo = SearchableComboBox(self, placeholder=self.ven_placeholder, values=self.all_vendors)

        # 5. Payment Method
        self.pm_menu = ctk.CTkOptionMenu(self, values=[])
        self.update_pm_list("EUR")

        # 6. Datetime
        self.cal_window = None
        date_frame = ctk.CTkFrame(self, fg_color="transparent")
        date_frame.grid(row=6, column=0, padx=20, pady=10, sticky="ew")
        date_frame.grid(row=6, column=1, padx=(0, 20), pady=8, sticky="ew")

        self.date_var = ctk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.date_entry = ctk.CTkEntry(date_frame, textvariable=self.date_var, width=150)
        self.date_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.today_btn = ctk.CTkButton(date_frame, text="T", width=30, command=lambda: self.set_relative_date(0))
        self.today_btn.pack(side="left", padx=2)

        self.yesterday_btn = ctk.CTkButton(date_frame, text="Y", width=30, command=lambda: self.set_relative_date(1))
        self.yesterday_btn.pack(side="left", padx=2)

        self.date_btn = ctk.CTkButton(date_frame, text="📅", width=40, command=self.open_calendar)
        self.date_btn.pack(side="left", padx=2)

        # 7. Description
        self.desc_entry = ctk.CTkEntry(self)
        self.desc_entry.insert(0, self.desc_placeholder)
        self.desc_entry.configure(text_color="gray")
        self.desc_entry.bind("<FocusIn>", lambda e: self._entry_focus_in(self.desc_entry, self.desc_placeholder))
        self.desc_entry.bind("<FocusOut>", lambda e: self._entry_focus_out(self.desc_entry, self.desc_placeholder))

        # 8. Project
        projects = [p.name for p in session.query(Project).filter_by(active_bool=True).order_by(Project.name.asc()).all()]
        self.project_var = ctk.StringVar(value="")
        self.project_menu = ctk.CTkOptionMenu(self, values=projects, variable=self.project_var)

        # Draw label + fields
        def add_row(label_text, widget, row_idx):
            lbl = ctk.CTkLabel(self, text=label_text, font=("Arial", 13, "bold"), anchor="w")
            lbl.grid(row=row_idx, column=0, padx=(20, 10), pady=8, sticky="w")
            widget.grid(row=row_idx, column=1, padx=(0, 20), pady=8, sticky="ew")

        add_row("Amount", self.amount_entry, 1)
        add_row("Currency", self.currency_menu, 2)
        add_row("Category", self.category_combo, 3)
        add_row("Vendor", self.vendor_combo, 4)
        add_row("Payment Method", self.pm_menu, 5)

        # Date container is special
        date_lbl = ctk.CTkLabel(self, text="Date & Time", font=("Arial", 13, "bold"), anchor="w")
        date_lbl.grid(row=6, column=0, padx=(20, 10), pady=8, sticky="w")

        add_row("Description", self.desc_entry, 7)
        add_row("Project", self.project_menu, 8)

        # Tooltips
        ToolTip(self.today_btn, "Set to Today")
        ToolTip(self.yesterday_btn, "Set to Yesterday")
        ToolTip(self.date_btn, "Open Calendar")

        # Clear All & Save Button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=9, column=0, columnspan=2, pady=30)
        self.clear_btn = ctk.CTkButton(btn_frame, text="Clear All", fg_color="gray30", command=self.clear_all)
        self.clear_btn.pack(side="left", padx=10)

        self.save_btn = ctk.CTkButton(btn_frame, text="Save Expense", command=self.submit_data, fg_color="green")
        self.save_btn.pack(side="left", padx=10)

    def _entry_focus_in(self, widget, placeholder):
        """Logic for Amount and Description placeholders on FocusIn."""
        if widget.get() == placeholder:
            widget.delete(0, 'end')
            widget.configure(text_color="white")

    def _entry_focus_out(self, widget, placeholder):
        """Logic for Amount and Description placeholders on FocusOut."""
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.configure(text_color="gray")

    def force_focus(self):
        self.focus_force()
        self.lift()
        self.amount_entry.focus()

    def open_calendar(self):
        """Pops up a calendar window to select a date."""
        if self.cal_window is not None and self.cal_window.winfo_exists():
            self.cal_window.deiconify()
            self.cal_window.lift()
            self.cal_window.focus_force()
            return
        self.cal_window = ctk.CTkToplevel(self)
        self.cal_window.title("Select Date")
        self.cal_window.attributes("-topmost", False)

        self.cal_window.after(10, lambda: ctk.set_appearance_mode("dark"))
        self.cal_window.after(90, lambda: force_focus(self.cal_window))

        # Standard Tkinter Calendar
        cal = Calendar(self.cal_window, selectmode='day',
                       year=datetime.datetime.now().year,
                       month=datetime.datetime.now().month,
                       day=datetime.datetime.now().day)
        cal.pack(pady=20, padx=10)

        def force_focus(window):
            window.focus_force()
            window.lift()

        def set_date():
            # Get date and append current time
            selected_date = cal.selection_get()
            now_time = datetime.datetime.now().strftime("%H:%M")
            self.date_var.set(f"{selected_date} {now_time}")
            self.cal_window.destroy()

        ctk.CTkButton(self.cal_window, text="Confirm", command=set_date).pack(pady=10)

    def clear_all(self):
        """Resets the form to default values."""
        self.amount_entry.delete(0, 'end')
        self.amount_entry.insert(0, self.amount_placeholder)
        self.amount_entry.configure(text_color="gray")
        self.desc_entry.delete(0, 'end')
        self.desc_entry.insert(0, self.desc_placeholder)
        self.desc_entry.configure(text_color="gray")

        # Reset SearchableComboBoxes to placeholders
        for combo in [self.category_combo, self.vendor_combo]:
            combo.set(combo.placeholder)
            combo._entry.configure(foreground="gray")

        # Reset Menus and Date
        self.currency_var.set("EUR")
        self.update_pm_list("EUR")
        self.date_var.set(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

        # Put focus back at the start
        self.force_focus()
        self.amount_entry.focus()

    def set_relative_date(self, days_ago):
        """Sets the date_var to Today (0) or Yesterday (1)."""
        target_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        formatted_date = target_date.strftime("%Y-%m-%d %H:%M")
        self.date_var.set(formatted_date)

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

    def submit_data(self):
        try:
            # Basic Validation
            amt = float(self.amount_entry.get().replace(",", "."))
            cat = self.category_combo.get()
            ven = self.vendor_combo.get()
            pm = self.pm_menu.get()
            cur = self.currency_var.get()
            descr = self.desc_entry.get()

            # Execute the manager
            self.manager.add_expense(
                amount=amt,
                currency_code=cur,
                category_name=cat,
                vendor_name=ven,
                payment_method_name=pm,
                description=descr,
                timestamp=datetime.datetime.now()
            )

            print(f"Success: Added {amt} to {ven}")
            self.destroy()  # Close window
        except ValueError:
            print("Error: Invalid amount entered.")

class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Venn Ledger 2026")
        self.geometry("1100x700")
        ctk.set_appearance_mode("dark")
        self.manager = finance_manager.TransactionManager(session)

        # 1. Grid Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 2. Sidebar (Accounts & Quick Actions)
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo = ctk.CTkLabel(self.sidebar, text="FINANCE", font=("Arial", 24, "bold"))
        self.logo.pack(pady=30, padx=20)

        self.add_btn = ctk.CTkButton(self.sidebar, text="+ Add Expense", command=self.open_add_expense)
        self.add_btn.pack(pady=20, padx=20)

        # Account List
        self.refresh_accounts()

        # 3. Main Content Area
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.header = ctk.CTkLabel(self.main_frame, text="Recent Transactions", font=("Arial", 22, "bold"))
        self.header.pack(anchor="w", pady=(0, 20))

        # 4. Scrollable Table
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="History")
        self.scroll_frame.pack(fill="both", expand=True)

        self.load_transactions()

    def refresh_accounts(self):
        """Builds the account buttons in the sidebar."""
        accounts = session.query(Account).order_by(Account.name.asc()).all()
        for acc in accounts:
            acc_text = f"{acc.name}\n{acc.balance:,.2f} {acc.currency_code}"
            btn = ctk.CTkButton(self.sidebar, text=acc_text, fg_color="gray20", hover_color="gray30")
            btn.pack(pady=5, padx=20, fill="x")

    def load_transactions(self):
        """Fetches transactions and renders them as rows."""
        # For performance in CustomTkinter, let's start with the last 100
        # We can add 'Load More' later.
        expenses = session.query(Expense).order_by(desc(Expense.timestamp)).limit(100).all()

        for exp in expenses:
            row = ctk.CTkFrame(self.scroll_frame, fg_color="gray15")
            row.pack(fill="x", pady=2, padx=5)

            # Row Content
            date_str = exp.timestamp.strftime("%Y-%m-%d")
            ctk.CTkLabel(row, text=date_str, width=100).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"{exp.vendor.name}", width=150, anchor="w").pack(side="left", padx=10)
            ctk.CTkLabel(row, text=f"{exp.category.name}", width=120).pack(side="left", padx=10)

            # Highlight amount in red
            amt_text = f"-{exp.amount:,.2f} {exp.currency_code}"
            ctk.CTkLabel(row, text=amt_text, text_color="#FF6B6B", font=("Arial", 12, "bold")).pack(side="right",
                                                                                                    padx=10)

    def open_add_expense(self):
        AddExpenseWindow(self, self.manager)


if __name__ == "__main__":
    app = FinanceApp()
    app.mainloop()