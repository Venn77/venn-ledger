import customtkinter as ctk
from models import session, Account, Expense, Gain
from sqlalchemy import desc


class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Venn Ledger 2026")
        self.geometry("1100x700")
        ctk.set_appearance_mode("dark")

        # 1. Grid Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 2. Sidebar (Accounts & Quick Actions)
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.logo = ctk.CTkLabel(self.sidebar, text="FINANCE", font=("Arial", 24, "bold"))
        self.logo.pack(pady=30, padx=20)

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
        accounts = session.query(Account).all()
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


if __name__ == "__main__":
    app = FinanceApp()
    app.mainloop()