import customtkinter as ctk
from config import CURRENCY_SYMBOLS
from core.manager import seed_fresh_database


class FirstRunWizard(ctk.CTkToplevel):
    def __init__(self, parent, db_session, on_complete_callback):
        super().__init__(parent)
        self.parent_app = parent
        self.db_session = db_session
        self.on_complete_callback = on_complete_callback

        self.title("Welcome")
        self.geometry("450x480")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self.protocol("WM_DELETE_WINDOW", self._on_close_attempt)
        self.grab_set()

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (450 / 2))
        y = int((screen_height / 2) - (480 / 2))
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Welcome to VennLedger!", font=("JetBrains Mono", 20, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(self,
                     text="Let's set up your database. Please select your\nprimary currency and starting balances.",
                     font=("JetBrains Mono", 12), text_color="gray60", justify="center").pack(pady=(0, 15))

        form_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        form_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(form_frame, text="Base Currency:", font=("JetBrains Mono", 12, "bold")).grid(row=0, column=0,
                                                                                                  sticky="e", padx=15,
                                                                                                  pady=10)
        codes = sorted(list(CURRENCY_SYMBOLS.keys())) + ["Custom..."]
        self.code_var = ctk.StringVar(value="EUR")
        self.code_dropdown = ctk.CTkOptionMenu(form_frame, values=codes, variable=self.code_var,
                                               command=self._on_code_change)
        self.code_dropdown.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        self.custom_code_var = ctk.StringVar(value="")
        self.custom_code_entry = ctk.CTkEntry(form_frame, textvariable=self.custom_code_var, width=80,
                                              placeholder_text="e.g. BTC")

        ctk.CTkLabel(form_frame, text="Symbol:", font=("JetBrains Mono", 12, "bold")).grid(row=2, column=0, sticky="e",
                                                                                           padx=15, pady=10)
        self.symbol_var = ctk.StringVar(value="€")
        self.symbol_entry = ctk.CTkEntry(form_frame, textvariable=self.symbol_var, width=60, state="disabled",
                                         text_color="#5AC8FA", font=("JetBrains Mono", 14, "bold"))
        self.symbol_entry.grid(row=2, column=1, sticky="w", padx=10, pady=10)

        bal_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        bal_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(bal_frame, text="Bank Account Balance:", font=("JetBrains Mono", 12, "bold")).grid(row=0, column=0,
                                                                                                        sticky="e",
                                                                                                        padx=15,
                                                                                                        pady=10)
        self.check_var = ctk.StringVar(value="0.00")
        self.check_entry = ctk.CTkEntry(bal_frame, textvariable=self.check_var, width=100)
        self.check_entry.grid(row=0, column=1, sticky="w", padx=10, pady=10)

        ctk.CTkLabel(bal_frame, text="Cash Balance:", font=("JetBrains Mono", 12, "bold")).grid(row=1, column=0,
                                                                                                       sticky="e",
                                                                                                       padx=15, pady=10)
        self.cash_var = ctk.StringVar(value="0.00")
        self.cash_entry = ctk.CTkEntry(bal_frame, textvariable=self.cash_var, width=100)
        self.cash_entry.grid(row=1, column=1, sticky="w", padx=10, pady=10)

        self.lbl_error = ctk.CTkLabel(self, text="", text_color="#FF6B6B", font=("JetBrains Mono", 11, "bold"))
        self.lbl_error.pack(pady=5)

        self.btn_start = ctk.CTkButton(self, text="Initialize Database", font=("JetBrains Mono", 13, "bold"), height=36,
                                       command=self._submit)
        self.btn_start.pack(pady=(5, 20))

    def _on_code_change(self, new_code):
        if new_code == "Custom...":
            self.custom_code_entry.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 10))
            self.symbol_entry.configure(state="normal")
            self.symbol_var.set("")
        else:
            self.custom_code_entry.grid_forget()
            self.symbol_entry.configure(state="disabled")
            self.symbol_var.set(CURRENCY_SYMBOLS.get(new_code, new_code))

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

        raw_code = self.code_var.get()
        code = self.custom_code_var.get().strip().upper() if raw_code == "Custom..." else raw_code
        symbol = self.symbol_var.get().strip()

        if raw_code == "Custom..." and (not code or not symbol):
            self.lbl_error.configure(text="⚠ Please provide both a Code and a Symbol.")
            return

        seed_fresh_database(self.db_session, code, f"{code} Currency", symbol, check_bal, cash_bal)

        self.grab_release()
        self.destroy()
        self.on_complete_callback()


