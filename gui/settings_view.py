import customtkinter as ctk
from config import USER_CONFIG_DIR, DB_PATH, TOKEN_PATH
from database.models import Category, Stream, Vendor, Payer, Project
from gui.master_data_grids import (
    SimpleMasterDataGrid, CurrencyGrid, ExchangeRateGrid, AccountGrid, PMGrid
)
from gui.dialogs import show_popup
from customtkinter import filedialog
import datetime, os, threading
from utils.fs_utils import export_data_to_csv, backup_sqlite_db
from utils.cld_utils import upload_to_drive
from utils.icon_manager import get_icon


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, manager, db_session):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.manager = manager
        self.db_session = db_session

        self.drive_icon = get_icon("gdrive.png", size=(18, 18))
        self.csv_icon = get_icon("csv.png")
        self.backup_db_icon = get_icon("file_save.png", size=(18, 18))

        self.settings_header = ctk.CTkLabel(self, text="Master Data Management",
                                            font=("JetBrains Mono", 22, "bold"))
        self.settings_header.pack(anchor="w", pady=(0, 20))

        self.settings_tabview = ctk.CTkTabview(self, command=self.on_tab_change)
        self.settings_tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.data_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.data_frame.pack(fill="x", pady=(20, 0), padx=10)

        ctk.CTkLabel(self.data_frame, text="BKP Tools", font=("JetBrains Mono", 16, "bold")).pack(anchor="w",
                                                                                                     pady=(0, 10))

        self.btn_frame = ctk.CTkFrame(self.data_frame, fg_color="transparent")
        self.btn_frame.pack(anchor="w")

        ctk.CTkButton(self.btn_frame, text="Export to CSV", image=self.csv_icon, anchor="center", width=150, fg_color="#1f538d", hover_color="#14375e",
                      command=self.ui_export_csv).pack(side="left", padx=(0, 10))

        ctk.CTkButton(self.btn_frame, text="Backup Database", image=self.backup_db_icon, anchor="center", width=150, fg_color="#4CD964", text_color="black",
                      hover_color="#3cb050",
                      command=self.ui_backup_database).pack(side="left")

        ctk.CTkButton(self.btn_frame, text="Backup to Drive", image=self.drive_icon, anchor="center", width=150, fg_color="#FF9F0A", text_color="black",
                      hover_color="#cc7f08",
                      command=self.ui_cloud_backup).pack(side="left", padx=(10, 0))

        ctk.CTkButton(self.btn_frame, text="Open Config Folder", anchor="center", width=150,
                      fg_color="#1f538d",
                      hover_color="#14375e",
                      command=lambda: os.startfile(USER_CONFIG_DIR)).pack(side="left", padx=(10, 0))

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
        = self.fx_grid = self.loading_popup\
        = self._backup_cancelled = None
        # noinspection PyTypeChecker
        self.after(50, self.on_tab_change)

    def on_tab_change(self):
        """Fires whenever a tab is clicked. Lazy-loads the content."""
        current_tab = self.settings_tabview.get()

        if not self.loaded_tabs[current_tab]:
            print(f"[Lazy Load] Building grids for tab: {current_tab}...")
            self.build_tab_content(current_tab)
            self.loaded_tabs[current_tab] = True

    def build_tab_content(self, tab_name):
        """Instantiates the MD grids for the requested tab."""
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

    def ui_export_csv(self):
        """UI wrapper for the CSV export process."""
        default_name = f"VennExpense_Export_{datetime.date.today().strftime('%Y%m%d')}.csv"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=default_name,
            title="Export Data",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if not filepath:
            return

        success, message = export_data_to_csv(self.db_session, filepath)

        if success:
            show_popup(self,"Export Successful", message, is_error=False)
        else:
            show_popup(self,"Export Failed", message, is_error=True)

    def ui_backup_database(self):
        """UI wrapper for the SQLite backup process."""
        default_name = f"VennExpense_Backup_{datetime.date.today().strftime('%Y%m%d')}.db"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".db",
            initialfile=default_name,
            title="Backup Database",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )

        if not filepath:
            return

        source_db = DB_PATH

        success, message = backup_sqlite_db(self.db_session, source_db, filepath)

        if success:
            show_popup(self,"Backup Successful", message, is_error=False)
        else:
            show_popup(self,"Backup Failed", message, is_error=True)

    def ui_cloud_backup(self):
        """UI wrapper for the Google Drive backup process."""
        self._backup_cancelled = False

        if not os.path.exists(TOKEN_PATH):
            show_popup(
                self,
                title="First Time Setup",
                message="To back up to Google Drive, a browser window will open so you can log in.\n\nProceed?",
                show_cancel=True,
                ok_command=lambda: self._start_cloud_backup_process(waiting_for_auth=True)
            )
        else:
            self._start_cloud_backup_process(waiting_for_auth=False)

    def _start_cloud_backup_process(self, waiting_for_auth=False):
        """Performs local db backup before initiating cloud backup."""
        def abort_backup():
            self._backup_cancelled = True

        title = "Authenticating..." if waiting_for_auth else "Cloud Backup"
        msg = "Waiting for Google Login in your browser..." if waiting_for_auth else "Uploading database to Drive..."

        self.loading_popup = show_popup(self, title, msg, show_ok=False, show_cancel=waiting_for_auth, cancel_command=abort_backup)
        self.update()

        filename = f"VennExpense_CloudBackup_{datetime.date.today().strftime('%Y%m%d')}.db"
        temp_filepath = os.path.join(USER_CONFIG_DIR, filename)

        success, message = backup_sqlite_db(self.app.db_session, DB_PATH, temp_filepath)

        if not success:
            if hasattr(self, 'loading_popup') and self.loading_popup.winfo_exists():
                self.loading_popup.destroy()
                delattr(self, 'loading_popup')
                self.update()

            show_popup(self, "Error", f"Failed to prepare database:\n{message}", is_error=True)
            return

        threading.Thread(target=self._cloud_backup_worker, args=(temp_filepath, filename), daemon=True).start()

    def _cloud_backup_worker(self, temp_filepath, filename):
        """Handles cloud backup operations in a separate thread."""
        cloud_success, cloud_msg = upload_to_drive(temp_filepath, filename)

        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

        self.after(0, self._cloud_backup_finish, cloud_success, cloud_msg)

    def _cloud_backup_finish(self, success, message):
        """Reports back results to the main thread."""
        if getattr(self, '_backup_cancelled', False):
            return

        if hasattr(self, 'loading_popup') and self.loading_popup.winfo_exists():
            self.loading_popup.destroy()
            delattr(self, 'loading_popup')
            self.update()

        if success:
            show_popup(self, "Success", message, is_error=False)
        else:
            show_popup(self, "Cloud Error", message, is_error=True)

    def refresh_view(self):
        """Called automatically when switching back to this tab.
        Refreshes the database queries for any Master Data grids that have been loaded."""
        grids = [
            self.acc_grid, self.pm_grid,
            self.cat_grid, self.stream_grid,
            self.vendor_grid, self.payer_grid,
            self.proj_grid,
            self.curr_grid, self.fx_grid
        ]

        for grid in grids:
            if grid is not None and hasattr(grid, "load_data"):
                grid.load_data()

