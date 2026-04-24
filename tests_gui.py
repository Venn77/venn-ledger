import customtkinter as ctk
from models import (
    session, Account, Expense, Gain, Category,
    PaymentMethod, Vendor, Currency, Project,
    Transfer, Payer, Stream, ExchangeRate
)
from ai_parser import chunk_file_by_day, get_structured_data
from sqlalchemy import (
    desc, or_, func, column, literal_column,
    union_all, asc, case
)
from sqlalchemy.orm import aliased
from sqlalchemy.exc import IntegrityError
from tkcalendar import Calendar
from customtkinter import filedialog
from io_utils import extract_exchange_rate
import finance_manager, datetime, json, os, threading


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

class SimpleDataDialog(ctk.CTkToplevel):
    """Generic popup form for creating/editing Master Data."""
    def __init__(self, parent, title, initial_name="", initial_desc="", has_desc=False, on_submit=None):
        super().__init__(parent)
        self.title(title)

        height = 220 if has_desc else 160
        width = 300
        self.geometry(f"{width}x{height}")
        self.attributes("-topmost", True)
        self.grab_set()

        self.on_submit = on_submit
        self.has_desc = has_desc

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        ctk.CTkLabel(self, text="Name:", font=("JetBrains Mono", 12, "bold")).pack(pady=(15, 0))
        self.name_entry = ctk.CTkEntry(self, width=240)
        self.name_entry.insert(0, initial_name)
        self.name_entry.pack(pady=(5, 10))

        if self.has_desc:
            ctk.CTkLabel(self, text="Description:", font=("JetBrains Mono", 12, "bold")).pack()
            self.desc_entry = ctk.CTkEntry(self, width=240)
            self.desc_entry.insert(0, initial_desc)
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
    """Custom popup for creating Currencies (requires a 3-letter code)."""
    def __init__(self, parent, title, initial_code="", initial_name="", is_edit=False, on_submit=None):
        super().__init__(parent)
        self.title(title)
        height = 220
        width = 300
        self.geometry(f"{width}x{height}")
        self.attributes("-topmost", True)
        self.grab_set()

        self.on_submit = on_submit

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        ctk.CTkLabel(self, text="Currency Code (3 Letters):", font=("JetBrains Mono", 11, "bold")).pack(pady=(15, 0))
        self.code_entry = ctk.CTkEntry(self, width=240)
        self.code_entry.insert(0, initial_code)
        if is_edit:
            self.code_entry.configure(state="disabled")
        self.code_entry.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Currency Name:", font=("JetBrains Mono", 11, "bold")).pack()
        self.name_entry = ctk.CTkEntry(self, width=240)
        self.name_entry.insert(0, initial_name)
        self.name_entry.pack(pady=(2, 10))

        self.err_lbl = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 10), height=15)
        self.err_lbl.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)

        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=self.destroy).pack(side="left",
                                                                                                        padx=10)
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self.submit).pack(side="left", padx=10)

    def submit(self):
        code_val = self.code_entry.get().strip().upper()
        name_val = self.name_entry.get().strip()

        if len(code_val) != 3:
            self.err_lbl.configure(text="Code must be exactly 3 letters.")
            return
        if not name_val:
            self.err_lbl.configure(text="Name cannot be empty.")
            return

        if self.on_submit:
            success, msg = self.on_submit(code_val, name_val)
            if success:
                self.destroy()
            else:
                self.err_lbl.configure(text=msg)

class FXDialog(ctk.CTkToplevel):
    """Custom popup for adding a new Exchange Rate."""
    def __init__(self, parent, active_currencies, on_submit=None):
        super().__init__(parent)
        self.title("New Exchange Rate")
        height = 340
        width = 300
        self.geometry(f"{width}x{height}")
        self.attributes("-topmost", True)
        self.grab_set()

        self.on_submit = on_submit

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        ctk.CTkLabel(self, text="Select Currency:", font=("JetBrains Mono", 11, "bold")).pack(pady=(15, 0))
        self.curr_combo = ctk.CTkComboBox(self, values=active_currencies, width=240)
        self.curr_combo.pack(pady=(2, 5))

        ctk.CTkLabel(self, text="FX Multiplier (e.g. 1850.0):", font=("JetBrains Mono", 11, "bold")).pack()
        self.rate_entry = ctk.CTkEntry(self, width=240)
        self.rate_entry.pack(pady=(2, 5))

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

    def submit(self):
        curr_val = self.curr_combo.get()
        try:
            rate_val = float(self.rate_entry.get().replace(",", "."))
            if rate_val <= 0: raise ValueError
        except ValueError:
            self.err_lbl.configure(text="Rate must be a positive number.")
            return

        date_val = self.date_entry.get().strip()
        time_val = self.time_entry.get().strip()

        try:
            dt_str = f"{date_val} {time_val}"
            timestamp_val = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            self.err_lbl.configure(text="Invalid date/time format.")
            return

        if self.on_submit:
            success, msg = self.on_submit(curr_val, rate_val, timestamp_val)
            if success:
                self.destroy()
            else:
                self.err_lbl.configure(text=msg)

class AccountDialog(ctk.CTkToplevel):
    def __init__(self, parent, active_currencies, initial_name="", initial_desc="", initial_curr="", initial_bal="0.00",
                 is_edit=False, on_submit=None):
        super().__init__(parent)
        self.title("Edit Account" if is_edit else "New Account")
        width = 320
        height = 350
        self.geometry(f"{width}x{height}")
        self.attributes("-topmost", True)
        self.grab_set()
        self.on_submit = on_submit

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

        ctk.CTkLabel(self, text="Account Name:", font=("JetBrains Mono", 11, "bold")).pack(pady=(15, 0))
        self.name_entry = ctk.CTkEntry(self, width=260)
        self.name_entry.insert(0, initial_name)
        self.name_entry.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Description:", font=("JetBrains Mono", 11, "bold")).pack()
        self.desc_entry = ctk.CTkEntry(self, width=260)
        self.desc_entry.insert(0, initial_desc)
        self.desc_entry.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Currency:", font=("JetBrains Mono", 11, "bold")).pack()
        self.curr_combo = ctk.CTkComboBox(self, values=active_currencies, width=260)
        if initial_curr: self.curr_combo.set(initial_curr)
        if is_edit: self.curr_combo.configure(state="disabled")
        self.curr_combo.pack(pady=(2, 10))

        ctk.CTkLabel(self, text="Initial Balance:", font=("JetBrains Mono", 11, "bold")).pack()
        self.bal_entry = ctk.CTkEntry(self, width=260)
        self.bal_entry.insert(0, initial_bal)
        if is_edit: self.bal_entry.configure(state="disabled")
        self.bal_entry.pack(pady=(2, 10))

        self.err_lbl = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 10), height=15)
        self.err_lbl.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=5)
        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=self.destroy).pack(side="left",
                                                                                                        padx=10)
        ctk.CTkButton(btn_frame, text="Save", width=80, command=self.submit).pack(side="left", padx=10)

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
        self.title("Payment Method")
        width = 300
        height = 220
        self.geometry(f"{width}x{height}")
        self.attributes("-topmost", True)
        self.grab_set()
        self.on_submit = on_submit

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

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

class SimpleMasterDataGrid(ctk.CTkFrame):
    """Renders a dynamic grid for simple CRUD operations on db."""
    def __init__(self, parent, db_session, model, title, has_desc=False):
        super().__init__(parent, fg_color="transparent")
        self.session = db_session
        self.model = model
        self.title = title
        self.has_desc = has_desc

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header_frame, text=title, font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header_frame, text="+ Add New", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self):
        for widget in self.scroll.winfo_children():
            widget.destroy()

        items = self.session.query(self.model).order_by(self.model.name).all()
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            name_lbl = ctk.CTkLabel(row, text=item.name, width=150, anchor="w", font=("JetBrains Mono", 12, "bold"))
            name_lbl.pack(side="left", padx=10, pady=8)

            if self.has_desc and hasattr(item, 'description'):
                desc_text = (item.description[:30] + '...') if item.description and len(
                    item.description) > 30 else item.description
                ctk.CTkLabel(row, text=desc_text or "", width=150, anchor="w", text_color="gray60").pack(side="left",
                                                                                                         padx=10)

            # Action Buttons
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            toggle_text = "Deactivate" if item.active_bool else "Activate"
            toggle_color = "#b13e3e" if item.active_bool else "#1f538d"

            ctk.CTkButton(btn_frame, text=toggle_text, width=80, height=24, fg_color=toggle_color,
                          command=lambda i=item.id: self.toggle_status(i)).pack(side="right", padx=2)

            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit_item(i)).pack(side="right", padx=2)

            # Status Label
            status_text = "Active" if item.active_bool else "Inactive"
            status_color = "#4CD964" if item.active_bool else "gray50"
            ctk.CTkLabel(row, text=status_text, text_color=status_color, width=60, font=("JetBrains Mono", 11)).pack(
                side="right", padx=10)

    def toggle_status(self, item_id):
        item = self.session.get(self.model, item_id)
        if item:
            item.active_bool = not item.active_bool
            self.session.commit()
            self.load_data()

    def add_new(self):
        def _save(new_name, new_desc):
            try:
                existing_item = self.session.query(self.model).filter_by(name=new_name).first()

                if existing_item:
                    if not existing_item.active_bool:
                        existing_item.active_bool = True
                        if self.has_desc and hasattr(existing_item, 'description'):
                            existing_item.description = new_desc
                        self.session.commit()
                        self.load_data()
                        return True, ""
                    else:
                        return False, f"'{new_name}' already exists and is active."

                if self.has_desc:
                    new_item = self.model(name=new_name, description=new_desc)
                else:
                    new_item = self.model(name=new_name)

                self.session.add(new_item)
                self.session.commit()
                self.load_data()
                return True, ""
            except IntegrityError:
                self.session.rollback()
                return False, "Database error."
            except Exception as e:
                self.session.rollback()
                return False, str(e)

        SimpleDataDialog(self, f"Add {self.model.__name__}", has_desc=self.has_desc, on_submit=_save)

    def edit_item(self, item):
        initial_desc = item.description if self.has_desc and hasattr(item, 'description') else ""

        def _update(new_name, new_desc):
            try:
                existing_item = self.session.query(self.model).filter_by(name=new_name).first()
                if existing_item and existing_item.id != item.id:
                    status = "active" if existing_item.active_bool else "deactivated"
                    return False, f"Name already used by a {status} item."

                item.name = new_name
                if self.has_desc and hasattr(item, 'description'):
                    item.description = new_desc

                self.session.commit()
                self.load_data()
                return True, ""
            except IntegrityError:
                self.session.rollback()
                return False, "Database error."
            except Exception as e:
                self.session.rollback()
                return False, str(e)

        SimpleDataDialog(self, f"Edit {self.model.__name__}", initial_name=item.name, initial_desc=initial_desc,
                         has_desc=self.has_desc, on_submit=_update)

