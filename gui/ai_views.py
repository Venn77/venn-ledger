import customtkinter as ctk
import datetime, gc
from database.models import (
    Category, Vendor, Currency, PaymentMethod
)
from utils.currency_utils import extract_exchange_rate
from gui.widgets import ToolTip, SearchableComboBox


class AIStagingRow(ctk.CTkFrame):
    """Represents one parsed transaction in a single row, with real-time validation."""
    def __init__(self, parent, data, active_cats, active_pms, active_vendors, active_currencies, app_ref, year, grid_ref, db_session=None):
        super().__init__(parent, fg_color="gray20", corner_radius=6)
        self.data = data
        self.app = app_ref
        self.year = year
        self.grid_ref = grid_ref
        self.db_session = db_session

        self.cat_names = [c.name for c in active_cats]
        self.pm_names = [p.name for p in active_pms]
        self.ven_names = [v.name for v in active_vendors]
        self.curr_names = [c.code for c in active_currencies]

        self.pm_dict = {p.name: p.account.currency_code for p in active_pms}

        # Expand Vendor & Description
        self.grid_columnconfigure(2, weight=1)
        self.grid_columnconfigure(8, weight=2)

        # 0. Status Indicator
        self.status_lbl = ctk.CTkLabel(self, text="⚫", width=30, font=("Segoe UI", 14))
        self.status_lbl.grid(row=0, column=0, padx=5, pady=5)
        self.status_tooltip = ToolTip(self.status_lbl, "Initializing...")

        # 1. Date
        ctk.CTkLabel(self, text=data['date'], width=45, font=("JetBrains Mono", 11, "bold")).grid(row=0, column=1,
                                                                                                  padx=5, sticky="w")

        # 2. Vendor
        self.ven_var = ctk.StringVar(value=data['vendor'])
        self.ven_entry = ctk.CTkEntry(self, textvariable=self.ven_var, height=24)
        self.ven_entry.grid(row=0, column=2, padx=5, sticky="ew")

        # 3. Amount
        self.amt_var = ctk.StringVar(value=str(data['amount']))
        self.amt_entry = ctk.CTkEntry(self, textvariable=self.amt_var, width=70, height=24)
        self.amt_entry.grid(row=0, column=3, padx=5)

        # 4. Currency
        self.currency_combo = ctk.CTkComboBox(self, values=self.curr_names, width=70, height=24, state="readonly",
                                          command=self._on_currency_change)
        self.currency_combo.set(data['currency'] if data['currency'] in self.curr_names else "EUR")
        self.currency_combo.grid(row=0, column=4, padx=5)

        # 4. FX Rate
        self.fx_var = ctk.StringVar()
        self.fx_entry = ctk.CTkEntry(self, textvariable=self.fx_var, width=60, height=24, placeholder_text="FX")
        self.fx_entry.grid(row=0, column=5, padx=5)
        self.fx_tooltip = ToolTip(self.fx_entry, "")

        self._calculate_fx(self.currency_combo.get(), initial_load=True)

        # 5. Category (Combo)
        self.cat_combo = SearchableComboBox(self, placeholder="Category...", values=self.cat_names, width=110, height=24,
                                         command=lambda _: self.validate())
        self.cat_combo.inject_value(data['category'])
        self.cat_combo.grid(row=0, column=6, padx=5, sticky="ew")

        self.cat_combo.configure(command=lambda _: self.validate())
        # noinspection PyProtectedMember
        self.cat_combo._entry.bind("<KeyRelease>", lambda e: self.validate(), add="+")

        # 6. Payment Method (Combo)
        valid_pms = [name for name, c_code in self.pm_dict.items() if c_code == self.currency_combo.get()]
        self.pm_combo = ctk.CTkComboBox(self, values=valid_pms if valid_pms else ["None"], width=130, height=24,
                                        state="readonly", command=lambda _: self.validate())

        if data['payment_method'] in valid_pms:
            self.pm_combo.set(data['payment_method'])
        else:
            self.pm_combo.set("--- Select ---")
        self.pm_combo.grid(row=0, column=7, padx=5, sticky="ew")

        # 7. Description (Editable)
        self.desc_var = ctk.StringVar(value=data['description'])
        self.desc_entry = ctk.CTkEntry(self, textvariable=self.desc_var, height=24)
        self.desc_entry.grid(row=0, column=8, padx=5, sticky="ew")

        # 8. Discard Button
        self.btn_discard = ctk.CTkButton(self, text="✕", width=30, height=24, fg_color="transparent",
                                         text_color="gray50", hover_color="#b13e3e", command=self.discard_row)
        self.btn_discard.grid(row=0, column=9, padx=(5, 10))

        def on_x_hover(event):
            # Red
            self.configure(fg_color="#332424")

        def on_x_leave(event):
            self.configure(fg_color="gray20")

        # Binds
        self.btn_discard.bind("<Enter>", on_x_hover, add="+")
        self.btn_discard.bind("<Leave>", on_x_leave, add="+")
        self.ven_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.amt_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.desc_entry.bind("<KeyRelease>", lambda e: self.validate())
        self.fx_entry.bind("<KeyRelease>", self._on_fx_manual_edit)

        self.is_valid = False
        self.status_type = ""
        self.validate()

    def _set_fx_tooltip(self, text):
        """Sets the FX rate tooltip."""
        self.fx_tooltip.text = text

    def _on_fx_manual_edit(self, event):
        """Flags the FX source as Manual if the user types in it."""
        self._set_fx_tooltip("Source: Manual Entry")
        self.validate()

    def _calculate_fx(self, curr_code, initial_load=False):
        """Determines the FX rate and sets the appropriate Tooltip."""
        self.fx_var.set("")

        if curr_code == "EUR":
            self.fx_entry.configure(state="normal", fg_color="gray15", text_color="gray50", font=("JetBrains Mono", 11))
            self.fx_var.set("EUR Base")
            self.fx_entry.configure(state="disabled")
            self._set_fx_tooltip("EUR is the Base Currency")
            return

        self.fx_entry.configure(state="normal", fg_color=["#F9F9FA", "#343638"], text_color="white", font=("JetBrains Mono", 12))

        if initial_load:
            if 'fx_rate' in self.data:
                saved_val = str(self.data['fx_rate'])
                self.fx_var.set(saved_val)
                if saved_val.strip() == "":
                    self._set_fx_tooltip("Source: Manual Entry Required")
                else:
                    self._set_fx_tooltip("Source: Saved Entry")
                return

            extracted_fx = extract_exchange_rate(self.data['description'])
            if extracted_fx:
                self.fx_var.set(str(extracted_fx))
                self._set_fx_tooltip("Source: Extracted from Description")
                return

        day_str, month_str = self.data['date'].split('/')
        target_dt = datetime.datetime(int(self.year), int(month_str), int(day_str), 12, 0, 0, 0)
        fx_data = self.app.manager.get_historical_fx_rate(curr_code, target_dt)

        if fx_data:
            db_fx, db_ts = fx_data
            self.fx_var.set(str(db_fx))
            self._set_fx_tooltip(f"Source: Historical DB\nLogged: {db_ts.strftime('%Y-%m-%d')}")
        else:
            self._set_fx_tooltip("Source: Manual Entry Required")

    def _on_currency_change(self, new_curr):
        self.data['currency'] = new_curr

        valid_pms = [name for name, c_code in self.pm_dict.items() if c_code == new_curr]
        self.pm_combo.configure(values=valid_pms if valid_pms else ["None"])

        if self.pm_combo.get() not in valid_pms:
            self.pm_combo.set("--- Select ---")

        self._calculate_fx(new_curr, initial_load=False)
        self.validate()

    def discard_row(self):
        """Marks the item as discarded in memory and marks it discarded in memory."""
        self.data['discarded'] = True

        self.btn_discard.unbind("<Enter>")
        self.btn_discard.unbind("<Leave>")

        self.destroy()
        if hasattr(self.grid_ref, 'update_pagination_state'):
            self.app.after(10, self.grid_ref.update_pagination_state)

    def validate(self):
        """Checks DB integrity and updates the status light, and syncs back to master memory."""
        warnings = []
        errors = []

        self.data['description'] = self.desc_var.get().strip()

        # Check Amount
        raw_amt = self.amt_var.get().strip()
        self.data['amount'] = raw_amt
        try:
            float(raw_amt)
        except ValueError:
            errors.append("Invalid Amount.")

        # Check FX
        if self.currency_combo.get() != "EUR":
            raw_fx = self.fx_var.get().strip()
            self.data['fx_rate'] = raw_fx
            try:
                rate = float(raw_fx)
                if rate <= 0: raise ValueError
            except ValueError:
                errors.append("Missing/Invalid FX Rate.")

        # Check Vendor
        ven_val = self.ven_var.get().strip()
        self.data['vendor'] = ven_val
        if not ven_val:
            warnings.append("Will be imported with no Vendor.")
        elif ven_val not in self.ven_names:
            warnings.append("New Vendor will be created.")

        # Check Category
        cat_val = self.cat_combo.get().strip()
        if hasattr(self.cat_combo, 'placeholder') and cat_val == self.cat_combo.placeholder:
            cat_val = ""
        self.data['category'] = cat_val

        if not cat_val:
            warnings.append("Will be imported with no Category.")
        elif cat_val not in self.cat_names:
            warnings.append("New Category will be created.")

        # Check Payment Method & Currency Link
        pm_val = self.pm_combo.get()
        self.data['payment_method'] = pm_val
        valid_pms = [name for name, c_code in self.pm_dict.items() if c_code == self.currency_combo.get()]

        if pm_val not in valid_pms:
            errors.append("Select a matching Payment Method.")

        raw_line = f"\n\nRaw Line: {self.data.get('line', '')}"

        # Apply Colors
        if errors:
            self.status_lbl.configure(text="🔴", text_color="#FF6B6B")
            self.is_valid = False
            self.data['is_valid'] = False
            self.data['status_type'] = "red"
            self.status_tooltip.text = " | ".join(errors) + raw_line
        elif warnings:
            self.status_lbl.configure(text="🟡", text_color="#FFD60A")
            self.is_valid = True
            self.data['is_valid'] = True
            self.data['status_type'] = "yellow"
            self.status_tooltip.text = " | ".join(warnings) + raw_line
        else:
            self.status_lbl.configure(text="🟢", text_color="#4CD964")
            self.is_valid = True
            self.data['is_valid'] = True
            self.data['status_type'] = "green"
            self.status_tooltip.text = "Ready to import." + raw_line

        if hasattr(self.grid_ref, 'check_master_validation'):
            self.grid_ref.check_master_validation()

