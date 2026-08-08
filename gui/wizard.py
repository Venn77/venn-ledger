import customtkinter as ctk
from config import CURRENCY_SYMBOLS
from core.manager import seed_fresh_database
from utils.icon_manager import set_app_window_icon
from utils.ctk_utils import apply_placeholder
from gui.dialogs import SearchableListDialog
from gui.widgets import CompoundDropdown


class FirstRunWizard(ctk.CTkToplevel):
    def __init__(self, parent, db_session, on_complete_callback):
        super().__init__(parent)
        self.withdraw()
        self.parent_app = parent
        self.db_session = db_session
        self.on_complete_callback = on_complete_callback

        self.title("Welcome")
        self.geometry("540x620")
        set_app_window_icon(self)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self.custom_code_placeholder = "Code ONLY (e.g. BTC) (Max 10)"
        self.custom_symbol_placeholder = "Raw Symbol (e.g. ₿)"

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (540 / 2))
        y = int((screen_height / 2) - (620 / 2))
        self.geometry(f"+{x}+{y}")

        self._build_ui()

        self.after(150,lambda: self.deiconify())
        self.wait_visibility()
        self.grab_set()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Welcome to VennLedger!", font=("JetBrains Mono", 20, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self,
                     text="Let's set up your database. Please select your\nprimary currency and starting balances.",
                     font=("JetBrains Mono", 12), text_color="gray60", justify="center").pack(pady=(0, 15))

        form_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        form_frame.pack(pady=10, padx=50, fill="x")

        self.lbl_currency = ctk.CTkLabel(form_frame, text="Base Currency:", font=("JetBrains Mono", 12, "bold"), width=170, anchor="e")
        self.lbl_currency.grid(row=0, column=0, sticky="e", padx=(15, 5), pady=(15, 5))

        self.code_var = ctk.StringVar(self, value="EUR - Eurozone Euro")
        self.code_dropdown = CompoundDropdown(
            form_frame, variable=self.code_var, command=self._open_currency_picker
        )
        self.code_dropdown.grid(row=0, column=1, sticky="w", padx=10, pady=(15, 5))

        self.custom_code_entry = ctk.CTkEntry(form_frame,width=200)
        apply_placeholder(self.custom_code_entry, self.custom_code_placeholder)

        self.is_custom_var = ctk.BooleanVar(self, value=False)
        self.chk_custom = ctk.CTkCheckBox(
            form_frame, text="Define custom currency", variable=self.is_custom_var,
            command=self._on_custom_currency_toggle, font=("JetBrains Mono", 11)
        )
        self.chk_custom.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 15))

        self.lbl_symbol = ctk.CTkLabel(form_frame, text="Symbol:", font=("JetBrains Mono", 12, "bold"), width=170,
                                       anchor="e")
        self.lbl_symbol.grid(row=2, column=0, sticky="e", padx=(15, 5), pady=(0, 5))
        self.symbol_var = ctk.StringVar(self, value="€")
        self.symbol_dropdown = CompoundDropdown(
            form_frame, variable=self.symbol_var, command=self._open_symbol_picker
        )
        self.symbol_dropdown.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 5))
        self.symbol_dropdown.set_disabled(True)

        self.custom_symbol_entry = ctk.CTkEntry(form_frame, width=200)
        apply_placeholder(self.custom_symbol_entry, self.custom_symbol_placeholder)

        self.is_custom_sym_var = ctk.BooleanVar(self, value=False)
        self.chk_custom_symbol = ctk.CTkCheckBox(
            form_frame, text="Enter manual symbol", variable=self.is_custom_sym_var,
            command=self._on_custom_symbol_toggle, font=("JetBrains Mono", 11)
        )

        self.lbl_precision = ctk.CTkLabel(form_frame, text="# of Decimals:", font=("JetBrains Mono", 12, "bold"))
        self.precision_var = ctk.StringVar(self, value="2 (Standard Fiat)")
        self.precision_dropdown = ctk.CTkOptionMenu(
            form_frame,
            values=["0 (Whole Numbers)", "2 (Standard Fiat)", "8 (Crypto/Tokens)"],
            variable=self.precision_var,
            width=200,
            command=self._on_precision_change
        )
        self.decimals = 2

        bal_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        bal_frame.pack(pady=10, padx=50, fill="x")

        ctk.CTkLabel(bal_frame, text="Bank Account Balance:", font=("JetBrains Mono", 12, "bold"), width=170, anchor="e").grid(row=0, column=0, sticky="e", padx=(15, 5), pady=10)
        self.check_var = ctk.StringVar(self, value="0.00")
        self.check_entry = ctk.CTkEntry(bal_frame, textvariable=self.check_var, width=200)
        self.check_entry.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        ctk.CTkLabel(bal_frame, text="Cash Balance:", font=("JetBrains Mono", 12, "bold"), width=170, anchor="e").grid(row=1, column=0, sticky="e", padx=(15, 5), pady=10)
        self.cash_var = ctk.StringVar(self, value="0.00")
        self.cash_entry = ctk.CTkEntry(bal_frame, textvariable=self.cash_var, width=200)
        self.cash_entry.grid(row=1, column=1, sticky="w", padx=10, pady=10)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 11, "bold"))
        self.lbl_error.pack(pady=5)

        self.btn_start = ctk.CTkButton(self, text="Initialize Database", font=("JetBrains Mono", 13, "bold"), height=36,
                                       command=self._submit)
        self.btn_start.pack(pady=(5, 20))

        self._reformat_balances()

    def _open_currency_picker(self):
        codes = sorted([f"{c} - {d['name']}" for c, d in CURRENCY_SYMBOLS.items()])

        dialog = SearchableListDialog(self, title="Select Currency", items=codes)
        selection = dialog.get_result()

        if selection:
            self.code_var.set(selection)
            self._apply_standard_currency(selection)

    def _open_symbol_picker(self):
        unique_symbols = sorted(list(set([d["symbol"] for d in CURRENCY_SYMBOLS.values()])))
        dialog = SearchableListDialog(self, title="Select Symbol", items=unique_symbols, show_search=False)
        selection = dialog.get_result()

        if selection:
            self.symbol_var.set(selection)

    def _apply_standard_currency(self, selection):
        code = selection.split(" - ")[0]
        currency_data = CURRENCY_SYMBOLS.get(code, {"symbol": code, "decimals": 2})
        self.symbol_var.set(currency_data["symbol"])
        self.decimals = currency_data["decimals"]
        self._reformat_balances()

    def _on_custom_currency_toggle(self):
        is_custom = self.is_custom_var.get()
        if is_custom:
            self.code_dropdown.grid_forget()
            self.lbl_currency.configure(text="Custom Code:")
            self.custom_code_entry.grid(row=0, column=1, sticky="w", padx=10, pady=(15, 5))

            self.symbol_dropdown.set_disabled(False)
            self.chk_custom_symbol.grid(row=3, column=1, sticky="w", padx=10, pady=(0, 15))
            self._on_custom_symbol_toggle()

            self.lbl_precision.grid(row=4, column=0, sticky="e", padx=(15, 5), pady=(0, 15))
            self.precision_dropdown.grid(row=4, column=1, sticky="w", padx=10, pady=(0, 15))
            self._on_precision_change(self.precision_var.get())
        else:
            self.custom_code_entry.grid_forget()
            self.lbl_currency.configure(text="Base Currency:")
            self.code_dropdown.grid(row=0, column=1, sticky="w", padx=10, pady=(15, 5))

            self.chk_custom_symbol.grid_forget()
            self.custom_symbol_entry.grid_forget()
            self.symbol_dropdown.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 5))
            self.symbol_dropdown.set_disabled(True)

            self.lbl_precision.grid_forget()
            self.precision_dropdown.grid_forget()

            self._apply_standard_currency(self.code_var.get())

    def _on_custom_symbol_toggle(self):
        if self.is_custom_sym_var.get():
            self.symbol_dropdown.grid_forget()
            self.custom_symbol_entry.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 5))
        else:
            self.custom_symbol_entry.grid_forget()
            self.symbol_dropdown.grid(row=2, column=1, sticky="w", padx=10, pady=(0, 5))

    def _reformat_balances(self):
        """Reads the current float values and reapplies the correct decimal formatting."""
        for var in [self.check_var, self.cash_var]:
            raw = var.get().strip().replace(",", ".")
            try:
                val = float(raw) if raw else 0.0
            except ValueError:
                val = 0.0

            var.set(f"{val:.{self.decimals}f}")

    def _on_precision_change(self, selection):
        """Triggers when the user changes precision manually in 'Custom...' mode."""
        if selection.startswith("0"):
            self.decimals = 0
        elif selection.startswith("8"):
            self.decimals = 8
        else:
            self.decimals = 2

        self._reformat_balances()

    def _on_close_attempt(self):
        self.parent_app.on_closing()

    def _submit(self):
        raw_check = self.check_var.get().strip().replace(",", ".")
        raw_cash = self.cash_var.get().strip().replace(",", ".")

        try:
            check_bal = float(raw_check) if raw_check else 0.0
            cash_bal = float(raw_cash) if raw_cash else 0.0
        except ValueError:
            self.lbl_error.configure(text="⚠ Balances must be valid numbers (e.g. 1500.50)")
            return

        if self.is_custom_var.get():
            code_text = self.custom_code_entry.get().strip()
            if code_text == self.custom_code_placeholder:
                code_text = ""
            raw_code = code_text.upper()
            code = raw_code[:10]
            name = f"{code} Currency"

            if self.is_custom_sym_var.get():
                sym_text = self.custom_symbol_entry.get().strip()
                if sym_text == self.custom_symbol_placeholder:
                    sym_text = ""
                symbol = sym_text[:5]
            else:
                symbol = self.symbol_var.get()

            if not code or not symbol:
                self.lbl_error.configure(text="⚠ Please provide both a Custom Code and Symbol.")
                return
        else:
            selection = self.code_var.get()
            code = selection.split(" - ")[0]
            name = selection.split(" - ")[1]
            symbol = self.symbol_var.get()

        seed_fresh_database(self.db_session, code, name, symbol, check_bal, cash_bal, self.decimals)

        self.grab_release()
        self.destroy()
        self.on_complete_callback()


