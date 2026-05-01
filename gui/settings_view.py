import customtkinter as ctk
from database.models import Category, Stream, Vendor, Payer, Project
from gui.master_data_grids import (
    SimpleMasterDataGrid, CurrencyGrid, ExchangeRateGrid, AccountGrid, PMGrid
)

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, manager, db_session):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.manager = manager
        self.db_session = db_session

        self.settings_header = ctk.CTkLabel(self, text="Master Data Management",
                                            font=("JetBrains Mono", 22, "bold"))
        self.settings_header.pack(anchor="w", pady=(0, 20))

        self.settings_tabview = ctk.CTkTabview(self, command=self.on_tab_change)
        self.settings_tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_accounts = self.settings_tabview.add("Accounts & Payment Methods")
        self.tab_currencies = self.settings_tabview.add("Currencies & FX")
        self.tab_categories = self.settings_tabview.add("Categories & Streams")
        self.tab_entities = self.settings_tabview.add("Vendors & Payers")
        self.tab_projects = self.settings_tabview.add("Projects")

        self.loaded_tabs = {
            "Accounts & Payment Methods": False,
            "Currencies & FX": False,
            "Categories & Streams": False,
            "Vendors & Payers": False,
            "Projects": False
        }

        self.acc_grid = self.pm_grid\
        = self.cat_grid = self.stream_grid\
        = self.vendor_grid = self.payer_grid\
        = self.proj_grid = self.curr_grid\
        = self.fx_grid = None

        self.after(50, self.on_tab_change)

    def on_tab_change(self):
        """Fires whenever a tab is clicked. Lazy-loads the content."""
        current_tab = self.settings_tabview.get()

        if not self.loaded_tabs[current_tab]:
            print(f"[Lazy Load] Building grids for tab: {current_tab}...")
            self.build_tab_content(current_tab)
            self.loaded_tabs[current_tab] = True

    def build_tab_content(self, tab_name):
        """Instantiates the  MD grids for the requested tab."""

        if tab_name == "Accounts & Payment Methods":

            self.tab_accounts.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
            self.tab_accounts.grid_rowconfigure(0, weight=1)

            self.acc_grid = AccountGrid(self.tab_accounts, self.db_session)
            self.acc_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            self.pm_grid = PMGrid(self.tab_accounts, self.db_session)
            self.pm_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

            self.acc_grid.bind("<<DataChanged>>", self.pm_grid.load_data)

        elif tab_name == "Categories & Streams":

            self.tab_categories.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
            self.tab_categories.grid_rowconfigure(0, weight=1)

            self.cat_grid = SimpleMasterDataGrid(self.tab_categories, self.db_session, Category, "Categories (Expenses)")
            self.cat_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            self.stream_grid = SimpleMasterDataGrid(self.tab_categories, self.db_session, Stream, "Streams (Gains)")
            self.stream_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        elif tab_name == "Vendors & Payers":

            self.tab_entities.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
            self.tab_entities.grid_rowconfigure(0, weight=1)

            self.vendor_grid = SimpleMasterDataGrid(self.tab_entities, self.db_session, Vendor, "Vendors (Outbound)")
            self.vendor_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            self.payer_grid = SimpleMasterDataGrid(self.tab_entities, self.db_session, Payer, "Payers (Inbound)")
            self.payer_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        elif tab_name == "Projects":

            self.tab_projects.grid_columnconfigure(0, weight=1)
            self.tab_projects.grid_rowconfigure(0, weight=1)

            self.proj_grid = SimpleMasterDataGrid(self.tab_projects, self.db_session, Project, "Projects", has_desc=True)
            self.proj_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        elif tab_name == "Currencies & FX":

            self.tab_currencies.grid_columnconfigure((0, 1), weight=1, uniform="tab_col")
            self.tab_currencies.grid_rowconfigure(0, weight=1)

            self.curr_grid = CurrencyGrid(self.tab_currencies, self.db_session)
            self.curr_grid.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            self.fx_grid = ExchangeRateGrid(self.tab_currencies, self.db_session)
            self.fx_grid.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")


