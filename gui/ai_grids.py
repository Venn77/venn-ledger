import customtkinter as ctk
import datetime
from sqlalchemy import collate
from database.models import (
    Category, Vendor, Currency, PaymentMethod
)
from utils.io_utils import validate_parsed_record
from utils.ctk_utils import patch_linux_scrolling
from gui.widgets import AIStagingRow


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

        self.active_cats = self.db_session.query(Category).filter_by(active_bool=True).order_by(collate(Category.name, 'NOCASE')).all()
        self.active_pms = self.db_session.query(PaymentMethod).filter_by(active_bool=True).order_by(collate(PaymentMethod.name, 'NOCASE')).all()
        self.active_vendors = self.db_session.query(Vendor).filter_by(active_bool=True).order_by(collate(Vendor.name, 'NOCASE')).all()
        self.active_currencies = self.db_session.query(Currency).filter_by(active_bool=True).order_by(collate(Currency.name, 'NOCASE')).all()

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

    def destroy(self):
        """Safely cleans up pending renders before destroying the grid."""
        if self.render_timer is not None:
            self.after_cancel(self.render_timer)
            self.render_timer = None
        super().destroy()

    def _pre_validate_all(self):
        """Runs headless validation on all items before the UI renders them."""
        pm_map = {p.name: p.account.currency_code for p in self.active_pms}
        cats = [c.name for c in self.active_cats]
        vens = [v.name for v in self.active_vendors]

        for data in self.parsed_results:
            validate_parsed_record(data, self.app.manager, self.year, pm_map, cats, vens)

    def _schedule_render(self):
        """Debouncer: Cancels the previous timer and sets a new one to draw the page."""
        if self.render_timer is not None:
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
                               self.active_currencies, self.app, self.year, grid_ref=self)
            row.pack(fill="x", pady=2, padx=5)
            self.rows.append(row)

        if hasattr(self.scroll, "_parent_canvas"):
            # noinspection PyProtectedMember
            self.after(50, lambda: self.scroll._parent_canvas.yview_moveto(0))

        self.update_pagination_state()

        patch_linux_scrolling(self.scroll)

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
        main_app = self.app.app
        main_app.update_idletasks()

        active_items = [res for res in self.parsed_results if not res.get('discarded')]
        success_count = 0

        for res in active_items:
            day, month = map(int, res['date'].split('/'))
            dt = datetime.datetime(int(self.year), month, day, 12, 0, 0, 0)

            raw_fx = res.get('fx_rate')
            try:
                fx_rate = float(raw_fx) if raw_fx else None
            except ValueError:
                fx_rate = None

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
        if success_count == 1:
            msg_transaction = "transaction"
        else:
            msg_transaction = "transactions"
        # noinspection PyProtectedMember
        self.app._reset_ai_view(success_msg=f"Successfully imported {success_count} {msg_transaction} to database!", clear_text=False)
        main_app.refresh_accounts()