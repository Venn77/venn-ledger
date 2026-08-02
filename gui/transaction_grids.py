import customtkinter as ctk
from gui.widgets import TransactionRow


class TransactionGrid(ctk.CTkScrollableFrame):
    def __init__(self, parent, app_ref):
        super().__init__(parent, label_text="History")
        self.app = app_ref

    def render_rows(self, results, dec_map):
        """Wipes the current grid and draws the new page of transactions."""
        for widget in self.winfo_children():
            widget.destroy()

        self.update_idletasks()

        for row_data in results:
            TransactionRow(self, self.app, row_data, dec_map)


