import customtkinter as ctk
import threading, datetime, sys
from config import IS_STEAMOS
from database.models import (
    Category, Currency, Project
)
from sqlalchemy import collate
from core.ai_parser import (
    DEFAULT_PROMPT_TEMPLATE, DEFAULT_SKIP_TERMS_TEXT,
    chunk_file_by_day, get_structured_data,
    get_skip_terms, get_row_prompt
)
from utils.fs_utils import open_text_config
from utils.icon_manager import get_icon
from customtkinter import filedialog
from gui.widgets import ToolTip
from gui.dialogs import show_popup
from gui.ai_grids import AIStagingGrid


class AIImportView(ctk.CTkFrame):
    def __init__(self, parent, manager, db_session):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.manager = manager
        self.db_session = db_session
        self.engine_setup_icon = get_icon("terminal2_white.png", size=(14, 14))
        self.edit_skip_icon = get_icon("block_white.png", size=(14, 14))
        self.edit_rules_icon = get_icon("settings_white.png", size=(14, 14))
        self.view_grid_icon = get_icon("grid_white.png", size=(15, 15))
        self.view_file_icon = get_icon("visibility_white.png", size=(15, 15))

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 10))

        self.ai_header = ctk.CTkLabel(header_row, text="AI Expense Parser",
                                      font=("JetBrains Mono", 22, "bold"))
        self.ai_header.pack(side="left", anchor="w")

        self.ai_config_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        self.ai_config_frame.pack(fill="x", pady=(0, 15), padx=2)

        row1 = ctk.CTkFrame(self.ai_config_frame, fg_color="transparent")
        row1.pack(fill="x", pady=(12, 6), padx=15)
        # File
        ctk.CTkLabel(row1, text="Target File:", font=("JetBrains Mono", 12, "bold")).pack(side="left")

        self.btn_format_guide = ctk.CTkButton(
            row1, text="?", width=24, height=24, corner_radius=12,
            fg_color="gray30", hover_color="gray40", font=("JetBrains Mono", 12, "bold"),
            command=self._show_format_guide
        )
        self.btn_format_guide.pack(side="left", padx=(5, 10))
        ToolTip(self.btn_format_guide, "Required file format guide")

        self.lbl_container = ctk.CTkFrame(row1, height=28, fg_color="gray20", corner_radius=4)
        self.lbl_container.pack_propagate(False)
        self.lbl_container.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.ai_full_filepath = ""
        self.ai_filepath_var = ctk.StringVar(self, value="No file selected...")
        self.ai_file_lbl = ctk.CTkLabel(self.lbl_container, textvariable=self.ai_filepath_var, text_color="gray60",
                                        anchor="w")
        self.ai_file_lbl.pack(fill="both", expand=True, padx=10)
        self.file_tooltip = ToolTip(self.ai_file_lbl, "Please select a text file.")

        self.btn_browse = ctk.CTkButton(row1, text="Browse", width=70, fg_color="gray30", hover_color="gray40",
                                        command=self._ai_browse_file)
        self.btn_browse.pack(side="left", padx=(0, 20))

        # AI Config Buttons
        self.btn_parser_guide = ctk.CTkButton(
            row1, text="?", width=24, height=24, corner_radius=12,
            fg_color="gray30", hover_color="gray40", font=("JetBrains Mono", 12, "bold"),
            command=self._show_parser_guide
        )
        self.btn_parser_guide.pack(side="right")
        ToolTip(self.btn_parser_guide, "How to customize the AI parser")

        self.btn_edit_rules = ctk.CTkButton(
            row1, text="Parser Rules", image=self.edit_rules_icon, width=110, height=24,
            font=("JetBrains Mono", 11), fg_color="gray25", hover_color="gray35",
            command=lambda: open_text_config("ai_prompt_template.txt", DEFAULT_PROMPT_TEMPLATE, allow_empty=False)
        )
        self.btn_edit_rules.pack(side="right", padx=(0, 5))
        ToolTip(self.btn_edit_rules, "Edit the LLM System Prompt and examples")

        self.btn_edit_skip = ctk.CTkButton(
            row1, text="Skip Terms", image=self.edit_skip_icon, width=110, height=24,
            font=("JetBrains Mono", 11), fg_color="gray25", hover_color="gray35",
            command=lambda: open_text_config("ai_skip_terms.txt", DEFAULT_SKIP_TERMS_TEXT, allow_empty=True)
        )
        self.btn_edit_skip.pack(side="right", padx=(0, 5))
        ToolTip(self.btn_edit_skip, "Edit terms the parser should ignore")

        self.btn_engine_setup = ctk.CTkButton(
            row1, text="Engine Setup", image=self.engine_setup_icon, width=110, height=24,
            font=("JetBrains Mono", 11), fg_color="gray25", hover_color="gray35",
            command=self._show_engine_guide
        )
        self.btn_engine_setup.pack(side="right", padx=(0, 5))
        ToolTip(self.btn_engine_setup, "Instructions for installing the local AI engine")

        row2 = ctk.CTkFrame(self.ai_config_frame, fg_color="transparent")
        row2.pack(fill="x", pady=(6, 12), padx=15)

        # Dropdowns
        active_currencies = [c.code for c in self.db_session.query(Currency).filter_by(active_bool=True).order_by(
            collate(Currency.name, 'NOCASE')).all()]
        active_projects = ["None"] + [p.name for p in
                                      self.db_session.query(Project).filter_by(active_bool=True).order_by(
                                          collate(Project.name, 'NOCASE')).all()]
        current_year = str(datetime.datetime.now().year)
        years = [str(y) for y in range(int(current_year) - 2, int(current_year) + 3)]

        ctk.CTkLabel(row2, text="Year:", font=("JetBrains Mono", 11, "bold")).pack(side="left")
        self.ai_year_combo = ctk.CTkComboBox(row2, values=years, width=80)
        self.ai_year_combo.set(current_year)
        self.ai_year_combo.pack(side="left", padx=(10, 25))
        ToolTip(self.ai_year_combo, "Select from dropdown or manually type any year.")

        ctk.CTkLabel(row2, text="Default Currency:", font=("JetBrains Mono", 11, "bold")).pack(side="left")
        self.ai_curr_combo = ctk.CTkComboBox(row2, values=active_currencies, state="readonly", width=120)
        if self.manager.base_currency in active_currencies: self.ai_curr_combo.set(self.manager.base_currency)
        self.ai_curr_combo.pack(side="left", padx=(10, 25))
        ToolTip(self.ai_curr_combo, "Select from dropdown.")

        ctk.CTkLabel(row2, text="Tag Project:", font=("JetBrains Mono", 11, "bold")).pack(side="left")
        self.ai_proj_combo = ctk.CTkComboBox(row2, values=active_projects, state="readonly", width=220)
        self.ai_proj_combo.set("None")
        self.ai_proj_combo.pack(side="left", padx=(10, 20))
        ToolTip(self.ai_proj_combo, "Select from dropdown.")

        # Action Buttons
        self.btn_start_ai = ctk.CTkButton(row2, text="⚡ Start Parsing", fg_color="#1f538d", width=120,
                                          font=("JetBrains Mono", 12, "bold"), command=self._start_ai_thread)

        self.btn_cancel_ai = ctk.CTkButton(row2, text="✕ Cancel", fg_color="#b13e3e", hover_color="#611a1a",
                                           width=120, font=("JetBrains Mono", 12, "bold"),
                                           command=self._cancel_ai_thread)

        self.btn_clear_ai = ctk.CTkButton(row2, text="↺ Clear Session", fg_color="gray40", hover_color="gray50",
                                          width=120, font=("JetBrains Mono", 12, "bold"), command=self._reset_ai_view)

        self.btn_start_ai.pack(side="right")

        self.progress_container = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.progress_container.pack_propagate(False)
        self.progress_container.pack(fill="x", pady=(0, 10))

        self.ai_status_lbl = ctk.CTkLabel(self.progress_container, text="", text_color="#5AC8FA",
                                          font=("JetBrains Mono", 12))
        self.ai_status_lbl.pack(pady=(0, 5))

        self.ai_progress_bar = ctk.CTkProgressBar(self.progress_container, mode="determinate", height=8,
                                                  fg_color="gray20",
                                                  progress_color="#1f538d")
        self.ai_progress_bar.set(0)

        self.ai_staging_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.ai_staging_frame.pack(fill="both", expand=True)

        self.staging_header = ctk.CTkFrame(self.ai_staging_frame, fg_color="transparent")

        self.staging_title = ctk.CTkLabel(self.staging_header, text="File Preview",
                                          font=("JetBrains Mono", 14, "bold"))
        self.staging_title.pack(side="left", padx=10)

        self.btn_import_all = ctk.CTkButton(self.staging_header, text="✅   Import All", fg_color="#4CD964",
                                            text_color="black", hover_color="#3cb051", width=120,
                                            font=("JetBrains Mono", 12, "bold"), state="disabled")

        self.btn_toggle_view = ctk.CTkButton(self.staging_header, text="View File", image=self.view_file_icon, fg_color="gray30",
                                             hover_color="gray40", width=120, font=("JetBrains Mono", 12, "bold"),
                                             command=self._toggle_ai_view)

        self.preview_container = ctk.CTkFrame(self.ai_staging_frame, fg_color="transparent")
        self.grid_container = ctk.CTkFrame(self.ai_staging_frame, fg_color="transparent")

        self.ai_cancel_event = threading.Event()

        self._thread_results = None
        self._thread_error = None

    def destroy(self):
        """Ensures the background AI thread gracefully aborts if the view is destroyed."""
        self.ai_cancel_event.set()
        super().destroy()

    def _show_format_guide(self):
        """Displays a guide for the required text file format."""
        msg = (
            "The parser expects a specific daily journal format:\n\n"
            "1. DATE HEADERS\n\n"
            "Each day MUST start with 'DD/MM:' or 'DD/MM (note):'\n\n"
            "2. TRANSACTION LINES\n\n"
            "Format: [Category] [Vendor] [Amount] [Currency?] [Method] [Description]\n\n"
            "EXAMPLES\n\n"
            "23/07:\n"
            "Groceries Supermarket 45.50 debit Weekend food\n"
            "Transport Train 12 cash\n\n"
            "24/07 (Trip to city):\n"
            "Dining PizzaHut 24.99 credit\n\n"
            "FOREIGN CURRENCY & CUSTOM RATES\n\n"
            "Add a currency code after the amount to auto-fetch historical rates.\n"
            "To force a custom rate, include 'FX [rate]' in the description:\n"
            "Housing Hotel 150 USD (FX 1.14 - including tax) credit"
        )

        show_popup(self, title="Required File Format", message=msg, show_ok=True, width=450, height=580, message_wraplength=400, is_copyable=True)

    def _show_parser_guide(self):
        """Displays a comprehensive guide on tailoring the LLM prompt."""
        msg = (
            "To get 100% parsing accuracy, you MUST tailor the AI to your specific Master Data setup.\n\n"
            "1. SKIP TERMS\n\n"
            "Add words here (like 'Transfer' or 'Withdrawal') that the parser should completely ignore. One term per line.\n\n"
            "2. PARSER RULES\n\n"
            "This opens the raw instructions sent to the AI model. "
            "You should update the <mapping_table> and <examples> to perfectly match the precise Category and Payment Method names you created in the Master Data tab.\n\n"
            "For example: If your database uses 'Amex Card' instead of 'Credit Card', change it in the mapping table so the AI outputs the exact match!"
        )

        show_popup(self, title="Customizing the AI", message=msg, show_ok=True, width=480, height=440, message_wraplength=430, is_copyable=True)

    def _show_engine_guide(self):
        """Displays platform-specific instructions for installing Ollama."""
        if sys.platform == "win32":
            msg = (
                "Venn Ledger uses Ollama to process data locally and privately.\n\n"
                "1. Download and install Ollama Desktop from ollama.com\n\n"
                "2. Open your Command Prompt and run:\n\n"
                "   ollama pull mistral:7b\n\n"
                "Once downloaded, Venn Ledger will automatically manage the engine in the background!"
            )
            popup_height = 300
            popup_width = 480
            wrap_len = 430

        elif IS_STEAMOS:
            msg = (
                "Venn Ledger uses Ollama to process data locally and privately.\n\n"
                "Because SteamOS is read-only, open Konsole and run these steps just once:\n\n"
                "1. mkdir -p ~/.local && curl -L https://ollama.com/download/ollama-linux-amd64.tar.zst | tar -x --zstd -C ~/.local\n\n"
                "2. In Tab 1 run: OLLAMA_IGPU_ENABLE=1 ~/.local/bin/ollama serve\n\n"
                "3. In Tab 2 run: ~/.local/bin/ollama pull mistral:7b\n\n"
                "Once downloaded, Venn Ledger will automatically manage the engine!"
            )
            popup_height = 380
            popup_width = 580
            wrap_len = 530

        else:
            # Standard Linux (Ubuntu, Mint, Fedora, Arch, etc.)
            msg = (
                "Venn Ledger uses Ollama to process data locally and privately.\n\n"
                "To set this up, open your Terminal and run:\n\n"
                "1. curl -fsSL https://ollama.com/install.sh | sh\n\n"
                "2. ollama pull mistral:7b\n\n"
                "Once downloaded, Venn Ledger will automatically manage the engine!"
            )
            popup_height = 350
            popup_width = 480
            wrap_len = 430

        show_popup(
            self,
            title="AI Engine Setup",
            message=msg,
            show_ok=True,
            width=popup_width,
            height=popup_height,
            message_wraplength=wrap_len,
            is_copyable=True
        )

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
        self.btn_cancel_ai.pack(side="right")
        self.btn_cancel_ai.configure(state="normal")
        self.ai_status_lbl.configure(text="Connecting to Mistral 7B... Please wait.", text_color="#5AC8FA")

        self.ai_progress_bar.pack(fill="x", padx=150)
        self.ai_progress_bar.configure(progress_color="#1f538d")
        self.ai_progress_bar.set(0)

        currency = self.ai_curr_combo.get()
        year = self.ai_year_combo.get()
        project = self.ai_proj_combo.get()
        cats = self.db_session.query(Category).all()

        thread = threading.Thread(target=self._run_ai_parser_backend,
                                  args=(self.ai_full_filepath, currency, year, project, cats))
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

    def _run_ai_parser_backend(self, filepath, currency, year, project, cats):
        """Runs in the background."""
        try:
            current_skip_terms = get_skip_terms()
            current_system_prompt = get_row_prompt(currency)

            # 1. Chunk the file
            daily_chunks = chunk_file_by_day(filepath, current_skip_terms)

            # 2. Combine chunks into a single string for parsing
            combined_str = ""
            for day in daily_chunks:
                combined_str += f"{day['header']}\n{day['data']}\n"

            # 3. Define the callback
            def progress_cb(c_line, t_lines, c_tx, t_tx):
                self.after(0, self._update_ai_progress, c_line, t_lines, c_tx, t_tx)

            # 4. Invoke LLM
            parsed_results = get_structured_data(combined_str, cats, system_prompt=current_system_prompt,
                                                 cancel_event=self.ai_cancel_event, progress_callback=progress_cb)

            # 5. Pass results back to the main GUI thread
            self._thread_results = (parsed_results, year, project)
            self.after(0, lambda: self._on_ai_parsing_complete())

        except Exception as e:
            self._thread_error = str(e)
            self.after(0, lambda: self._on_ai_parsing_failed())

    def _toggle_ai_view(self):
        """Flips visibility between the file preview and the staging grid."""
        if self.preview_container.winfo_ismapped():
            self.preview_container.pack_forget()
            self.grid_container.pack(fill="both", expand=True)
            self.btn_toggle_view.configure(text="View File", image=self.view_file_icon)
            self.staging_title.configure(text="Review & Fix")
        else:
            self.grid_container.pack_forget()
            self.preview_container.pack(fill="both", expand=True)
            self.btn_toggle_view.configure(text="View Grid", image=self.view_grid_icon)
            self.staging_title.configure(text="File Preview")

    def _reset_ai_view(self, success_msg=None, clear_text=True):
        """Wipes the staging grid & preview and restores the config panel to default."""
        if clear_text:
            self.ai_year_combo.configure(state="normal")
            self.ai_year_combo.set(str(datetime.datetime.now().year))
            self.ai_curr_combo.configure(state="normal")
            self.ai_curr_combo.set(self.manager.base_currency)
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
            self.btn_start_ai.pack(side="right")

            self.staging_header.pack_forget()

        else:
            self.btn_cancel_ai.pack_forget()
            self.btn_start_ai.pack_forget()
            self.btn_clear_ai.pack(side="right")
            self.btn_clear_ai.configure(state="normal")
            self.preview_container.pack(fill="both", expand=True)

            self.staging_title.configure(text="File Preview")
            self.btn_import_all.pack_forget()
            self.btn_toggle_view.pack_forget()

        self.ai_progress_bar.pack_forget()

        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self.grid_container.update_idletasks()

        self.btn_import_all.configure(text="✅   Import All", state="disabled", fg_color="#4CD964", text_color="black")

        self.grid_container.pack_forget()

        if success_msg:
            self.ai_status_lbl.configure(text=success_msg, text_color="#4CD964")
        else:
            self.ai_status_lbl.configure(text="Session cleared. Ready.", text_color="gray")

    def _on_ai_parsing_failed(self, error_msg=None):
        """Runs on main thread: Handles crashes during parsing."""
        if error_msg is None:
            error_msg = self._thread_error or "Unknown error occurred."

        self.ai_year_combo.configure(state="normal")
        self.ai_curr_combo.configure(state="normal")
        self.ai_proj_combo.configure(state="normal")
        self.btn_browse.configure(state="normal")

        self.btn_cancel_ai.pack_forget()
        self.btn_start_ai.pack(side="right")
        self.btn_start_ai.configure(state="normal")

        if "Cannot connect to Ollama" in error_msg:
            error_msg += " Click 'Engine Setup' for instructions."

        color = "orange" if "cancelled" in error_msg.lower() else "#FF6B6B"
        self.ai_status_lbl.configure(text=f"Stopped: {error_msg}", text_color=color)

        self.ai_progress_bar.pack_forget()

    def _on_ai_parsing_complete(self):
        """Runs on main thread: Receives data and build the staging grid."""
        parsed_results, year, project = self._thread_results

        self.btn_cancel_ai.pack_forget()
        self.btn_clear_ai.pack(side="right")

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
        self.btn_toggle_view.configure(text="View File", image=self.view_file_icon)

        self.preview_container.pack_forget()
        self.grid_container.pack(fill="both", expand=True)

        for widget in self.grid_container.winfo_children():
            widget.destroy()

        self.grid_container.update_idletasks()
        self.preview_container.update_idletasks()

        grid = AIStagingGrid(self.grid_container, parsed_results, year, project, self, self.btn_import_all, self.db_session)
        grid.pack(fill="both", expand=True)

        self.btn_import_all.configure(command=grid.execute_import)

        # print("--- THREAD COMPLETE. DATA RECEIVED IN GUI ---")
        # for res in parsed_results:
        #     print(res)

    def refresh_view(self):
        """Called when this tab is brought to the front.
        Ensures the dropdowns have the latest Master Data."""

        active_currencies = [c.code for c in self.db_session.query(Currency).filter_by(active_bool=True).order_by(collate(Currency.name, 'NOCASE')).all()]
        active_projects = ["None"] + [p.name for p in self.db_session.query(Project).filter_by(active_bool=True).order_by(collate(Project.name, 'NOCASE')).all()]

        self.ai_curr_combo.configure(values=active_currencies)
        self.ai_proj_combo.configure(values=active_projects)

        if self.ai_curr_combo.get() not in active_currencies and active_currencies:
            self.ai_curr_combo.set(self.manager.base_currency if self.manager.base_currency in active_currencies else active_currencies[0])

        if self.ai_proj_combo.get() not in active_projects:
            self.ai_proj_combo.set("None")