class CurrencyGrid(ctk.CTkFrame):
    """Renders a dynamic grid for CRUD operations on currencies table."""
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.session = db_session

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Currencies", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add Currency", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self):
        for widget in self.scroll.winfo_children(): widget.destroy()
        items = self.session.query(Currency).order_by(Currency.code).all()
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=item.code, width=40, font=("JetBrains Mono", 12, "bold"), text_color="#5AC8FA").pack(
                side="left", padx=(10, 5), pady=8)
            ctk.CTkLabel(row, text=item.name, width=150, anchor="w", font=("JetBrains Mono", 11)).pack(side="left",
                                                                                                       padx=5)

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            toggle_text, toggle_color = ("Deactivate", "#b13e3e") if item.active_bool else ("Activate", "#1f538d")
            state = "disabled" if item.code == "EUR" else "normal"
            ctk.CTkButton(btn_frame, text=toggle_text, width=80, height=24, fg_color=toggle_color, state=state,
                          command=lambda i=item.code: self.toggle(i)).pack(side="right", padx=2)
            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit(i)).pack(side="right", padx=2)

            status = "Active" if item.active_bool else "Inactive"
            color = "#4CD964" if item.active_bool else "gray50"
            ctk.CTkLabel(row, text=status, text_color=color, width=60, font=("JetBrains Mono", 11)).pack(side="right",
                                                                                                         padx=10)

    def toggle(self, code):
        item = self.session.get(Currency, code)
        item.active_bool = not item.active_bool
        self.session.commit()
        self.load_data()

    def add_new(self):
        def _save(code, name):
            if self.session.get(Currency, code): return False, "Currency Code already exists."
            self.session.add(Currency(code=code, name=name))
            self.session.commit()
            self.load_data()
            return True, ""

        CurrencyDialog(self, "Add Currency", on_submit=_save)

    def edit(self, item):
        def _update(code, name):
            item.name = name
            self.session.commit()
            self.load_data()
            return True, ""

        CurrencyDialog(self, "Edit Currency Name", initial_code=item.code, initial_name=item.name, is_edit=True,
                       on_submit=_update)

class ExchangeRateGrid(ctk.CTkFrame):
    """Renders a dynamic grid for CRUD operations on exchange_rates table."""
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.session = db_session

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Exchange Rates", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Log New Rate", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self):
        for widget in self.scroll.winfo_children(): widget.destroy()
        rates = self.session.query(ExchangeRate).filter(ExchangeRate.currency_code != "EUR").order_by(
            ExchangeRate.timestamp.desc()).limit(500).all()
        for r in rates:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=r.currency_code, width=40, font=("JetBrains Mono", 12, "bold"),
                         text_color="#5AC8FA").pack(side="left", padx=(10, 5), pady=8)
            ctk.CTkLabel(row, text=f"Rate: {r.fx_multiplier:,.4f}", width=120, anchor="w",
                         font=("JetBrains Mono", 11, "bold")).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=r.timestamp.strftime("%Y-%m-%d %H:%M"), text_color="gray50",
                         font=("JetBrains Mono", 10)).pack(side="left", padx=10)

            ctk.CTkButton(row, text="✕", width=30, height=24, fg_color="transparent", text_color="gray50",
                          hover_color="#8b2525",
                          command=lambda i=r.id: self.delete(i)).pack(side="right", padx=10)

    def delete(self, rate_id):
        rate = self.session.get(ExchangeRate, rate_id)
        context_text = f"[{rate.timestamp.strftime('%Y-%m-%d')}] {rate.currency_code} | {rate.fx_multiplier}" if rate else ""
        popup = ctk.CTkToplevel(self)
        popup.title("Confirm")
        width = 250
        height = 150
        popup.geometry(f"{width}x{height}")
        popup.attributes("-topmost", True)
        popup.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        popup.geometry(f"+{x}+{y}")

        ctk.CTkLabel(popup, text="Delete this exchange rate?", font=("JetBrains Mono", 12)).pack(pady=(20, 5))
        ctk.CTkLabel(popup, text=context_text, font=("JetBrains Mono", 11), text_color="orange").pack(pady=(0, 15))

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack()

        def _confirm():
            if rate:
                self.session.delete(rate)
                self.session.commit()
                self.load_data()
            popup.destroy()

        ctk.CTkButton(btn_frame, text="Cancel", width=70, fg_color="gray40", command=popup.destroy).pack(side="left",
                                                                                                         padx=5)
        ctk.CTkButton(btn_frame, text="Delete", width=70, fg_color="#8b2525", hover_color="#611a1a",
                      command=_confirm).pack(side="left", padx=5)

    def add_new(self):
        act_currencies = [c.code for c in self.session.query(Currency).filter_by(active_bool=True).all() if
                        c.code != "EUR"]
        if not act_currencies:
            return

        def _save(code, rate, timestamp):
            self.session.add(ExchangeRate(currency_code=code, fx_multiplier=rate, timestamp=timestamp))
            self.session.commit()
            self.load_data()
            return True, ""

        FXDialog(self, active_currencies=act_currencies, on_submit=_save)

class AccountGrid(ctk.CTkFrame):
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.session = db_session
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Accounts", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add Account", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self):
        for widget in self.scroll.winfo_children(): widget.destroy()
        items = self.session.query(Account).order_by(Account.name).all()
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=item.name, width=150, anchor="w", font=("JetBrains Mono", 12, "bold")).pack(
                side="left", padx=10, pady=8)
            ctk.CTkLabel(row, text=f"{item.balance:,.2f} {item.currency_code}", width=100, anchor="w",
                         text_color="#5AC8FA", font=("JetBrains Mono", 11, "bold")).pack(side="left", padx=5)

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)
            t_text, t_color = ("Deactivate", "#b13e3e") if item.active_bool else ("Activate", "#1f538d")

            ctk.CTkButton(btn_frame, text=t_text, width=80, height=24, fg_color=t_color,
                          command=lambda i=item: self.toggle(i)).pack(side="right", padx=2)
            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit(i)).pack(side="right", padx=2)

            status, color = ("Active", "#4CD964") if item.active_bool else ("Inactive", "gray50")
            ctk.CTkLabel(row, text=status, text_color=color, width=60, font=("JetBrains Mono", 11)).pack(side="right",
                                                                                                         padx=10)

    def toggle(self, acc):
        if acc.active_bool and acc.balance != 0:
            popup = ctk.CTkToplevel(self)
            popup.title("Warning")
            popup.geometry("350x180")
            popup.attributes("-topmost", True)
            popup.grab_set()
            self.update_idletasks()
            popup.geometry(f"+{self.winfo_x() + 100}+{self.winfo_y() + 100}")

            msg = f"Account '{acc.name}' has a balance of {acc.balance:,.2f}.\n\nDeactivating it hides it from menus and\ndeactivates its Payment Methods, but the\nbalance will STILL count toward Net Worth.\n\nProceed?"
            ctk.CTkLabel(popup, text=msg, font=("JetBrains Mono", 11)).pack(pady=15)

            def _confirm():
                self._execute_toggle(acc)
                popup.destroy()

            bf = ctk.CTkFrame(popup, fg_color="transparent")
            bf.pack()
            ctk.CTkButton(bf, text="Cancel", width=80, fg_color="gray40", command=popup.destroy).pack(side="left",
                                                                                                      padx=10)
            ctk.CTkButton(bf, text="Deactivate", width=80, fg_color="#b13e3e", command=_confirm).pack(side="left",
                                                                                                      padx=10)
        else:
            self._execute_toggle(acc)

    def _execute_toggle(self, acc):
        acc.active_bool = not acc.active_bool
        if not acc.active_bool:
            for pm in acc.payment_methods: pm.active_bool = False
        self.session.commit()
        self.load_data()

        self.event_generate("<<DataChanged>>")

    def add_new(self):
        currencies = [c.code for c in self.session.query(Currency).filter_by(active_bool=True).all()]
        if not currencies: return

        def _save(name, descr, curr, bal):
            if self.session.query(Account).filter_by(name=name).first(): return False, "Name already exists."
            self.session.add(Account(name=name, description=descr, currency_code=curr, balance=bal, initial_balance=bal))
            self.session.commit()
            self.load_data()
            return True, ""

        AccountDialog(self, currencies, on_submit=_save)

    def edit(self, acc):
        def _update(name, descr):
            existing = self.session.query(Account).filter_by(name=name).first()
            if existing and existing.id != acc.id: return False, "Name in use."
            acc.name = name
            acc.description = descr
            self.session.commit()
            self.load_data()
            return True, ""

        AccountDialog(self, [], initial_name=acc.name, initial_desc=acc.description, initial_curr=acc.currency_code,
                      initial_bal=str(acc.initial_balance), is_edit=True, on_submit=_update)

