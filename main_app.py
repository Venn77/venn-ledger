import json, os, sys, traceback
import customtkinter as ctk

if sys.platform != "win32":
    ctk.set_widget_scaling(0.9)
    ctk.set_window_scaling(0.9)

import matplotlib.pyplot as plt
from tkinter import TclError
from typing import Any
from config import CONFIG_PATH, APP_VERSION, IS_COMPILED, ERROR_LOG_PATH
from database.models import Session, Account, Transfer, Currency
from core import manager as finance_manager
from utils.icon_manager import get_icon, set_app_window_icon
from utils.ctk_utils import calculate_dialog_geometry
from gui.transaction_forms import AddExpenseWindow, AddGainWindow, AddTransferWindow
from gui.transactions_view import TransactionsView
from gui.settings_view import SettingsView
from gui.ai_view import AIImportView
from gui.dashboard_view import DashboardView
from gui.wizard import FirstRunWizard


if IS_COMPILED:
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        with open(ERROR_LOG_PATH, "a") as log_file:
            log_file.write("--- FATAL CRASH ---\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=log_file)
            log_file.write("\n")

    sys.excepthook = global_exception_handler


class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        if IS_COMPILED:
            self.report_callback_exception = global_exception_handler
        self.title("Venn Ledger 2026")
        set_app_window_icon(self)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        app_w = min(1440, screen_w)
        app_h = min(700, screen_h)

        min_w = min(1280, screen_w)
        min_h = min(650, screen_h)

        self.geometry(f"{app_w}x{app_h}")
        self.minsize(min_w, min_h)
        self.maxsize(max(1440, screen_w), max(980, screen_h))
        ctk.set_appearance_mode("dark")
        self.db_session = Session()
        base_exists = self.db_session.query(Currency).filter_by(is_base=True).first()
        self.cal_window = None
        self.active_expense_window = None
        self.active_gain_window = None
        self.active_transfer_window = None
        self.reorder_mode = None
        self.selected_account_id = None
        self.filter_account_id = None
        self.current_net_worth = 0.0

        if not base_exists:
            self.withdraw()
            FirstRunWizard(self, self.db_session, self._finish_init)
        else:
            self._finish_init()

    def _finish_init(self):
        """Called either immediately (if DB exists) or after the Wizard finishes."""
        self.manager = finance_manager.TransactionManager(self.db_session)
        self.bar_chart_icon = get_icon("bar_chart.png", size=(18, 18), light_filename="bar_chart_lm.png")
        self.bolt_icon = get_icon("bolt.png", size=(18, 18), light_filename="bolt_lm.png")
        self.trending_up_icon = get_icon("trending_up.png", size=(18, 18), light_filename="trending_up_lm.png")
        self.settings_icon = get_icon("settings.png", size=(18, 18), light_filename="settings_lm.png")
        self.reorder_icon = get_icon("swap_vert.png", size=(15, 15), light_filename="swap_vert_lm.png")

        # 1. Grid Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.views: dict[str, Any] = {
            "transactions": None,
            "ai": None,
            "dashboard": None,
            "settings": None
        }

        self._build_sidebar()
        self.bind("<<SidebarUpdate>>", lambda e: self.refresh_accounts())
        self.switch_view("transactions")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.deiconify()
        # noinspection PyTypeChecker
        if sys.platform == "win32":
            self.after(0, lambda: self.state('zoomed'))
        else:
            def _maximize_linux():
                try:
                    self.attributes('-zoomed', True)
                except TclError:
                    pass

            self.after(0, _maximize_linux)

    def _build_sidebar(self):
        """Builds the permanent sidebar and navigation buttons."""
        self.reorder_mode = False
        self.selected_account_id = None
        self.filter_account_id = None

        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo = ctk.CTkLabel(self.sidebar, text="FINANCE", font=("JetBrains Mono", 24, "bold"))
        self.logo.pack(pady=15, padx=20)

        self.add_exp_btn = ctk.CTkButton(self.sidebar, text="+ Add Expense", command=self.open_add_expense)
        self.add_exp_btn.pack(pady=(15, 4), padx=20)

        self.add_gain_btn = ctk.CTkButton(self.sidebar, text="+ Add Gain", command=self.open_add_gain)
        self.add_gain_btn.pack(pady=(4, 4), padx=20)

        self.add_transfer_btn = ctk.CTkButton(self.sidebar, text="⇄ Transfer Funds", command=self.open_add_transfer)
        self.add_transfer_btn.pack(pady=(4, 20), padx=20)

        self.nw_frame = ctk.CTkFrame(self.sidebar, fg_color="gray15", corner_radius=8)
        self.nw_frame.pack(fill="x", pady=(0, 15), padx=15)

        self.lbl_nw_title = ctk.CTkLabel(self.nw_frame, text="TOTAL NET WORTH", font=("JetBrains Mono", 10, "bold"),
                                         text_color="gray")
        self.lbl_nw_title.pack(pady=(8, 0))

        self.lbl_nw_val = ctk.CTkLabel(self.nw_frame, text="...", font=("JetBrains Mono", 18, "bold"))
        self.lbl_nw_val.pack(pady=(0, 8))

        self.reorder_btn = ctk.CTkButton(self.sidebar, text="Reorder Accounts", image=self.reorder_icon, compound="left", fg_color="transparent",
                                         border_width=1, command=self.toggle_reorder_mode)
        self.reorder_btn.pack(pady=(10, 5), padx=20, fill="x")

        self.version_lbl = ctk.CTkLabel(
            self.sidebar,
            text=APP_VERSION,
            font=("JetBrains Mono", 11),
            text_color="gray50"
        )
        self.version_lbl.pack(side="bottom", pady=(0, 10))

        self.nav_group = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_group.pack(side="bottom", fill="x", pady=10, padx=15)

        self.btn_view_ledger = ctk.CTkButton(self.nav_group, text="Transactions", image=self.bar_chart_icon, compound="left",
                                             anchor="w", command=lambda: self.switch_view("transactions"))
        self.btn_view_ledger.pack(fill="x", pady=2)

        self.btn_view_ai = ctk.CTkButton(self.nav_group, text="AI Import", image=self.bolt_icon, compound="left",
                                         anchor="w", command=lambda: self.switch_view("ai"))
        self.btn_view_ai.pack(fill="x", pady=2)

        self.btn_view_dashboard = ctk.CTkButton(self.nav_group, text="Dashboard", image=self.trending_up_icon, compound="left",
                                         anchor="w", command=lambda: self.switch_view("dashboard"))
        self.btn_view_dashboard.pack(fill="x", pady=2)

        self.btn_view_settings = ctk.CTkButton(self.nav_group, text="Master Data", image=self.settings_icon, compound="left",
                                               anchor="w", command=lambda: self.switch_view("settings"))
        self.btn_view_settings.pack(fill="x", pady=2)

        self.acc_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", label_text="Accounts")
        self.acc_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        self.refresh_accounts()
        self.selected_account_id = None

    def switch_view(self, view_name):
        """Hides all views, builds the requested one if missing, and shows it."""
        for btn in [self.btn_view_ledger, self.btn_view_ai, self.btn_view_dashboard, self.btn_view_settings]:
            btn.configure(fg_color="transparent")

        if view_name == "transactions":
            self.btn_view_ledger.configure(fg_color="#1f538d")
        elif view_name == "ai":
            self.btn_view_ai.configure(fg_color="#1f538d")
        elif view_name == "dashboard":
            self.btn_view_dashboard.configure(fg_color="#1f538d")
        elif view_name == "settings":
            self.btn_view_settings.configure(fg_color="#1f538d")

        for view in self.views.values():
            if view is not None:
                view.grid_remove()

        if self.views[view_name] is None:
            # print(f"[Lazy Load] Building {view_name} screen...")
            if view_name == "transactions":
                self.views[view_name] = TransactionsView(self, self.manager, self.db_session)
            elif view_name == "ai":
                self.views[view_name] = AIImportView(self, self.manager, self.db_session)
            elif view_name == "dashboard":
                self.views[view_name] = DashboardView(self, self.manager, self.db_session)
            elif view_name == "settings":
                self.views[view_name] = SettingsView(self, self.manager, self.db_session)

            self.views[view_name].grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        else:
            if hasattr(self.views[view_name], "refresh_view"):
                self.views[view_name].refresh_view()

        self.views[view_name].grid()

    def refresh_accounts(self):
        """Builds the account buttons and the Net Worth summary."""
        self.update_net_worth()

        # Account cards
        for widget in self.acc_scroll.winfo_children():
            widget.destroy()

        accounts = {a.id: a for a in self.db_session.query(Account).order_by(Account.name.asc()).all()}
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

            # Account colors
            is_active = acc.active_bool
            name_text = acc.name.upper() if is_active else f"{acc.name.upper()} (INACTIVE)"
            name_color = "white" if is_active else "gray50"

            if not is_active:
                bal_color = "gray50"
            else:
                bal_color = "#FF6B6B" if acc.balance < 0 else "white"

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
            ctk.CTkLabel(acc_card, text=name_text, text_color=name_color,
                         font=("JetBrains Mono", 10),
                         anchor="w", height=15).pack(fill="x", padx=10, pady=(5, 0))

            # Row 2: Balance
            ctk.CTkLabel(acc_card, text=f"{acc.balance:,.{acc.currency.decimals}f} {acc.currency_code}",
                         font=("JetBrains Mono", 12, "bold"), text_color=bal_color,
                         anchor="w", height=20).pack(fill="x", padx=10, pady=(0, 5))

            for child in acc_card.winfo_children():
                child.bind("<Button-1>", lambda e, aid=acc.id: self.handle_account_click(aid))
                child.bind("<Enter>", on_enter)
                child.bind("<Leave>", on_leave)

    def update_net_worth(self):
        """Calculates Net Worth and triggers the rolling number animation."""
        new_nw = self.manager.get_net_worth()

        if abs(new_nw - self.current_net_worth) < 0.01:
            settle_color = "#FF6B6B" if new_nw <= 0 else "white"
            self.lbl_nw_val.configure(text=f"{self.manager.base_currency_symbol} {new_nw:,.{self.manager.base_currency_decimals}f}",
                                      text_color=settle_color)
            return

        difference = new_nw - self.current_net_worth
        flash_color = "#4CD964" if difference > 0 else "#FF6B6B"
        settle_color = "#FF6B6B" if new_nw <= 0 else "white"

        self._animate_odometer(self.current_net_worth, new_nw, flash_color, settle_color, steps=20, current_step=0)

        self.current_net_worth = new_nw

    def _animate_odometer(self, start_val, end_val, flash_color, settle_color, steps, current_step):
        """Recursive Tkinter loop that physically rolls the numbers."""
        if current_step <= steps:
            progress = current_step / steps
            current_val = start_val + ((end_val - start_val) * progress)

            self.lbl_nw_val.configure(
                text=f"{self.manager.base_currency_symbol} {current_val:,.{self.manager.base_currency_decimals}f}",
                text_color=flash_color
            )
            self.after(15, self._animate_odometer, start_val, end_val, flash_color, settle_color, steps,
                       current_step + 1)
        else:
            self.lbl_nw_val.configure(
                text=f"{self.manager.base_currency_symbol} {end_val:,.{self.manager.base_currency_decimals}f}",
                text_color=settle_color
            )

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
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    return json.load(f).get("account_order", [])
        except (json.decoder.JSONDecodeError, IOError):
            return[]
        return []

    @staticmethod
    def save_account_order(order_list):
        """Saves the current list of account IDs to JSON."""
        config = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)

        config["account_order"] = order_list
        with open(CONFIG_PATH, "w") as f:
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

            self.refresh_accounts()

            self.switch_view("transactions")

            tx_view = self.views["transactions"]
            tx_view.current_page = 0
            tx_view.load_transactions()
            tx_view.reset_scroll_to_top()

    def _open_or_focus_transaction_window(self, window_type, window_class, transaction_data=None):
        """Ensures only one instance of a specific transaction window is open at a time."""
        attr_name = f"active_{window_type}_window"
        current_window = getattr(self, attr_name, None)

        if isinstance(current_window, ctk.CTkToplevel) and current_window.winfo_exists():
            current_window.deiconify()
            current_window.lift()
            current_window.focus_force()
        else:
            new_window = window_class(self, self.manager, transaction_data=transaction_data, db_session=self.db_session)
            setattr(self, attr_name, new_window)

    def _prepare_transaction_data(self, row_data, is_edit=False):
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
            t = self.db_session.get(Transfer, row_data.id)
            data["amount"] = t.amount_origin
            data["dest_amount"] = t.amount_destination
            data["orig_acc"] = t.origin_account.name
            data["dest_acc"] = t.destination_account.name

        return data

    def open_copy_transaction(self, row_data):
        """Strips the ID and opens the form as a new entry."""
        mapped_data = self._prepare_transaction_data(row_data, is_edit=False)
        if row_data.type == "expense":
            self._open_or_focus_transaction_window("expense", AddExpenseWindow, mapped_data)
        elif row_data.type == "gain":
            self._open_or_focus_transaction_window("gain", AddGainWindow, mapped_data)
        elif "transfer" in row_data.type:
            self._open_or_focus_transaction_window("transfer", AddTransferWindow, mapped_data)

    def open_edit_transaction(self, row_data):
        """
        Keeps the ID so the backend knows to upsert.
        Opens the form for editing.
        """
        mapped_data = self._prepare_transaction_data(row_data, is_edit=True)
        if row_data.type == "expense":
            self._open_or_focus_transaction_window("expense", AddExpenseWindow, mapped_data)
        elif row_data.type == "gain":
            self._open_or_focus_transaction_window("gain", AddGainWindow, mapped_data)
        elif "transfer" in row_data.type:
            self._open_or_focus_transaction_window("transfer", AddTransferWindow, mapped_data)

    def delete_transaction_prompt(self, transaction_id, transaction_type, context_text="", on_cancel=None):
        """Generates a popup to confirm deletion before modifying the DB."""
        active_window = None
        if transaction_type == "expense":
            active_window = getattr(self, "active_expense_window", None)
        elif transaction_type == "gain":
            active_window = getattr(self, "active_gain_window", None)
        elif "transfer" in transaction_type:
            active_window = getattr(self, "active_transfer_window", None)

        if isinstance(active_window, ctk.CTkToplevel) and active_window.winfo_exists():
            is_edit = getattr(active_window, "is_edit_mode", False)
            tx_data = getattr(active_window, "transaction_data", {})

            if is_edit and tx_data and tx_data.get("id") == transaction_id:
                if on_cancel: on_cancel()

                info_popup = ctk.CTkToplevel(self)
                info_popup.withdraw()
                info_popup.title("Action Blocked")
                info_popup.geometry("350x150")
                set_app_window_icon(info_popup)
                info_popup.attributes("-topmost", True)

                self.update_idletasks()
                x = self.winfo_x() + (self.winfo_width() // 2) - 175
                y = self.winfo_y() + (self.winfo_height() // 2) - 75
                info_popup.geometry(f"+{x}+{y}")

                ctk.CTkLabel(info_popup, text="Cannot delete this transaction.",
                             font=("JetBrains Mono", 13, "bold")).pack(pady=(25, 5))
                ctk.CTkLabel(info_popup, text="It is currently open in an Edit window.",
                             font=("JetBrains Mono", 11)).pack(pady=(0, 20))
                ctk.CTkButton(info_popup, text="OK", width=80, fg_color="#1f538d", command=info_popup.destroy).pack()
                info_popup.deiconify()
                info_popup.wait_visibility()
                info_popup.grab_set()
                return

        popup = ctk.CTkToplevel(self)
        popup.withdraw()
        popup.title("Confirm Delete")
        p_width = 350
        p_height = 170
        set_app_window_icon(popup)
        popup.attributes("-topmost", True)

        popup.geometry(calculate_dialog_geometry(self, p_width, p_height))

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
                tx_view = self.views.get("transactions")
                if isinstance(tx_view, TransactionsView):
                    tx_view.load_transactions()

            except Exception as e:
                print(f"Delete error: {e}")
            finally:
                popup.destroy()

        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="gray40", command=cancel_action).pack(side="left",
                                                                                                         padx=10)
        ctk.CTkButton(btn_frame, text="Delete", width=80, fg_color="#8b2525", hover_color="#611a1a",
                      command=confirm).pack(side="left", padx=10)

        popup.deiconify()
        popup.wait_visibility()
        popup.grab_set()

    def on_closing(self):
        """Ensures the DB session is safely closed before quitting."""
        try:
            self.db_session.close()
            # print("Database session closed successfully.")
            self.db_session.get_bind().dispose()
            # print("Database connection fully severed.")
            plt.close('all')
        except Exception as e:
            print(f"Error closing database session: {e}")
        finally:
            self.quit()
            self.destroy()

    def open_add_expense(self):
        self._open_or_focus_transaction_window("expense", AddExpenseWindow)

    def open_add_gain(self):
        self._open_or_focus_transaction_window("gain", AddGainWindow)

    def open_add_transfer(self):
        self._open_or_focus_transaction_window("transfer", AddTransferWindow)


if __name__ == "__main__":
    app = FinanceApp()
    app.mainloop()


