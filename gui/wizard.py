import customtkinter as ctk
from config import CURRENCY_SYMBOLS
from core.manager import seed_fresh_database
from utils.icon_manager import set_app_window_icon


class FirstRunWizard(ctk.CTkToplevel):
    def __init__(self, parent, db_session, on_complete_callback):
        super().__init__(parent)
        self.withdraw()
        self.parent_app = parent
        self.db_session = db_session
        self.on_complete_callback = on_complete_callback

        self.title("Welcome")
        self.geometry("450x550")
        set_app_window_icon(self)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (450 / 2))
        y = int((screen_height / 2) - (550 / 2))
        self.geometry(f"+{x}+{y}")

        self._build_ui()

        self.deiconify()
        self.wait_visibility()
        self.grab_set()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Welcome to VennLedger!", font=("JetBrains Mono", 20, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self,
                     text="Let's set up your database. Please select your\nprimary currency and starting balances.",
                     font=("JetBrains Mono", 12), text_color="gray60", justify="center").pack(pady=(0, 15))

        form_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        form_frame.pack(pady=10, padx=60, fill="x")

        ctk.CTkLabel(form_frame, text="Base Currency:", font=("JetBrains Mono", 12, "bold")).grid(row=0, column=0,
                                                                                                  sticky="e", padx=15,
                                                                                                  pady=10)
        codes = sorted([f"{c} - {d['name']}" for c, d in CURRENCY_SYMBOLS.items()]) + ["Custom..."]
        self.code_var = ctk.StringVar(value="EUR - Eurozone Euro")
        self.code_dropdown = ctk.CTkOptionMenu(form_frame, values=codes, variable=self.code_var, width=190,
                                               command=self._on_code_change)
        self.code_dropdown.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        self.custom_code_var = ctk.StringVar(value="")
        self.custom_code_entry = ctk.CTkEntry(form_frame, textvariable=self.custom_code_var, width=190,
                                              placeholder_text="Code (Max 10)")

        ctk.CTkLabel(form_frame, text="Symbol:", font=("JetBrains Mono", 12, "bold")).grid(row=2, column=0, sticky="e",
                                                                                           padx=15, pady=10)
        self.symbol_var = ctk.StringVar(value="€")
        self.symbol_dropdown = ctk.CTkOptionMenu(form_frame, values=["€"], variable=self.symbol_var, state="disabled",
                                                 width=190, command=self._on_symbol_change)
        self.symbol_dropdown.grid(row=2, column=1, sticky="w", padx=10, pady=10)

        self.custom_symbol_var = ctk.StringVar(value="")
        self.custom_symbol_entry = ctk.CTkEntry(form_frame, textvariable=self.custom_symbol_var, width=190,
                                                placeholder_text="Symbol")

        self.precision_lbl = ctk.CTkLabel(form_frame, text="# of Decimals:", font=("JetBrains Mono", 12, "bold"))
        self.precision_var = ctk.StringVar(value="2 (Standard Fiat)")
        self.precision_dropdown = ctk.CTkOptionMenu(
            form_frame,
            values=["0 (Whole Numbers)", "2 (Standard Fiat)", "8 (Crypto/Tokens)"],
            variable=self.precision_var,
            width=190,
            command=self._on_precision_change
        )
        self.decimals = 2

        bal_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        bal_frame.pack(pady=10, padx=60, fill="x")

        ctk.CTkLabel(bal_frame, text="Bank Account Balance:", font=("JetBrains Mono", 12, "bold")).grid(row=0, column=0,
                                                                                                        sticky="e",
                                                                                                        padx=15,
                                                                                                        pady=10)
        self.check_var = ctk.StringVar(value="0.00")
        self.check_entry = ctk.CTkEntry(bal_frame, textvariable=self.check_var, width=145)
        self.check_entry.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        ctk.CTkLabel(bal_frame, text="Cash Balance:", font=("JetBrains Mono", 12, "bold")).grid(row=1, column=0,
                                                                                                       sticky="e",
                                                                                                       padx=15, pady=10)
        self.cash_var = ctk.StringVar(value="0.00")
        self.cash_entry = ctk.CTkEntry(bal_frame, textvariable=self.cash_var, width=145)
        self.cash_entry.grid(row=1, column=1, sticky="w", padx=10, pady=10)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 11, "bold"))
        self.lbl_error.pack(pady=5)

        self.btn_start = ctk.CTkButton(self, text="Initialize Database", font=("JetBrains Mono", 13, "bold"), height=36,
                                       command=self._submit)
        self.btn_start.pack(pady=(5, 20))

        self._reformat_balances()

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

    def _on_code_change(self, selection):
        if selection == "Custom...":
            self.custom_code_entry.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 10))
            self.symbol_dropdown.configure(state="normal", values=["$", "€", "£", "¥", "₹", "Custom..."])
            self.symbol_var.set("$")
            self._on_symbol_change("$")
            self.precision_lbl.grid(row=4, column=0, sticky="e", padx=15, pady=(0, 10))
            self.precision_dropdown.grid(row=4, column=1, sticky="w", padx=10, pady=(0, 10))
            p_str = self.precision_var.get()
            if p_str.startswith("0"):
                self.decimals = 0
            elif p_str.startswith("8"):
                self.decimals = 8
            else:
                self.decimals = 2
            self._reformat_balances()
        else:
            self.custom_code_entry.grid_forget()
            self.custom_symbol_entry.grid_forget()
            self.precision_lbl.grid_forget()
            self.precision_dropdown.grid_forget()
            code = selection.split(" - ")[0]
            currency_data = CURRENCY_SYMBOLS.get(code, {"symbol": code, "decimals": 2})
            self.symbol_dropdown.configure(state="disabled", values=[currency_data["symbol"]])
            self.symbol_var.set(currency_data["symbol"])
            self.decimals = currency_data["decimals"]
            self._reformat_balances()

    def _on_symbol_change(self, selection):
        if selection == "Custom...":
            self.custom_symbol_entry.grid(row=3, column=1, sticky="w", padx=10, pady=(0, 10))
        else:
            self.custom_symbol_entry.grid_forget()

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

        selection = self.code_var.get()
        if selection == "Custom...":
            raw_code = self.custom_code_var.get().strip().upper()
            code = raw_code[:10]
            name = f"{code} Currency"

            p_str = self.precision_var.get()
            if p_str.startswith("0"):
                self.decimals = 0
            elif p_str.startswith("8"):
                self.decimals = 8
            else:
                self.decimals = 2
        else:
            code = selection.split(" - ")[0]
            name = selection.split(" - ")[1]

        sym_selection = self.symbol_var.get()
        raw_symbol = self.custom_symbol_var.get().strip()
        symbol = raw_symbol[:5] if sym_selection == "Custom..." else sym_selection

        if not code or not symbol:
            self.lbl_error.configure(text="⚠ Please provide both a Code and a Symbol.")
            return

        seed_fresh_database(self.db_session, code, name, symbol, check_bal, cash_bal, self.decimals)

        self.grab_release()
        self.destroy()
        self.on_complete_callback()


