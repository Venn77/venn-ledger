import customtkinter as ctk
from database.models import (
    session, Account, Expense, Gain, Category,
    PaymentMethod, Vendor, Currency, Project,
    Transfer, Payer, Stream
)
from core import manager as finance_manager
from core.ai_parser import chunk_file_by_day, get_structured_data
from sqlalchemy import (
    desc, or_, func, column, literal_column,
    union_all, asc, case
)
from sqlalchemy.orm import aliased
from customtkinter import filedialog
import datetime, json, os, threading
from gui.widgets import ToolTip, TransactionRow
from gui.dialogs import open_calendar
from gui.transaction_forms import AddExpenseWindow, AddGainWindow, AddTransferWindow
from gui.master_data_views import (
    SimpleMasterDataGrid, CurrencyGrid, ExchangeRateGrid,
    AccountGrid, PMGrid
)
from gui.ai_views import AIStagingGrid


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
        self.page_size = 25
        self.total_pages = 0
        self.jump_entry = None
        self.search_timer = None
        self.current_search_text = ""
        self.nav_timer = None
        self.type_timer = None
        self.page_timer = None

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

        self.update_idletasks()

    def show_transactions_view(self):
        self._hide_all_views()
        self.main_frame.grid()
        self.btn_view_ledger.configure(fg_color="#1f538d")
        self.load_transactions()

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

    def _reset_ai_view(self, success_msg=None, clear_text=True):
        """Wipes the staging grid & preview and restores the config panel to default."""
        if clear_text:
            self.ai_year_combo.configure(state="normal")
            self.ai_year_combo.set(str(datetime.datetime.now().year))
            self.ai_curr_combo.configure(state="normal")
            self.ai_curr_combo.set("EUR")
            self.ai_proj_combo.configure(state="normal")
            self.ai_proj_combo.set("None")
            self.btn_browse.configure(state="normal")

            self.ai_full_filepath = ""
            self.ai_filepath_var.set("No file selected...")
            self.file_tooltip.text = "Please select a text file."

            for widget in self.preview_container.winfo_children():
                widget.destroy()
            self.preview_container.update_idletasks()
            self.preview_container.pack_forget()

            self.btn_cancel_ai.pack_forget()
            self.btn_clear_ai.pack_forget()
            self.btn_start_ai.pack(side="left")

            self.staging_header.pack_forget()

        else:
            self.btn_cancel_ai.pack_forget()
            self.btn_start_ai.pack_forget()
            self.btn_clear_ai.pack(side="left")
            self.btn_clear_ai.configure(state="normal")
            self.preview_container.pack(fill="both", expand=True)

            if hasattr(self, 'staging_title'):
                self.staging_title.configure(text="File Preview")

            self.btn_import_all.pack_forget()

            if hasattr(self, 'btn_toggle_view'):
                self.btn_toggle_view.pack_forget()

        self.ai_progress_bar.pack_forget()

        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self.grid_container.update_idletasks()

        self.btn_import_all.configure(text="✅ Import All", state="disabled", fg_color="#4CD964", text_color="black")

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

        self.grid_container.update_idletasks()
        self.preview_container.update_idletasks()

        grid = AIStagingGrid(self.grid_container, parsed_results, year, project, self, self.btn_import_all)
        grid.pack(fill="both", expand=True)

        self.btn_import_all.configure(command=grid.execute_import)

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

        self.update_idletasks()

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

    def _schedule_page_render(self):
        """Debounces pagination to prevent DB/Render lag on rapid clicks."""
        if self.page_timer:
            self.after_cancel(self.page_timer)
        self.page_timer = self.after(300, self._execute_page_render)

    def _execute_page_render(self):
        """Fires the actual database query and redraws the UI."""
        self.page_timer = None
        self.load_transactions()
        if self.current_page == self.total_pages - 1:
            self.reset_scroll_to_top()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            if self.jump_entry:
                self.jump_entry.delete(0, "end")
                self.jump_entry.insert(0, str(self.current_page + 1))

            self._schedule_page_render()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            if self.jump_entry:
                self.jump_entry.delete(0, "end")
                self.jump_entry.insert(0, str(self.current_page + 1))

            self._schedule_page_render()

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