class PMGrid(ctk.CTkFrame):
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.session = db_session
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Payment Methods", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add Method", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self, _event=None):
        for widget in self.scroll.winfo_children(): widget.destroy()
        items = self.session.query(PaymentMethod).join(Account).order_by(Account.name, PaymentMethod.name).all()
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=item.name, width=120, anchor="w", font=("JetBrains Mono", 12, "bold")).pack(
                side="left", padx=10, pady=8)

            acc_color = "gray60" if not item.account.active_bool else "#5AC8FA"
            acc_text = f"→ {item.account.name}" + (" (Inactive)" if not item.account.active_bool else "")
            ctk.CTkLabel(row, text=acc_text, width=150, anchor="w", text_color=acc_color,
                         font=("JetBrains Mono", 11)).pack(side="left", padx=5)

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            t_text, t_color = ("Deactivate", "#b13e3e") if item.active_bool else ("Activate", "#1f538d")

            state = "disabled" if not item.active_bool and not item.account.active_bool else "normal"
            ctk.CTkButton(btn_frame, text=t_text, width=80, height=24, fg_color=t_color, state=state,
                          command=lambda i=item.id: self.toggle(i)).pack(side="right", padx=2)
            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit(i)).pack(side="right", padx=2)

            status, color = ("Active", "#4CD964") if item.active_bool else ("Inactive", "gray50")
            ctk.CTkLabel(row, text=status, text_color=color, width=60, font=("JetBrains Mono", 11)).pack(side="right",
                                                                                                         padx=10)

    def toggle(self, item_id):
        item = self.session.get(PaymentMethod, item_id)
        item.active_bool = not item.active_bool
        self.session.commit()
        self.load_data()

    def add_new(self):
        act_accounts = [a.name for a in self.session.query(Account).filter_by(active_bool=True).all()]
        if not act_accounts: return

        def _save(name, acc_name):
            if self.session.query(PaymentMethod).filter_by(name=name).first(): return False, "Name in use."
            acc = self.session.query(Account).filter_by(name=acc_name).first()
            self.session.add(PaymentMethod(name=name, account_id=acc.id))
            self.session.commit()
            self.load_data()
            return True, ""

        PMDialog(self, act_accounts, on_submit=_save)

    def edit(self, item):
        act_accounts = [a.name for a in self.session.query(Account).filter_by(active_bool=True).all()]
        if item.account.name not in act_accounts: act_accounts.append(item.account.name)

        def _update(name, acc_name):
            existing = self.session.query(PaymentMethod).filter_by(name=name).first()
            if existing and existing.id != item.id: return False, "Name in use."
            acc = self.session.query(Account).filter_by(name=acc_name).first()
            item.name = name
            item.account_id = acc.id
            self.session.commit()
            self.load_data()
            return True, ""

        PMDialog(self, act_accounts, initial_name=item.name, initial_acc=item.account.name, on_submit=_update)

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

        self.tip_window = ctk.CTkToplevel(self.widget)
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

