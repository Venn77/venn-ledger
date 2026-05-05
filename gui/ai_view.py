import customtkinter as ctk
import threading, datetime
from database.models import (
    Category, Currency, Project
)
from core.ai_parser import chunk_file_by_day, get_structured_data
from customtkinter import filedialog
from gui.widgets import ToolTip
from gui.ai_grids import AIStagingGrid


class AIImportView(ctk.CTkFrame):
    def __init__(self, parent, manager, db_session):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.manager = manager
        self.db_session = db_session

        self.ai_header = ctk.CTkLabel(self, text="AI Transaction Parser",
                                      font=("JetBrains Mono", 22, "bold"))
        self.ai_header.pack(anchor="w", pady=(0, 10))

        self.ai_config_frame = ctk.CTkFrame(self, fg_color="gray15", corner_radius=8)
        self.ai_config_frame.pack(fill="x", pady=(0, 15), padx=2)

        cmd_bar = ctk.CTkFrame(self.ai_config_frame, fg_color="transparent")
        cmd_bar.pack(fill="x", pady=12, padx=15)

        # File Selection
        ctk.CTkLabel(cmd_bar, text="Target File:", font=("JetBrains Mono", 12, "bold"), anchor="w").pack(
            side="left")
        self.lbl_container = ctk.CTkFrame(cmd_bar, width=300, height=28, fg_color="gray20", corner_radius=4)
        self.lbl_container.pack_propagate(False)
        self.lbl_container.pack(side="left", padx=(10, 0))

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
        active_currencies = [c.code for c in self.db_session.query(Currency).filter_by(active_bool=True).all()]
        active_projects = ["None"] + [p.name for p in
                                      self.db_session.query(Project).filter_by(active_bool=True).all()]
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
                                          width=120, font=("JetBrains Mono", 12, "bold"),
                                          command=self._reset_ai_view)

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

            # 3. Get categories
            cats = self.db_session.query(Category).all()

            # 4. Define the callback
            def progress_cb(c_line, t_lines, c_tx, t_tx):
                self.after(0, self._update_ai_progress, c_line, t_lines, c_tx, t_tx)

            # 5. Invoke LLM
            parsed_results = get_structured_data(combined_str, currency, cats, cancel_event=self.ai_cancel_event,
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

        grid = AIStagingGrid(self.grid_container, parsed_results, year, project, self, self.btn_import_all, self.db_session)
        grid.pack(fill="both", expand=True)

        self.btn_import_all.configure(command=grid.execute_import)

        print("--- THREAD COMPLETE. DATA RECEIVED IN GUI ---")
        for res in parsed_results:
            print(res)