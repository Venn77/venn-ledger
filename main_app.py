import customtkinter as ctk
import matplotlib.pyplot as plt
from typing import Any
from database.models import Session, Account, Transfer
from core import manager as finance_manager
import json, os
from gui.transaction_forms import AddExpenseWindow, AddGainWindow, AddTransferWindow
from gui.transactions_view import TransactionsView
from gui.settings_view import SettingsView
from gui.ai_view import AIImportView
from gui.dashboard_view import DashboardView


class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Venn Ledger 2026")
        self.geometry("1440x700")
        self.minsize(1440, 700)
        self.maxsize(1440,980)
        ctk.set_appearance_mode("dark")
        self.db_session = Session()
        self.manager = finance_manager.TransactionManager(self.db_session)
        self.cal_window = None
        self.reorder_mode = None
        self.selected_account_id = None
        self.filter_account_id = None

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

        self.switch_view("transactions")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

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

        self.reorder_btn = ctk.CTkButton(self.sidebar, text="⇅ Reorder Accounts", fg_color="transparent",
                                         border_width=1, command=self.toggle_reorder_mode)
        self.reorder_btn.pack(pady=(10, 5), padx=20, fill="x")

        self.nav_group = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_group.pack(side="bottom", fill="x", pady=20, padx=15)

        self.btn_view_ledger = ctk.CTkButton(self.nav_group, text="📊 Transactions",
                                             anchor="w", command=lambda: self.switch_view("transactions"))
        self.btn_view_ledger.pack(fill="x", pady=2)

        self.btn_view_ai = ctk.CTkButton(self.nav_group, text="⚡ AI Import",
                                         anchor="w", command=lambda: self.switch_view("ai"))
        self.btn_view_ai.pack(fill="x", pady=2)

        self.btn_view_dashboard = ctk.CTkButton(self.nav_group, text="📈 Dashboard",
                                         anchor="w", command=lambda: self.switch_view("dashboard"))
        self.btn_view_dashboard.pack(fill="x", pady=2)

        self.btn_view_settings = ctk.CTkButton(self.nav_group, text="⚙️ Master Data",
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
            print(f"[Lazy Load] Building {view_name} screen...")
            if view_name == "transactions":
                self.views[view_name] = TransactionsView(self, self.manager, self.db_session)
            elif view_name == "ai":
                self.views[view_name] = AIImportView(self, self.manager, self.db_session)
            elif view_name == "dashboard":
                self.views[view_name] = DashboardView(self, self.manager, self.db_session)
            elif view_name == "settings":
                self.views[view_name] = SettingsView(self, self.manager, self.db_session)

            self.views[view_name].grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

        self.views[view_name].grid()

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
            if os.path.exists("config/config.json"):
                with open("config/config.json", "r") as f:
                    return json.load(f).get("account_order", [])
        except (json.decoder.JSONDecodeError, IOError):
            return[]
        return []

    @staticmethod
    def save_account_order(order_list):
        """Saves the current list of account IDs to JSON."""
        config = {}
        if os.path.exists("config/config.json"):
            with open("config/config.json", "r") as f:
                config = json.load(f)

        config["account_order"] = order_list
        with open("config/config.json", "w") as f:
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
            AddExpenseWindow(self, self.manager, transaction_data=mapped_data, db_session=self.db_session)
        elif row_data.type == "gain":
            AddGainWindow(self, self.manager, transaction_data=mapped_data, db_session=self.db_session)
        elif "transfer" in row_data.type:
            AddTransferWindow(self, self.manager, transaction_data=mapped_data, db_session=self.db_session)

    def open_edit_transaction(self, row_data):
        """
        Keeps the ID so the backend knows to upsert.
        Opens the form for editing.
        """
        mapped_data = self._prepare_transaction_data(row_data, is_edit=True)
        if row_data.type == "expense":
            AddExpenseWindow(self, self.manager, transaction_data=mapped_data, db_session=self.db_session)
        elif row_data.type == "gain":
            AddGainWindow(self, self.manager, transaction_data=mapped_data, db_session=self.db_session)
        elif "transfer" in row_data.type:
            AddTransferWindow(self, self.manager, transaction_data=mapped_data, db_session=self.db_session)

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

    def on_closing(self):
        """Ensures the DB session is safely closed before quitting."""
        try:
            self.db_session.close()
            print("Database session closed successfully.")
            self.db_session.get_bind().dispose()
            print("Database connection fully severed.")
            plt.close('all')
        except Exception as e:
            print(f"Error closing database session: {e}")
        finally:
            self.quit()
            self.destroy()

    def open_add_expense(self):
        AddExpenseWindow(self, self.manager, db_session=self.db_session)

    def open_add_gain(self):
        AddGainWindow(self, self.manager, db_session=self.db_session)

    def open_add_transfer(self):
        AddTransferWindow(self, self.manager, db_session=self.db_session)


if __name__ == "__main__":
    app = FinanceApp()
    # noinspection PyTypeChecker
    app.after(0, lambda: app.state('zoomed'))
    app.mainloop()