class BaseTransactionWindow(ctk.CTkToplevel):
    def __init__(self, parent, manager, title, transaction_data = None):
        super().__init__(parent)
        self.title(title)
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
                      session.query(Currency).filter_by(active_bool=True).order_by(Currency.code.asc()).all()]
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

        projects = [p.name for p in session.query(Project).filter_by(active_bool=True).order_by(Project.name.asc()).all()]
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
                self.fx_entry.configure(text_color="white")
                self.fx_tooltip.text = "Injected rate from original transaction"
                self.mem["fx_rate"] = None
                return

            result = self.manager.get_historical_fx_rate(selected_currency, full_date)
            if result:
                self.fx_entry.delete(0, 'end')
                self.fx_entry.insert(0, str(result[0]))
                self.fx_entry.configure(text_color="white")
                self.fx_tooltip.text = f"Suggested rate from: {result[1].strftime('%Y-%m-%d')}"
            else:
                self.fx_entry.delete(0, 'end')
                self.fx_entry.insert(0, self.fx_placeholder)
                self.fx_entry.configure(text_color="gray")
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
    def __init__(self, parent, manager, transaction_data=None):
        title = "Edit Expense" if transaction_data and transaction_data.get("id") else "New Expense"
        super().__init__(parent, manager, title, transaction_data)

        self.cat_placeholder = "Search or type Category..."
        self.ven_placeholder = "Search or type Vendor..."

        # Category
        self.lbl_category = ctk.CTkLabel(self, text="Category", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_categories = [c.name for c in
                               session.query(Category).filter_by(active_bool=True).order_by(Category.name.asc()).all()]
        self.category_combo = SearchableComboBox(self, placeholder=self.cat_placeholder, values=self.all_categories,
                                                 command=lambda _: self.validate_form())
        self.category_combo.inject_value(self.mem.get("category"))
        # noinspection PyProtectedMember
        self.category_combo._entry.bind("<KeyRelease>", self.schedule_validation, add="+")

        # Vendor
        self.lbl_vendor = ctk.CTkLabel(self, text="Vendor", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_vendors = [v.name for v in
                            session.query(Vendor).filter_by(active_bool=True).order_by(Vendor.name.asc()).all()]
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
            session.query(PaymentMethod)
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

        is_duplicate = self.manager.check_for_duplicate(current_amt, current_vendor, self.date_var.get())
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
    def __init__(self, parent, manager, transaction_data=None):
        title = "Edit Gain" if transaction_data and transaction_data.get("id") else "New Gain"
        super().__init__(parent, manager, title, transaction_data)

        self.stream_placeholder = "Search or type Stream..."
        self.payer_placeholder = "Search or type Payer..."

        # Stream
        self.lbl_stream = ctk.CTkLabel(self, text="Stream", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_streams = [s.name for s in
                               session.query(Stream).filter_by(active_bool=True).order_by(Stream.name.asc()).all()]
        self.stream_combo = SearchableComboBox(self, placeholder=self.stream_placeholder, values=self.all_streams,
                                                 command=lambda _: self.validate_form())
        self.stream_combo.inject_value(self.mem.get("stream"))
        # noinspection PyProtectedMember
        self.stream_combo._entry.bind("<KeyRelease>", self.schedule_validation, add="+")

        # Payer
        self.lbl_payer = ctk.CTkLabel(self, text="Payer", font=("JetBrains Mono", 13, "bold"), anchor="w")
        self.all_payers = [p.name for p in
                            session.query(Payer).filter_by(active_bool=True).order_by(Payer.name.asc()).all()]
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
            session.query(Account)
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

        is_duplicate = self.manager.check_for_duplicate(current_amt, current_payer, self.date_var.get(), transaction_type="gain")
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
        acc_id = session.query(Account).filter_by(name=self.acc_menu.get()).first().id
        g_id = self.transaction_data.get("id") if self.is_edit_mode and self.transaction_data else None

        self.manager.add_gain(
            **base_data,
            stream_name=stream,
            payer_name=payer,
            account_id=acc_id,
            gain_id=g_id
        )

class AddTransferWindow(BaseTransactionWindow):
    def __init__(self, parent, manager, transaction_data=None):
        active_accounts = session.query(Account).filter_by(active_bool=True).order_by(Account.name.asc()).all()
        self.account_map = {acc.name: acc for acc in active_accounts}
        self.all_acc_names = list(self.account_map.keys())

        title = "Edit Transfer" if transaction_data and transaction_data.get("id") else "New Transfer"
        super().__init__(parent, manager, title, transaction_data)

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

        is_duplicate = self.manager.check_for_duplicate(
            amount=amt_orig,
            entity_name=None,
            date_str=self.date_var.get(),
            transaction_type="transfer",
            origin_id=self.origin_acc.id,
            destination_id=self.dest_acc.id,
            amount_dest=amt_dest
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
        self.status_lbl = ctk.CTkLabel(self, text="⚫", width=30, font=("Segoe UI", 14))
        self.status_lbl.grid(row=0, column=0, padx=5, pady=5)

        # 1. Date
        ctk.CTkLabel(self, text=data['date'], width=45, font=("JetBrains Mono", 11, "bold")).grid(row=0, column=1,
                                                                                                  padx=5, sticky="w")

        # 2. Vendor
        self.ven_var = ctk.StringVar(value=data['vendor'])
        self.ven_entry = ctk.CTkEntry(self, textvariable=self.ven_var, height=24)
        self.ven_entry.grid(row=0, column=2, padx=5, sticky="ew")

        # 3. Amount
        self.amt_var = ctk.StringVar(value=str(data['amount']))
        self.amt_entry = ctk.CTkEntry(self, textvariable=self.amt_var, width=70, height=24)
        self.amt_entry.grid(row=0, column=3, padx=5)

        # 4. Currency
        self.currency_combo = ctk.CTkComboBox(self, values=self.curr_names, width=70, height=24, state="readonly",
                                          command=self._on_currency_change)
        self.currency_combo.set(data['currency'] if data['currency'] in self.curr_names else "EUR")
        self.currency_combo.grid(row=0, column=4, padx=5)

        # 4. FX Rate
        self.fx_var = ctk.StringVar()
        self.fx_entry = ctk.CTkEntry(self, textvariable=self.fx_var, width=60, height=24, placeholder_text="FX")
        self.fx_entry.grid(row=0, column=5, padx=5)

        self._calculate_fx(self.currency_combo.get(), initial_load=True)

        # 5. Category (Combo)
        self.cat_combo = SearchableComboBox(self, placeholder="Category...", values=self.cat_names, width=110, height=24,
                                         command=lambda _: self.validate())
        self.cat_combo.inject_value(data['category'])
        self.cat_combo.grid(row=0, column=6, padx=5, sticky="ew")

        self.cat_combo.configure(command=lambda _: self.validate())
        # noinspection PyProtectedMember
        self.cat_combo._entry.bind("<KeyRelease>", lambda e: self.validate(), add="+")

        # 6. Payment Method (Combo)
        valid_pms = [name for name, c_code in self.pm_dict.items() if c_code == self.currency_combo.get()]
        self.pm_combo = ctk.CTkComboBox(self, values=valid_pms if valid_pms else ["None"], width=130, height=24,
                                        state="readonly", command=lambda _: self.validate())

        if data['payment_method'] in valid_pms:
            self.pm_combo.set(data['payment_method'])
        else:
            self.pm_combo.set("--- Select ---")
        self.pm_combo.grid(row=0, column=7, padx=5, sticky="ew")

        # 7. Description (Editable)
        self.desc_var = ctk.StringVar(value=data['description'])
        self.desc_entry = ctk.CTkEntry(self, textvariable=self.desc_var, height=24)
        self.desc_entry.grid(row=0, column=8, padx=5, sticky="ew")

        # 8. Discard Button
        self.btn_discard = ctk.CTkButton(self, text="✕", width=30, height=24, fg_color="transparent",
                                         text_color="gray50", hover_color="#b13e3e", command=self.discard_row)
        self.btn_discard.grid(row=0, column=9, padx=(5, 10))

        def on_x_hover(event):
            # Red
            self.configure(fg_color="#332424")

        def on_x_leave(event):
            self.configure(fg_color="gray20")

        # Binds
        self.btn_discard.bind("<Enter>", on_x_hover, add="+")
        self.btn_discard.bind("<Leave>", on_x_leave, add="+")
        self.ven_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.amt_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.desc_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.fx_entry.bind("<KeyRelease>", self._on_fx_manual_edit)

        self.is_valid = False
        self.status_type = ""
        self.validate()

    def _set_fx_tooltip(self, text):
        """Sets the FX rate tooltip."""
        self.fx_entry.unbind("<Enter>")
        self.fx_entry.unbind("<Leave>")
        ToolTip(self.fx_entry, text)

    def _on_fx_manual_edit(self, event):
        """Flags the FX source as Manual if the user types in it."""
        self._set_fx_tooltip("Source: Manual Entry")
        self.validate()

    def _calculate_fx(self, curr_code, initial_load=False):
        """Determines the FX rate and sets the appropriate Tooltip."""
        self.fx_var.set("")

        if curr_code == "EUR":
            self.fx_entry.configure(state="normal", fg_color="gray15", text_color="gray50", font=("JetBrains Mono", 11))
            self.fx_var.set("EUR Base")
            self.fx_entry.configure(state="disabled")
            self._set_fx_tooltip("EUR is the Base Currency")
            return

        self.fx_entry.configure(state="normal", fg_color=["#F9F9FA", "#343638"], text_color="white")
        self.fx_var.set("")

        if initial_load:
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
        self.pm_combo.configure(values=valid_pms if valid_pms else ["None"])

        if self.pm_combo.get() not in valid_pms:
            self.pm_combo.set("--- Select ---")

        self._calculate_fx(new_curr, initial_load=False)
        self.validate()

    def discard_row(self):
        """Removes the row and triggers a validation check after Tkinter cleans memory."""
        self.destroy()
        if hasattr(self.grid_ref, 'check_master_validation'):
            self.app.after(10, self.grid_ref.check_master_validation)

    def validate(self):
        """Checks DB integrity and updates the status light."""
        warnings = []
        errors = []

        # Check Amount
        try:
            float(self.amt_var.get())
        except ValueError:
            errors.append("Invalid Amount.")

        # Check FX
        if self.currency_combo.get() != "EUR":
            try:
                rate = float(self.fx_var.get())
                if rate <= 0: raise ValueError
            except ValueError:
                errors.append("Missing/Invalid FX Rate.")

        # Check Vendor
        if self.ven_var.get().strip() not in self.ven_names:
            warnings.append(f"New Vendor will be created.")

        # Check Category
        cat_val = self.cat_combo.get()
        if cat_val not in self.cat_names and cat_val != self.cat_combo.placeholder:
            warnings.append("New Category will be created.")
        elif cat_val == self.cat_combo.placeholder or cat_val == "":
            errors.append("Select a Category.")

        # Check Payment Method & Currency Link
        pm_val = self.pm_combo.get()
        valid_pms = [name for name, c_code in self.pm_dict.items() if c_code == self.currency_combo.get()]

        if pm_val not in valid_pms:
            errors.append("Select a matching Payment Method.")

        raw_line = f"\n\nRaw Line: {self.data.get('line', '')}"

        self.status_lbl.unbind("<Enter>")
        self.status_lbl.unbind("<Leave>")

        # Apply Colors
        if errors:
            self.status_lbl.configure(text="🔴", text_color="#FF6B6B")
            self.is_valid = False
            self.status_type = "red"
            ToolTip(self.status_lbl, " | ".join(errors) + raw_line)
        elif warnings:
            self.status_lbl.configure(text="🟡", text_color="#FFD60A")
            self.is_valid = True
            self.status_type = "yellow"
            ToolTip(self.status_lbl, " | ".join(warnings) + raw_line)
        else:
            self.status_lbl.configure(text="🟢", text_color="#4CD964")
            self.is_valid = True
            self.status_type = "green"
            ToolTip(self.status_lbl, "Ready to import." + raw_line)

        if hasattr(self.grid_ref, 'check_master_validation'):
            self.grid_ref.check_master_validation()

class AIStagingGrid(ctk.CTkFrame):
    """Holds all parsed rows and manages the final DB commit."""
    def __init__(self, parent, parsed_results, year, project, app_ref, import_btn):
        super().__init__(parent, fg_color="transparent")
        self.app = app_ref
        self.year = year
        self.project = project
        self.import_btn = import_btn

        self.active_cats = session.query(Category).filter_by(active_bool=True).all()
        self.active_pms = session.query(PaymentMethod).filter_by(active_bool=True).all()
        self.active_vendors = session.query(Vendor).filter_by(active_bool=True).all()
        self.active_currencies = session.query(Currency).filter_by(active_bool=True).all()

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)

        self.rows = []
        for res in parsed_results:
            row = AIStagingRow(self.scroll, res, self.active_cats, self.active_pms, self.active_vendors,
                               self.active_currencies, self.app, self.year, grid_ref=self)
            row.pack(fill="x", pady=2, padx=5)
            self.rows.append(row)

        self.check_master_validation()

    def check_master_validation(self):
        """Enables the Import button ONLY if every row is Green or Yellow."""
        active_rows = [row for row in self.rows if row.winfo_exists()]

        if not active_rows:
            self.import_btn.configure(state="disabled")
            return

        all_valid = all(row.is_valid for row in active_rows)
        has_warnings = any(row.status_type == "yellow" for row in active_rows)

        if all_valid:
            self.import_btn.configure(state="normal", text_color="black")
            if has_warnings:
                # Yellow Warning State
                self.import_btn.configure(fg_color="#FFD60A", hover_color="#e5c00b")
            else:
                # Green State
                self.import_btn.configure(fg_color="#4CD964", hover_color="#3cb051")
        else:
            self.import_btn.configure(state="disabled", fg_color="gray30", text_color="white")

    def execute_import(self):
        """Commits all validated rows to the database."""
        self.import_btn.configure(state="disabled", text="Importing...")
        self.app.update_idletasks()

        success_count = 0
        for row in self.rows:
            if not row.winfo_exists(): continue

            day, month = map(int, row.data['date'].split('/'))
            dt = datetime.datetime(int(self.year), month, day, 12, 0, 0, 0)

            fx_rate = None
            if row.currency_combo.get() != "EUR" and row.fx_var.get():
                try:
                    fx_rate = float(row.fx_var.get())
                except ValueError:
                    fx_rate = None

            try:
                self.app.manager.add_expense(
                    amount=float(row.amt_var.get()),
                    currency_code=row.currency_combo.get(),
                    payment_method_name=row.pm_combo.get(),
                    exchange_rate=fx_rate,
                    category_name=row.cat_combo.get(),
                    vendor_name=row.ven_var.get().strip(),
                    project_name=self.project if self.project != "None" else None,
                    description=row.desc_var.get().strip(),
                    timestamp=dt
                )
                success_count += 1
            except Exception as e:
                print(f"Failed to save {row.data['vendor']}: {e}")

        self.destroy()
        # noinspection PyProtectedMember
        self.app._reset_ai_view(success_msg=f"Successfully imported {success_count} transactions to database!")
        self.app.refresh_accounts()

class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Venn Ledger 2026")
        self.geometry("1440x700")
        self.minsize(1440, 700)
        self.maxsize(1440,980)
        ctk.set_appearance_mode("dark")
        self.manager = finance_manager.TransactionManager(session)
        self.cal_window = None
        self.current_view_date = datetime.datetime.now().replace(day=1)
        self.show_expenses_var = ctk.BooleanVar(value=True)
        self.show_gains_var = ctk.BooleanVar(value=True)
        self.show_transfers_var = ctk.BooleanVar(value=True)

        # 1. Grid Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 2. Sidebar (Accounts, Quick Actions & Modes)
        self.reorder_mode = False
        self.selected_account_id = None
        self.filter_account_id = None

        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo = ctk.CTkLabel(self.sidebar, text="FINANCE", font=("JetBrains Mono", 24, "bold"))
        self.logo.pack(pady=30, padx=20)

        self.add_exp_btn = ctk.CTkButton(self.sidebar, text="+ Add Expense", command=self.open_add_expense)
        self.add_exp_btn.pack(pady=(20, 4), padx=20)

        self.add_gain_btn = ctk.CTkButton(self.sidebar, text="+ Add Gain", command=self.open_add_gain)
        self.add_gain_btn.pack(pady=(4, 4), padx=20)

        self.add_transfer_btn = ctk.CTkButton(self.sidebar, text="⇄ Transfer Funds", command=self.open_add_transfer)
        self.add_transfer_btn.pack(pady=(4, 20), padx=20)

        self.nw_frame = ctk.CTkFrame(self.sidebar, fg_color="gray15", corner_radius=8)
        self.nw_frame.pack(fill="x", pady=(0, 15), padx=15)

        self.reorder_btn = ctk.CTkButton(self.sidebar, text="⇅ Reorder Accounts", fg_color="transparent",
                                         border_width=1, command=self.toggle_reorder_mode)
        self.reorder_btn.pack(pady=(10, 5), padx=20, fill="x")

        self.nav_group = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_group.pack(side="bottom", fill="x", pady=20, padx=15)

        self.btn_view_ledger = ctk.CTkButton(self.nav_group, text="📊 Transactions",
                                             fg_color="#1f538d", anchor="w",
                                             command=self.show_transactions_view)
        self.btn_view_ledger.pack(fill="x", pady=2)

        self.btn_view_ai = ctk.CTkButton(self.nav_group, text="⚡ AI Import",
                                         fg_color="transparent", hover_color="gray30", anchor="w",
                                         command=self.show_ai_view)
        self.btn_view_ai.pack(fill="x", pady=2)

        self.btn_view_settings = ctk.CTkButton(self.nav_group, text="⚙️ Master Data",
                                               fg_color="transparent", hover_color="gray30", anchor="w",
                                               command=self.show_settings_view)
        self.btn_view_settings.pack(fill="x", pady=2)

        self.acc_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", label_text="Accounts")
        self.acc_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # Account List
        self.refresh_accounts()

        # 3. Main Content Area (Transactions)
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.top_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.top_bar.pack(fill="x", pady=(0, 20))

        self.header = ctk.CTkLabel(self.top_bar, text="Transactions", font=("JetBrains Mono", 22, "bold"))
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
        self.date_filter_var = ctk.StringVar(value="This Month")

        self.filter_bar = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.filter_bar.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(self.filter_bar, text="Date Range:", font=("JetBrains Mono", 12, "bold")).pack(side="left", padx=(0, 10))

        self.date_menu = ctk.CTkOptionMenu(
            self.filter_bar,
            values=["All Time", "Today", "Last 7 Days", "This Month", "Last Month", "This Year", "Custom..."],
            variable=self.date_filter_var,
            command=self.on_date_filter_change,
            width=140
        )
        self.date_menu.pack(side="left")

        self.time_nav_frame = ctk.CTkFrame(self.filter_bar, fg_color="transparent")

        self.year_frame = ctk.CTkFrame(self.time_nav_frame, fg_color="gray20", height=28, corner_radius=8)
        self.year_frame.pack_propagate(False)
        self.year_frame.configure(width=128)
        self.btn_prev_year = ctk.CTkButton(self.year_frame, text="‹", width=30, height=28,
                                           hover_color="#14375e", command=self.go_prev_year)
        self.btn_prev_year.pack(side="left", padx=2)
        self.year_display_lbl = ctk.CTkLabel(self.year_frame, text="", font=("JetBrains Mono", 12, "bold"), width=60,
                                             height=28, fg_color="#1f538d"
                                             )
        self.year_display_lbl.pack(side="left")
        self.btn_next_year = ctk.CTkButton(self.year_frame, text="›", width=30, height=28,
                                           hover_color="#14375e", command=self.go_next_year)
        self.btn_next_year.pack(side="left", padx=2)

        self.month_frame = ctk.CTkFrame(self.time_nav_frame, fg_color="gray20", height=28, corner_radius=8)
        self.month_frame.pack_propagate(False)
        self.month_frame.configure(width=148)
        self.btn_prev_month = ctk.CTkButton(self.month_frame, text="‹", width=30, height=28,
                                            hover_color="#14375e", command=self.go_prev_month)
        self.btn_prev_month.pack(side="left", padx=2)
        self.month_display_lbl = ctk.CTkLabel(self.month_frame, text="", font=("JetBrains Mono", 12, "bold"), width=80,
                                              height=28, fg_color="#1f538d")
        self.month_display_lbl.pack(side="left")
        self.btn_next_month = ctk.CTkButton(self.month_frame, text="›", width=30, height=28,
                                            hover_color="#14375e", command=self.go_next_month)
        self.btn_next_month.pack(side="left", padx=2)

        self.year_frame.pack(side="left", padx=(0, 5))
        self.month_frame.pack(side="left")

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

        self.type_filter_frame = ctk.CTkFrame(self.filter_bar, fg_color="transparent")
        self.type_filter_frame.pack(side="right", padx=(20, 0))

        ctk.CTkLabel(self.type_filter_frame, text="Type:", font=("JetBrains Mono", 12, "bold")).pack(side="left",
                                                                                                     padx=(0, 10))

        self.search_entry.bind("<FocusIn>", lambda e: self._search_focus_in())
        self.search_entry.bind("<FocusOut>", lambda e: self._search_focus_out())
        self.search_entry.bind("<KeyRelease>", self.on_search_key_release)

        # 4. Transaction Counter
        self.transaction_counter_lbl = ctk.CTkLabel(
            self.top_bar,
            text="Showing 0 of 0 transactions",
            font=("JetBrains Mono", 11),
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

        self.in_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("JetBrains Mono", 12, "bold"), text_color="#4CD964", anchor="e")
        self.in_lbl.pack(fill="x")

        self.out_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("JetBrains Mono", 12, "bold"), text_color="#b13e3e", anchor="e")
        self.out_lbl.pack(fill="x")

        self.balance_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("JetBrains Mono", 13, "bold"), anchor="e")
        self.balance_lbl.pack(fill="x")

        ToolTip(self.search_entry,self.search_placeholder)

        self.selected_account_id = None

        self.current_page = 0
        self.page_size = 40
        self.total_pages = 0
        self.jump_entry = None
        self.search_timer = None
        self.current_search_text = ""
        self.nav_timer = None
        self.type_timer = None

        self.on_date_filter_change("This Month")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.chk_expenses = ctk.CTkCheckBox(self.type_filter_frame, text="Expenses", variable=self.show_expenses_var,
                                       font=("JetBrains Mono", 11), width=60, command=self._schedule_type_filter)
        self.chk_expenses.pack(side="left", padx=5)

        self.chk_gains = ctk.CTkCheckBox(self.type_filter_frame, text="Gains", variable=self.show_gains_var,
                                        font=("JetBrains Mono", 11), width=60, command=self._schedule_type_filter)
        self.chk_gains.pack(side="left", padx=5)

        self.chk_transfers = ctk.CTkCheckBox(self.type_filter_frame, text="Transfers", variable=self.show_transfers_var,
                                       font=("JetBrains Mono", 11), width=60, command=self._schedule_type_filter)
        self.chk_transfers.pack(side="left", padx=5)

        # 7. Settings & Master Data Area
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.settings_header = ctk.CTkLabel(self.settings_frame, text="Master Data Management",
                                            font=("JetBrains Mono", 22, "bold"))
        self.settings_header.pack(anchor="w", pady=(0, 20))

        self.settings_tabview = ctk.CTkTabview(self.settings_frame)
        self.settings_tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_accounts = self.settings_tabview.add("Accounts & Payment Methods")
        self.tab_currencies = self.settings_tabview.add("Currencies & FX")
        self.tab_categories = self.settings_tabview.add("Categories & Streams")
        self.tab_entities = self.settings_tabview.add("Vendors & Payers")
        self.tab_projects = self.settings_tabview.add("Projects")

        # Accounts & Payment Methods Tab
        self.tab_accounts.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
        self.tab_accounts.grid_rowconfigure(0, weight=1)

        self.acc_grid = AccountGrid(self.tab_accounts, session)
        self.acc_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.pm_grid = PMGrid(self.tab_accounts, session)
        self.pm_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.acc_grid.bind("<<DataChanged>>", self.pm_grid.load_data)

        # Categories & Streams Tab
        self.tab_categories.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
        self.tab_categories.grid_rowconfigure(0, weight=1)

        self.cat_grid = SimpleMasterDataGrid(self.tab_categories, session, Category, "Categories (Expenses)")
        self.cat_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.stream_grid = SimpleMasterDataGrid(self.tab_categories, session, Stream, "Streams (Gains)")
        self.stream_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Vendors & Payers Tab
        self.tab_entities.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
        self.tab_entities.grid_rowconfigure(0, weight=1)

        self.vendor_grid = SimpleMasterDataGrid(self.tab_entities, session, Vendor, "Vendors (Outbound)")
        self.vendor_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.payer_grid = SimpleMasterDataGrid(self.tab_entities, session, Payer, "Payers (Inbound)")
        self.payer_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Projects Tab
        self.tab_projects.grid_columnconfigure(0, weight=1)
        self.tab_projects.grid_rowconfigure(0, weight=1)

        self.proj_grid = SimpleMasterDataGrid(self.tab_projects, session, Project, "Projects", has_desc=True)
        self.proj_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Currencies & FX Tab
        self.tab_currencies.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
        self.tab_currencies.grid_rowconfigure(0, weight=1)

        self.curr_grid = CurrencyGrid(self.tab_currencies, session)
        self.curr_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        self.fx_grid = ExchangeRateGrid(self.tab_currencies, session)
        self.fx_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.settings_frame.grid_remove()

    def _hide_all_views(self):
        """Hides all main frames and resets navigation button colors."""
        self.main_frame.grid_remove()
        self.settings_frame.grid_remove()
        if hasattr(self, 'ai_frame'):
            self.ai_frame.grid_remove()

        for btn in [self.btn_view_ledger, self.btn_view_ai, self.btn_view_settings]:
            btn.configure(fg_color="transparent")

    def show_transactions_view(self):
        self._hide_all_views()
        self.main_frame.grid()
        self.btn_view_ledger.configure(fg_color="#1f538d")

    def show_settings_view(self):
        self._hide_all_views()
        self.settings_frame.grid()
        self.btn_view_settings.configure(fg_color="#1f538d")

    def show_ai_view(self):
        self._hide_all_views()

        if not hasattr(self, 'ai_frame'):
            self._build_ai_frame()

        self.ai_frame.grid()
        self.btn_view_ai.configure(fg_color="#1f538d")

    def _build_ai_frame(self):
        """Builds the AI Import configuration panel and staging area."""
        self.ai_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.ai_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.ai_header = ctk.CTkLabel(self.ai_frame, text="AI Transaction Parser", font=("JetBrains Mono", 22, "bold"))
        self.ai_header.pack(anchor="w", pady=(0, 10))

        self.ai_config_frame = ctk.CTkFrame(self.ai_frame, fg_color="gray15", corner_radius=8)
        self.ai_config_frame.pack(fill="x", pady=(0, 15), padx=2)

        cmd_bar = ctk.CTkFrame(self.ai_config_frame, fg_color="transparent")
        cmd_bar.pack(fill="x", pady=12, padx=15)

        # File Selection
        ctk.CTkLabel(cmd_bar, text="Target File:", font=("JetBrains Mono", 12, "bold"), anchor="w").pack(
            side="left")
        self.lbl_container = ctk.CTkFrame(cmd_bar, width=300, height=28, fg_color="gray20", corner_radius=4)
        self.lbl_container.pack_propagate(False)
        self.lbl_container.pack(side="left", padx=(10,0))

        self.ai_full_filepath = ""
        self.ai_filepath_var = ctk.StringVar(value="No file selected...")
        self.ai_file_lbl = ctk.CTkLabel(self.lbl_container, textvariable=self.ai_filepath_var, text_color="gray60",
                                        anchor="w")
        self.ai_file_lbl.pack(fill="both", expand=True, padx=10)
        self.file_tooltip = ToolTip(self.ai_file_lbl, "Please select a text file.")

        self.btn_browse = ctk.CTkButton(cmd_bar, text="Browse", width=70, fg_color="gray30", hover_color="gray40",
                                        command=self._ai_browse_file)
        self.btn_browse.pack(side="left", padx=(5, 15))

        # Dropdowns
        active_currencies = [c.code for c in session.query(Currency).filter_by(active_bool=True).all()]
        active_projects = ["None"] + [p.name for p in session.query(Project).filter_by(active_bool=True).all()]
        current_year = str(datetime.datetime.now().year)
        years = [str(y) for y in range(int(current_year) - 2, int(current_year) + 3)]

        ctk.CTkLabel(cmd_bar, text="Year:", font=("JetBrains Mono", 11, "bold")).pack(side="left")
        self.ai_year_combo = ctk.CTkComboBox(cmd_bar, values=years, width=80)
        self.ai_year_combo.set(current_year)
        self.ai_year_combo.pack(side="left", padx=(10, 15))
        ToolTip(self.ai_year_combo, "Select from dropdown or manually type a year.")

        ctk.CTkLabel(cmd_bar, text="Default Currency:", font=("JetBrains Mono", 11, "bold")).pack(side="left")
        self.ai_curr_combo = ctk.CTkComboBox(cmd_bar, values=active_currencies, state="readonly", width=70)
        if "EUR" in active_currencies: self.ai_curr_combo.set("EUR")
        self.ai_curr_combo.pack(side="left", padx=(10, 15))
        ToolTip(self.ai_curr_combo, "Select from dropdown.")

        ctk.CTkLabel(cmd_bar, text="Tag Project:", font=("JetBrains Mono", 11, "bold")).pack(side="left")
        self.ai_proj_combo = ctk.CTkComboBox(cmd_bar, values=active_projects, state="readonly", width=130)
        self.ai_proj_combo.set("None")
        self.ai_proj_combo.pack(side="left", padx=(10, 20))
        ToolTip(self.ai_proj_combo, "Select from dropdown.")

        self.btn_start_ai = ctk.CTkButton(cmd_bar, text="⚡ Start Parsing", fg_color="#1f538d", width=120,
                                          font=("JetBrains Mono", 12, "bold"), command=self._start_ai_thread)
        self.btn_start_ai.pack(side="left")

        self.btn_cancel_ai = ctk.CTkButton(cmd_bar, text="✕ Cancel", fg_color="#b13e3e", hover_color="#611a1a",
                                           width=120, font=("JetBrains Mono", 12, "bold"),
                                           command=self._cancel_ai_thread)

        self.btn_clear_ai = ctk.CTkButton(cmd_bar, text="↺ Clear Session", fg_color="gray40", hover_color="gray50",
                                          width=120, font=("JetBrains Mono", 12, "bold"), command=self._reset_ai_view)

        self.progress_container = ctk.CTkFrame(self.ai_frame, fg_color="transparent", height=50)
        self.progress_container.pack_propagate(False)
        self.progress_container.pack(fill="x", pady=(0, 10))

        self.ai_status_lbl = ctk.CTkLabel(self.progress_container, text="", text_color="#5AC8FA",
                                          font=("JetBrains Mono", 12))
        self.ai_status_lbl.pack(pady=(0, 5))

        self.ai_progress_bar = ctk.CTkProgressBar(self.progress_container, mode="determinate", height=8, fg_color="gray20",
                                                  progress_color="#1f538d")
        self.ai_progress_bar.set(0)

        self.ai_staging_frame = ctk.CTkFrame(self.ai_frame, fg_color="transparent")
        self.ai_staging_frame.pack(fill="both", expand=True)

        self.staging_header = ctk.CTkFrame(self.ai_staging_frame, fg_color="transparent")

        self.staging_title = ctk.CTkLabel(self.staging_header, text="File Preview", font=("JetBrains Mono", 14, "bold"))
        self.staging_title.pack(side="left", padx=10)

        self.btn_import_all = ctk.CTkButton(self.staging_header, text="✅ Import All", fg_color="#4CD964",
                                            text_color="black", hover_color="#3cb051", width=120,
                                            font=("JetBrains Mono", 12, "bold"), state="disabled")

        self.btn_toggle_view = ctk.CTkButton(self.staging_header, text="👁 View File", fg_color="gray30",
                                             hover_color="gray40", width=120, font=("JetBrains Mono", 12, "bold"),
                                             command=self._toggle_ai_view)

        self.preview_container = ctk.CTkFrame(self.ai_staging_frame, fg_color="transparent")
        self.grid_container = ctk.CTkFrame(self.ai_staging_frame, fg_color="transparent")

        self.ai_cancel_event = threading.Event()

    def _ai_browse_file(self):
        """Opens the OS file picker."""
        filepath = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if filepath:
            self.ai_full_filepath = filepath
            display = filepath if len(filepath) < 45 else ".../" + filepath.split("/")[-1]
            self.ai_filepath_var.set(display)
            self.file_tooltip.text = filepath
            self.ai_status_lbl.configure(text="Ready to parse.", text_color="#5AC8FA")

            self.staging_header.pack(fill="x", pady=(10, 5))
            self.staging_title.configure(text="File Preview")
            self.btn_toggle_view.pack_forget()
            self.btn_import_all.pack_forget()

            self.grid_container.pack_forget()
            self.btn_toggle_view.pack_forget()
            self.preview_container.pack(fill="both", expand=True)

            for widget in self.preview_container.winfo_children():
                widget.destroy()

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                preview_box = ctk.CTkTextbox(self.preview_container, font=("JetBrains Mono", 12), text_color="gray70",
                                             fg_color="gray15")
                preview_box.pack(fill="both", expand=True, padx=5, pady=5)
                preview_box.insert("0.0", file_content)
                preview_box.configure(state="disabled")

            except Exception as e:
                self.ai_status_lbl.configure(text=f"Error reading file: {e}", text_color="#FF6B6B")

    def _start_ai_thread(self):
        """Validates inputs, disables UI, and spins up the background worker."""
        if not self.ai_full_filepath:
            self.ai_status_lbl.configure(text="Error: Please select a file first.", text_color="#FF6B6B")
            return

        year_val = self.ai_year_combo.get().strip()
        if len(year_val) != 4 or not year_val.isdigit():
            self.ai_status_lbl.configure(text="Error: Please enter a valid 4-digit year.", text_color="#FF6B6B")
            return

        self.ai_cancel_event.clear()
        self.btn_browse.configure(state="disabled")
        self.ai_year_combo.configure(state="disabled")
        self.ai_curr_combo.configure(state="disabled")
        self.ai_proj_combo.configure(state="disabled")
        self.btn_start_ai.pack_forget()
        self.btn_clear_ai.pack_forget()
        self.btn_cancel_ai.pack(side="left")
        self.btn_cancel_ai.configure(state="normal")
        self.ai_status_lbl.configure(text="Connecting to Mistral 7B... Please wait.", text_color="#5AC8FA")

        self.ai_progress_bar.pack(fill="x", padx=150)
        self.ai_progress_bar.configure(progress_color="#1f538d")
        self.ai_progress_bar.set(0)

        currency = self.ai_curr_combo.get()
        year = self.ai_year_combo.get()
        project = self.ai_proj_combo.get()

        thread = threading.Thread(target=self._run_ai_parser_backend,
                                  args=(self.ai_full_filepath, currency, year, project))
        thread.daemon = True
        thread.start()

    def _update_ai_progress(self, current_line, total_lines, current_tx, total_tx):
        """Runs on main thread: Updates the visual progress bar and text."""
        if total_lines > 0:
            self.ai_progress_bar.set(current_line / total_lines)
        if total_tx > 0 and current_tx > 0:
            self.ai_status_lbl.configure(
                text=f"Parsing transaction {current_tx} of {total_tx}...",
                text_color="#5AC8FA"
            )

    def _cancel_ai_thread(self):
        """Triggers the threading event to stop the parser loop."""
        self.ai_cancel_event.set()
        self.btn_cancel_ai.configure(state="disabled")
        self.ai_status_lbl.configure(text="Cancelling... waiting for current line to finish.", text_color="orange")
        self.ai_progress_bar.configure(progress_color="orange")

    def _run_ai_parser_backend(self, filepath, currency, year, project):
        """Runs in the background."""
        try:
            # 1. Chunk the file
            daily_chunks = chunk_file_by_day(filepath)

            # 2. Combine chunks into a single string for parsing
            combined_str = ""
            for day in daily_chunks:
                combined_str += f"{day['header']}\n{day['data']}\n"

            # 3. Get active categories
            active_cats = session.query(Category).filter_by(active_bool=True).all()

            # 4. Define the callback
            def progress_cb(c_line, t_lines, c_tx, t_tx):
                self.after(0, self._update_ai_progress, c_line, t_lines, c_tx, t_tx)

            # 5. Invoke LLM
            parsed_results = get_structured_data(combined_str, currency, active_cats, cancel_event=self.ai_cancel_event,
                                                 progress_callback=progress_cb)

            # 6. Pass results back to the main GUI thread
            self.after(0, self._on_ai_parsing_complete, parsed_results, year, project)

        except Exception as e:
            self.after(0, self._on_ai_parsing_failed, str(e))

    def _toggle_ai_view(self):
        """Flips visibility between the file preview and the staging grid."""
        if self.preview_container.winfo_ismapped():
            self.preview_container.pack_forget()
            self.grid_container.pack(fill="both", expand=True)
            self.btn_toggle_view.configure(text="👁 View File")
            self.staging_title.configure(text="Review & Fix")
        else:
            self.grid_container.pack_forget()
            self.preview_container.pack(fill="both", expand=True)
            self.btn_toggle_view.configure(text="▦ View Grid")
            self.staging_title.configure(text="File Preview")

    def _reset_ai_view(self, success_msg=None):
        """Wipes the staging grid & preview and restores the config panel to default."""
        self.ai_year_combo.configure(state="normal")
        self.ai_year_combo.set(str(datetime.datetime.now().year))
        self.ai_curr_combo.configure(state="normal")
        self.ai_curr_combo.set("EUR")
        self.ai_proj_combo.configure(state="normal")
        self.ai_proj_combo.set("None")
        self.btn_browse.configure(state="normal")

        self.btn_cancel_ai.pack_forget()
        self.btn_clear_ai.pack_forget()
        self.btn_start_ai.pack(side="left")

        self.ai_full_filepath = ""
        self.ai_filepath_var.set("No file selected...")
        self.file_tooltip.text = "Please select a text file."

        self.ai_progress_bar.pack_forget()

        for widget in self.grid_container.winfo_children():
            widget.destroy()
        for widget in self.preview_container.winfo_children():
            widget.destroy()

        self.staging_header.pack_forget()
        self.preview_container.pack_forget()
        self.grid_container.pack_forget()

        if success_msg:
            self.ai_status_lbl.configure(text=success_msg, text_color="#4CD964")
        else:
            self.ai_status_lbl.configure(text="Session cleared. Ready.", text_color="gray")

    def _on_ai_parsing_failed(self, error_msg):
        """Runs on main thread: Handles crashes during parsing."""
        self.ai_year_combo.configure(state="normal")
        self.ai_curr_combo.configure(state="normal")
        self.ai_proj_combo.configure(state="normal")
        self.btn_browse.configure(state="normal")

        self.btn_cancel_ai.pack_forget()
        self.btn_start_ai.pack(side="left")
        self.btn_start_ai.configure(state="normal")

        color = "orange" if "cancelled" in error_msg.lower() else "#FF6B6B"
        self.ai_status_lbl.configure(text=f"Stopped: {error_msg}", text_color=color)

        self.ai_progress_bar.pack_forget()

    def _on_ai_parsing_complete(self, parsed_results, year, project):
        """Runs on main thread: Receives data and build the staging grid."""
        self.btn_cancel_ai.pack_forget()
        self.btn_clear_ai.pack(side="left")

        self.ai_progress_bar.pack_forget()

        if not parsed_results:
            self.ai_status_lbl.configure(text="No valid transactions found.", text_color="#FF6B6B")
            return

        self.ai_status_lbl.configure(
            text=f"Found {len(parsed_results)} transactions. Please review and fix any errors before importing.",
            text_color="#5AC8FA",
            font=("JetBrains Mono", 12))

        self.staging_title.configure(text="Review & Fix")
        self.btn_import_all.pack(side="right")
        self.btn_toggle_view.pack(side="right", padx=10)
        self.btn_toggle_view.configure(text="👁 View File")

        self.preview_container.pack_forget()
        self.grid_container.pack(fill="both", expand=True)

        for widget in self.grid_container.winfo_children():
            widget.destroy()

        grid = AIStagingGrid(self.grid_container, parsed_results, year, project, self, self.btn_import_all)
        grid.pack(fill="both", expand=True)

        print("--- THREAD COMPLETE. DATA RECEIVED IN GUI ---")
        for res in parsed_results:
            print(res)

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
        if selection in ["This Month", "This Year"]:
            self.current_view_date = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            self.custom_date_frame.pack_forget()
            if selection == "This Year":
                self.month_frame.pack_forget()
            else:
                self.month_frame.pack(side="left")
            self.time_nav_frame.pack(side="left", padx=20, anchor="n")
            self.update_time_display()
            self.current_page = 0
            self.load_transactions()
            self.reset_scroll_to_top()
        else:
            self.time_nav_frame.pack_forget()
            if selection == "Custom...":
                self.custom_date_frame.pack(side="left", padx=20)
            else:
                self.custom_date_frame.pack_forget()
                self.current_page = 0
                self.load_transactions()
                self.reset_scroll_to_top()

    def _schedule_nav_load(self):
        """Debounces DB calls to allow rapid clicking."""
        if self.nav_timer:
            self.after_cancel(self.nav_timer)
        self.nav_timer = self.after(300, self._execute_nav_load)

    def _execute_nav_load(self):
        self.nav_timer = None
        self.current_page = 0
        self.load_transactions()
        self.reset_scroll_to_top()

    def _schedule_type_filter(self):
        """Debounces DB calls to allow rapid clicking."""
        if self.type_timer:
            self.after_cancel(self.type_timer)
        self.type_timer = self.after(600, self._execute_type_filter)

    def _execute_type_filter(self):
        """Resets view and reloads when a type checkbox is toggled."""
        self.type_timer = None
        self.current_page = 0
        self.load_transactions()
        self.reset_scroll_to_top()

    def update_time_display(self):
        self.year_display_lbl.configure(text=self.current_view_date.strftime("%Y"))
        self.month_display_lbl.configure(text=self.current_view_date.strftime("%B"))

    def go_prev_year(self):
        self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year - 1)
        self.update_time_display()
        self._schedule_nav_load()

    def go_next_year(self):
        self.current_view_date = self.current_view_date.replace(year=self.current_view_date.year + 1)
        self.update_time_display()
        self._schedule_nav_load()

    def go_prev_month(self):
        last_month = self.current_view_date - datetime.timedelta(days=1)
        self.current_view_date = last_month.replace(day=1)
        self.update_time_display()
        self._schedule_nav_load()

    def go_next_month(self):
        next_month = self.current_view_date + datetime.timedelta(days=32)
        self.current_view_date = next_month.replace(day=1)
        self.update_time_display()
        self._schedule_nav_load()

    def get_date_limit(self, selection):
        """Calculates the 'start' and 'end' dates for the SQL query."""
        now = datetime.datetime.now()
        end_of_now = now.replace(microsecond=999999)

        if selection == "Today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return start, end_of_now

        elif selection == "Last 7 Days":
            start = now - datetime.timedelta(days=7)
            return start, end_of_now

        elif selection == "This Month":
            start = self.current_view_date.replace(hour=0, minute=0, second=0, microsecond=0)
            next_month = start + datetime.timedelta(days=32)
            end = next_month.replace(day=1) - datetime.timedelta(microseconds=1)
            return start, end

        elif selection == "Last Month":
            first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_of_last_month = first_of_this_month - datetime.timedelta(microseconds=1)
            first_of_last_month = last_of_last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            return first_of_last_month, last_of_last_month

        elif selection == "This Year":
            start = self.current_view_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
            return start, end

        return None, None

    def get_dynamic_char_limit(self):
        """Calculates how many characters can fit in the Description gap."""
        self.update_idletasks()
        current_width = 1400
        # Sum of static widths + sidebar:
        static_space = 800+250+140

        available_pixels = current_width - static_space

        char_limit = int(available_pixels / 7)

        return max(20, char_limit)

    def refresh_accounts(self):
        """Builds the account buttons and the Net Worth summary."""
        for widget in self.nw_frame.winfo_children():
            widget.destroy()

        # Net Worth
        net_worth = self.manager.get_net_worth()

        ctk.CTkLabel(self.nw_frame, text="TOTAL NET WORTH", font=("JetBrains Mono", 10, "bold"), text_color="gray").pack(pady=(8, 0))
        ctk.CTkLabel(self.nw_frame, text=f"€ {net_worth:,.2f}", font=("JetBrains Mono", 18, "bold"), text_color="#4CD964").pack(
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
            def on_enter(_e, card=acc_card, h_bg=hover_bg):
                card.configure(fg_color=h_bg)

            def on_leave(_e, card=acc_card, b_bg=base_bg):
                card.configure(fg_color=b_bg)

            # Bind to the frame itself
            acc_card.bind("<Enter>", on_enter)
            acc_card.bind("<Leave>", on_leave)
            acc_card.bind("<Button-1>", lambda e, aid=acc.id: self.handle_account_click(aid))

            # Row 1: Name
            ctk.CTkLabel(acc_card, text=acc.name.upper(),
                         font=("JetBrains Mono", 10),
                         anchor="w", height=15).pack(fill="x", padx=10, pady=(5, 0))

            # Row 2: Balance
            bal_color = "#FF6B6B" if acc.balance < 0 else "white"
            ctk.CTkLabel(acc_card, text=f"{acc.balance:,.2f} {acc.currency_code}",
                         font=("JetBrains Mono", 12, "bold"), text_color=bal_color,
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

    @staticmethod
    def load_account_order():
        """Loads the account ID order from a local JSON file."""
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    return json.load(f).get("account_order", [])
        except (json.decoder.JSONDecodeError, IOError):
            return[]
        return []

    @staticmethod
    def save_account_order(order_list):
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
            self.show_transactions_view()

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
                end = datetime.datetime.strptime(self.end_date_var.get(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                query = query.filter(column("ts").between(start, end))
            except ValueError:
                pass
        else:
            start_limit, end_limit = self.get_date_limit(selection)

            if start_limit and end_limit:
                query = query.filter(column("ts").between(start_limit, end_limit))
            elif selection == "All Time":
                pass

        if self.filter_account_id:
            query = query.filter(column("acc_id") == self.filter_account_id)

        allowed_types = []
        if self.show_expenses_var.get():
            allowed_types.append('expense')
        if self.show_gains_var.get():
            allowed_types.append('gain')
        if self.show_transfers_var.get():
            allowed_types.extend(['transfer_in', 'transfer_out'])

        query = query.filter(column("type").in_(allowed_types))

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
            TransactionRow(self.scroll_frame, self, row_data, char_limit, ent_char_limit)

        self.update_pagination_ui(total_count, query)

    @staticmethod
    def get_unified_transaction_query(current_session):
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

    @staticmethod
    def calculate_totals(base_query):
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

    def jump_to_page(self, _event=None):
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

    @staticmethod
    def _prepare_transaction_data(row_data, is_edit=False):
        """Maps a unified SQL row into the dictionary for the forms."""
        data = {
            "amount": row_data.amount,
            "currency": row_data.currency,
            "date": row_data.ts.strftime("%Y-%m-%d"),
            "desc": row_data.desc,
            "project": row_data.proj_name,
            "fx_rate": row_data.fx_rate
        }

        if is_edit:
            data["id"] = row_data.id
            data["date"] = row_data.ts.strftime("%Y-%m-%d %H:%M:%S")

        if row_data.type == "expense":
            data["category"] = row_data.category
            data["entity"] = row_data.entity
            data["pm"] = row_data.pm_or_acc
        elif row_data.type == "gain":
            data["stream"] = row_data.category
            data["entity"] = row_data.entity
            data["acc"] = row_data.pm_or_acc
        elif "transfer" in row_data.type:
            t = session.get(Transfer, row_data.id)
            data["amount"] = t.amount_origin
            data["dest_amount"] = t.amount_destination
            data["orig_acc"] = t.origin_account.name
            data["dest_acc"] = t.destination_account.name

        return data

    def open_copy_transaction(self, row_data):
        """Strips the ID and opens the form as a new entry."""
        mapped_data = self._prepare_transaction_data(row_data, is_edit=False)
        if row_data.type == "expense":
            AddExpenseWindow(self, self.manager, transaction_data=mapped_data)
        elif row_data.type == "gain":
            AddGainWindow(self, self.manager, transaction_data=mapped_data)
        elif "transfer" in row_data.type:
            AddTransferWindow(self, self.manager, transaction_data=mapped_data)

    def open_edit_transaction(self, row_data):
        """
        Keeps the ID so the backend knows to upsert.
        Opens the form for editing.
        """
        mapped_data = self._prepare_transaction_data(row_data, is_edit=True)
        if row_data.type == "expense":
            AddExpenseWindow(self, self.manager, transaction_data=mapped_data)
        elif row_data.type == "gain":
            AddGainWindow(self, self.manager, transaction_data=mapped_data)
        elif "transfer" in row_data.type:
            AddTransferWindow(self, self.manager, transaction_data=mapped_data)

    def delete_transaction_prompt(self, transaction_id, transaction_type, context_text="", on_cancel=None):
        """Generates a popup to confirm deletion before modifying the DB."""
        popup = ctk.CTkToplevel(self)
        popup.title("Confirm Delete")
        popup.geometry("350x170")
        popup.attributes("-topmost", True)
        popup.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 175
        y = self.winfo_y() + (self.winfo_height() // 2) - 85
        popup.geometry(f"+{x}+{y}")

        def cancel_action():
            if on_cancel: on_cancel()
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", cancel_action)

        ctk.CTkLabel(popup, text="Are you sure you want to delete\nthis transaction?",
                     font=("JetBrains Mono", 12)).pack(pady=(20, 5))
        ctk.CTkLabel(popup, text=context_text, font=("JetBrains Mono", 11), text_color="orange").pack(pady=(0, 15))
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(pady=5)

        def confirm():
            try:
                self.manager.delete_transaction(transaction_id, transaction_type)
                self.refresh_accounts()
                self.load_transactions()
            except Exception as e:
                print(f"Delete error: {e}")
            finally:
                popup.destroy()

        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=cancel_action).pack(side="left",
                                                                                                         padx=10)
        ctk.CTkButton(btn_frame, text="Delete", width=80, fg_color="#8b2525", hover_color="#611a1a",
                      command=confirm).pack(side="left", padx=10)

    def on_closing(self):
        """Ensures the DB session is safely closed before quitting."""
        try:
            session.close()
            print("Database session closed successfully.")
        except Exception as e:
            print(f"Error closing database session: {e}")
        finally:
            self.destroy()

    def open_add_expense(self):
        AddExpenseWindow(self, self.manager)

    def open_add_gain(self):
        AddGainWindow(self, self.manager)

    def open_add_transfer(self):
        AddTransferWindow(self, self.manager)


if __name__ == "__main__":
    app = FinanceApp()
    app.mainloop()