class AIStagingGrid(ctk.CTkFrame):
    """Holds all parsed rows and manages pagination and final DB commit."""
    def __init__(self, parent, parsed_results, year, project, app_ref, import_btn, db_session=None):
        super().__init__(parent, fg_color="transparent")
        self.app = app_ref
        self.year = year
        self.project = project
        self.import_btn = import_btn
        self.db_session = db_session

        self.parsed_results = parsed_results

        self.current_page = 0
        self.page_size = 25
        self.rows = []

        self.active_cats = self.db_session.query(Category).filter_by(active_bool=True).order_by(Category.name.asc()).all()
        self.active_pms = self.db_session.query(PaymentMethod).filter_by(active_bool=True).order_by(PaymentMethod.name.asc()).all()
        self.active_vendors = self.db_session.query(Vendor).filter_by(active_bool=True).order_by(Vendor.name.asc()).all()
        self.active_currencies = self.db_session.query(Currency).filter_by(active_bool=True).order_by(Currency.name.asc()).all()

        self._pre_validate_all()

        self.render_timer = None

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)

        self.nav_bar = ctk.CTkFrame(self, fg_color="transparent", height=40)
        self.nav_bar.pack(fill="x", pady=(5, 10))

        self.nav_bar.grid_columnconfigure((0, 2), weight=1)
        self.nav_bar.grid_columnconfigure(1, weight=0)

        left_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        left_group.grid(row=0, column=0, sticky="e", padx=20)
        self.btn_prev = ctk.CTkButton(left_group, text="‹ Prev", width=70, fg_color="gray30", command=self.prev_page)
        self.btn_prev.pack(side="left", padx=2)

        center_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        center_group.grid(row=0, column=1, sticky="n")
        self.lbl_page_info = ctk.CTkLabel(center_group, text="Page 1 of 1", font=("JetBrains Mono", 12))
        self.lbl_page_info.pack(side="left", padx=5)

        right_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        right_group.grid(row=0, column=2, sticky="w", padx=20)
        self.btn_next = ctk.CTkButton(right_group, text="Next ›", width=70, fg_color="gray30", command=self.next_page)
        self.btn_next.pack(side="left", padx=2)

        self.render_page()

    def _pre_validate_all(self):
        """Runs headless validation on all items before the UI renders them."""
        pm_dict = {p.name: p.account.currency_code for p in self.active_pms}
        cat_names = [c.name for c in self.active_cats]
        ven_names = [v.name for v in self.active_vendors]

        for data in self.parsed_results:
            errors, warnings = False, False

            try:
                float(data.get('amount', 0))
            except ValueError:
                errors = True

            curr = data.get('currency', 'EUR')
            valid_pms = [n for n, c in pm_dict.items() if c == curr]
            if data.get('payment_method') not in valid_pms: errors = True

            if data.get('category') not in cat_names: warnings = True
            if data.get('vendor') not in ven_names: warnings = True

            if curr != "EUR":
                fx = extract_exchange_rate(data.get('description', ''))
                if not fx:
                    try:
                        day_str, month_str = data['date'].split('/')
                        target_dt = datetime.datetime(int(self.year), int(month_str), int(day_str), 12, 0, 0, 0)
                        fx_data = self.app.manager.get_historical_fx_rate(curr, target_dt)
                        if not fx_data: errors = True
                    except Exception:
                        errors = True

            if errors:
                data['is_valid'] = False
                data['status_type'] = "red"
            elif warnings:
                data['is_valid'] = True
                data['status_type'] = "yellow"
            else:
                data['is_valid'] = True
                data['status_type'] = "green"

    def _schedule_render(self):
        """Debouncer: Cancels the previous timer and sets a new one to draw the page."""
        if self.render_timer:
            self.after_cancel(self.render_timer)
        self.render_timer = self.after(300, self.render_page)

    def update_pagination_state(self):
        """Updates counters, button states, and import validation based on memory."""
        active_items = [res for res in self.parsed_results if not res.get('discarded')]
        total_active = len(active_items)
        total_pages = max(1, (total_active + self.page_size - 1) // self.page_size)

        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)
            self._schedule_render()
            return

        visible_rows = sum(1 for row in self.rows if row.winfo_exists())
        expected_visible = min(self.page_size, total_active - (self.current_page * self.page_size))
        is_last_page = (self.current_page == total_pages - 1)

        if (visible_rows == 0 and total_active > 0) or (is_last_page and visible_rows < expected_visible):
            self._schedule_render()
            return

        self.lbl_page_info.configure(text=f"Page {self.current_page + 1} of {total_pages} ({total_active} total items)")
        self.btn_prev.configure(state="normal" if self.current_page > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

        self.check_master_validation()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_pagination_state()
            self._schedule_render()

    def next_page(self):
        active_items = [res for res in self.parsed_results if not res.get('discarded')]
        max_page = max(0, (len(active_items) - 1) // self.page_size)
        if self.current_page < max_page:
            self.current_page += 1
            self.update_pagination_state()
            self._schedule_render()

    def render_page(self):
        """Destroys old widgets, forces GC, and draws the current slice."""
        for row in self.rows:
            if row.winfo_exists():
                row.destroy()
        self.rows.clear()

        gc.collect()

        active_items = [res for res in self.parsed_results if not res.get('discarded')]

        total_pages = max(1, (len(active_items) + self.page_size - 1) // self.page_size)

        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)

        self.lbl_page_info.configure(
            text=f"Page {self.current_page + 1} of {total_pages} ({len(active_items)} total items)")
        self.btn_prev.configure(state="normal" if self.current_page > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")

        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size
        page_data = active_items[start_idx:end_idx]

        for res in page_data:
            row = AIStagingRow(self.scroll, res, self.active_cats, self.active_pms, self.active_vendors,
                               self.active_currencies, self.app, self.year, grid_ref=self, db_session=self.db_session)
            row.pack(fill="x", pady=2, padx=5)
            self.rows.append(row)

        if hasattr(self.scroll, "_parent_canvas"):
            # noinspection PyProtectedMember
            self.scroll._parent_canvas.yview_moveto(0)

        self.update_pagination_state()

    def check_master_validation(self):
        """Enables the Import button ONLY if every active item in memory is valid."""
        active_items = [res for res in self.parsed_results if not res.get('discarded')]

        if not active_items:
            self.import_btn.configure(state="disabled", fg_color="gray30", text_color="white")
            return

        all_valid = all(res.get('is_valid', False) for res in active_items)
        has_warnings = any(res.get('status_type') == "yellow" for res in active_items)

        if all_valid:
            self.import_btn.configure(state="normal", text_color="black")
            if has_warnings:
                # Yellow Warning State
                self.import_btn.configure(fg_color="#FFD60A", hover_color="#e5c00b")
            else:
                # Green State
                self.import_btn.configure(fg_color="#4CD964", hover_color="#3cb051")
        else:
            self.import_btn.configure(state="disabled", fg_color="gray30", text_color="white")

    def execute_import(self):
        """Commits all rows from master memory to the database."""
        self.import_btn.configure(state="disabled", text="Importing...")
        self.app.update_idletasks()

        active_items = [res for res in self.parsed_results if not res.get('discarded')]
        success_count = 0

        for res in active_items:
            day, month = map(int, res['date'].split('/'))
            dt = datetime.datetime(int(self.year), month, day, 12, 0, 0, 0)

            fx_rate = res.get('fx_rate', None)

            try:
                self.app.manager.add_expense(
                    amount=res['amount'],
                    currency_code=res['currency'],
                    payment_method_name=res['payment_method'],
                    exchange_rate=fx_rate,
                    category_name=res['category'],
                    vendor_name=res['vendor'],
                    project_name=self.project if self.project != "None" else None,
                    description=res['description'],
                    timestamp=dt
                )
                success_count += 1
            except Exception as e:
                print(f"Failed to save {res['vendor']}: {e}")

        self.parsed_results.clear()
        self.destroy()
        gc.collect()
        if success_count == 1:
            msg_transaction = "transaction"
        else:
            msg_transaction = "transactions"
        # noinspection PyProtectedMember
        self.app._reset_ai_view(success_msg=f"Successfully imported {success_count} {msg_transaction} to database!", clear_text=False)
        self.app.refresh_accounts()