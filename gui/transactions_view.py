import customtkinter as ctk
import datetime
from database.models import (
    Account, Expense, Gain, Category,
    PaymentMethod, Vendor, Project,
    Transfer, Payer, Stream, Currency
)
from sqlalchemy import (
    desc, or_, func, column, literal_column,
    union_all, asc, case, collate
)
from sqlalchemy.orm import aliased
from gui.widgets import ToolTip, MonthYearSelector
from gui.transaction_grids import TransactionGrid
from gui.dialogs import open_calendar


class TransactionsView(ctk.CTkFrame):
    def __init__(self, parent, manager, db_session):
        super().__init__(parent, fg_color="transparent")
        self.app = parent
        self.manager = manager
        self.db_session = db_session

        self.current_view_date = datetime.datetime.now().replace(day=1)
        self.show_expenses_var = ctk.BooleanVar(value=True)
        self.show_gains_var = ctk.BooleanVar(value=True)
        self.show_transfers_var = ctk.BooleanVar(value=True)

        # Variables for Date Filtering
        self.active_date_filter = "This Month"
        self.active_custom_start = ""
        self.active_custom_end = ""

        # 3. Main Content Area (Transactions)
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
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
        self.date_filter_var = ctk.StringVar(self, value="This Month")

        self.filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.filter_bar.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(self.filter_bar, text="Date Range:", font=("JetBrains Mono", 12, "bold")).pack(side="left", padx=(0, 10))

        self.date_menu = ctk.CTkOptionMenu(
            self.filter_bar,
            values=["All Time", "Today", "Last 7 Days", "This Month", "Last Month", "This Year", "Custom..."],
            variable=self.date_filter_var,
            command=self.on_date_filter_change,
            width=130,
            dynamic_resizing=False
        )
        self.date_menu.pack(side="left")

        self.time_nav = MonthYearSelector(
            self.filter_bar,
            initial_date=self.current_view_date,
            command=self._on_time_nav_change
        )

        self.start_date_var = ctk.StringVar(self, value=(datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"))
        self.end_date_var = ctk.StringVar(self, value=datetime.datetime.now().strftime("%Y-%m-%d"))

        self.custom_date_frame = ctk.CTkFrame(self.filter_bar, fg_color="transparent")

        ctk.CTkLabel(self.custom_date_frame, text="From:").pack(side="left", padx=(5, 2))
        self.start_entry = ctk.CTkEntry(self.custom_date_frame, textvariable=self.start_date_var, width=85)
        self.start_entry.pack(side="left")

        self.start_cal_btn = ctk.CTkButton(
            self.custom_date_frame, text="", width=28, image=self.app.calendar_icon,
            command=lambda: open_calendar(self, self.start_date_var, include_time=False)
        )
        self.start_cal_btn.pack(side="left", padx=(2, 5))

        ctk.CTkLabel(self.custom_date_frame, text="To:").pack(side="left", padx=(5, 2))
        self.end_entry = ctk.CTkEntry(self.custom_date_frame, textvariable=self.end_date_var, width=85)
        self.end_entry.pack(side="left")

        self.end_cal_btn = ctk.CTkButton(
            self.custom_date_frame, text="", width=28, image=self.app.calendar_icon,
            command=lambda: open_calendar(self, self.end_date_var, include_time=False)
        )
        self.end_cal_btn.pack(side="left", padx=(2, 5))

        self.apply_date_btn = ctk.CTkButton(self.custom_date_frame, text="Apply", width=50, command=self.apply_custom_dates)
        self.apply_date_btn.pack(side="left", padx=2)

        self.type_filter_frame = ctk.CTkFrame(self.filter_bar, fg_color="transparent")
        self.type_filter_frame.pack(side="right", padx=(10, 0))

        self.project_filter_frame = ctk.CTkFrame(self.filter_bar, fg_color="transparent")
        self.project_filter_frame.pack(side="right", padx=(10, 0))

        self.project_filter_var = ctk.StringVar(self, value="All Projects")
        projects = ["All Projects", "No Project"] + [p.name for p in
                                       self.db_session.query(Project)
                                       .order_by(collate(Project.name, 'NOCASE'))
                                       .all()]
        self.project_menu = ctk.CTkOptionMenu(
            self.project_filter_frame,
            values=projects,
            variable=self.project_filter_var,
            command=self._on_project_filter_change,
            width=170,
            dynamic_resizing=False
        )
        self.project_menu.pack(side="left")

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
        self.grid_component = TransactionGrid(self, self.app)
        self.grid_component.pack(fill="both", expand=True)

        # 6. Navigation Bar
        self.nav_bar = ctk.CTkFrame(self, fg_color="transparent", height=50)
        self.nav_bar.pack(fill="x", pady=5)

        self.totals_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.totals_frame.pack(pady=(0, 10), padx=20, anchor="e")

        self.in_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("JetBrains Mono", 12, "bold"), text_color="#4CD964", anchor="e")
        self.in_lbl.pack(fill="x")

        self.out_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("JetBrains Mono", 12, "bold"), text_color="#b13e3e", anchor="e")
        self.out_lbl.pack(fill="x")

        self.balance_lbl = ctk.CTkLabel(self.totals_frame, text="", font=("JetBrains Mono", 13, "bold"), anchor="e")
        self.balance_lbl.pack(fill="x")

        ToolTip(self.search_entry,self.search_placeholder)

        self.current_page = 0
        self.page_size = 25
        self.total_pages = 0
        self.jump_entry = None
        self.search_timer = None
        self.current_search_text = ""
        self.nav_timer = None
        self.type_timer = None
        self.page_timer = None
        self.unlock_timer = None
        self._is_loading = False
        self._nav_built = False
        self.btn_first = None
        self.btn_prev = None
        self.btn_next = None
        self.btn_last = None
        self.lbl_page = None
        self.curr_data = self.db_session.query(Currency.code, Currency.decimals).all()
        self.dec_map = {code: decimals for code, decimals in self.curr_data}

        self.on_date_filter_change("This Month")

        self.chk_expenses = ctk.CTkCheckBox(self.type_filter_frame, text="Expenses", variable=self.show_expenses_var,
                                       font=("JetBrains Mono", 11), width=60, command=self._schedule_type_filter)
        self.chk_expenses.pack(side="left", padx=5)

        self.chk_gains = ctk.CTkCheckBox(self.type_filter_frame, text="Gains", variable=self.show_gains_var,
                                        font=("JetBrains Mono", 11), width=60, command=self._schedule_type_filter)
        self.chk_gains.pack(side="left", padx=5)

        self.chk_transfers = ctk.CTkCheckBox(self.type_filter_frame, text="Transfers", variable=self.show_transfers_var,
                                       font=("JetBrains Mono", 11), width=60, command=self._schedule_type_filter)
        self.chk_transfers.pack(side="left", padx=5)

    def apply_custom_dates(self):
        """Locks in the typed dates so filters don't trigger prematurely."""
        self.active_date_filter = "Custom..."
        self.active_custom_start = self.start_date_var.get()
        self.active_custom_end = self.end_date_var.get()
        self.current_page = 0
        self.load_transactions()
        self.reset_scroll_to_top()

    def load_transactions(self):
        """Fetches a page of transactions and renders them as rows."""
        self.render_pagination_controls(disable_all=True)
        self.update_idletasks()

        query = self.get_unified_transaction_query(self.db_session)

        selection = getattr(self, 'active_date_filter', "This Month")

        if selection == "Custom...":
            try:
                start = datetime.datetime.strptime(self.active_custom_start, "%Y-%m-%d").replace(hour=0, minute=0)
                end = datetime.datetime.strptime(self.active_custom_end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                query = query.filter(column("ts").between(start, end))
            except ValueError:
                pass
        else:
            start_limit, end_limit = self.get_date_limit(selection)

            if start_limit and end_limit:
                query = query.filter(column("ts").between(start_limit, end_limit))
            elif selection == "All Time":
                pass

        if self.app.filter_account_id:
            query = query.filter(column("acc_id") == self.app.filter_account_id)

        selected_proj = self.project_filter_var.get()
        if selected_proj == "No Project":
            query = query.filter(
                or_(
                    column("proj_name").is_(None),
                    column("proj_name") == ""
                )
            )
        elif selected_proj != "All Projects":
            query = query.filter(column("proj_name") == selected_proj)

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

        self.grid_component.render_rows(results, self.dec_map)

        # Back to Top Button
        if self.total_pages > 1:
            ctk.CTkButton(self.grid_component, text="▲ Back to Top", width=120, height=24,
                          fg_color="transparent", text_color="gray60", hover_color="gray25",
                          command=lambda: self.after(20, self.reset_scroll_to_top)
                          ).pack(pady=(0, 20))

        self.update_pagination_ui(total_count, query)

    @staticmethod
    def calculate_totals(base_query, current_session):
        """
        Calculates In, Out, and Balance.
        Ignores Transfers.
        """
        sub = base_query.subquery()

        totals_base = current_session.query(
            func.sum(case((sub.c.type == 'gain', sub.c.base_val), else_=0)).label("in_base"),
            func.sum(case((sub.c.type == 'expense', sub.c.base_val), else_=0)).label("out_base")
        ).one()

        in_base = totals_base[0] or 0
        out_base = totals_base[1] or 0
        net_balance = in_base - out_base

        raw_breakdown = (current_session.query(
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

        return (in_base, in_dict), (out_base, out_dict), net_balance

    @staticmethod
    def get_unified_transaction_query(current_session):
        # 1. EXPENSES
        q1 = current_session.query(
            Expense.id.label("id"),
            Expense.timestamp.label("ts"),
            Expense.amount.label("amount"),
            Expense.currency_code.label("currency"),
            Expense.converted_amount.label("base_val"),
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
            Gain.converted_amount.label("base_val"),
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
        q3_out = (current_session.query(
            Transfer.id.label("id"),
            Transfer.timestamp.label("ts"),
            Transfer.amount_origin.label("amount"),
            origin_account.currency_code.label("currency"),
            Transfer.amount_destination.label("base_val"),
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
        q3_in = (current_session.query(
            Transfer.id.label("id"),
            Transfer.timestamp.label("ts"),
            Transfer.amount_destination.label("amount"),
            dest_account.currency_code.label("currency"),
            Transfer.amount_origin.label("base_val"),
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
            (in_base, in_dict), (out_base, out_dict), net_bal = self.calculate_totals(current_query, self.db_session)

            in_brk = " | ".join([f"{amt:,.{self.dec_map.get(c, 2)}f} {c}" for c, amt in in_dict.items()]) or f"{0:,.{self.manager.base_currency_decimals}f} {self.manager.base_currency}"
            self.in_lbl.configure(text=f"In: {in_brk}  (Combined: ≈ {in_base:,.{self.manager.base_currency_decimals}f} {self.manager.base_currency})")

            out_brk = " | ".join([f"{amt:,.{self.dec_map.get(c, 2)}f} {c}" for c, amt in out_dict.items()]) or f"{0:,.{self.manager.base_currency_decimals}f} {self.manager.base_currency}"
            self.out_lbl.configure(text=f"Out: {out_brk}  (Combined: ≈ {out_base:,.{self.manager.base_currency_decimals}f} {self.manager.base_currency})")

            self.balance_lbl.configure(text=f"Balance: (≈ {net_bal:,.{self.manager.base_currency_decimals}f} {self.manager.base_currency})")

            bal_color = "#4CD964" if net_bal >= 0 else "#b13e3e"
            self.balance_lbl.configure(text_color=bal_color)
        else:
            for lbl in [self.in_lbl, self.out_lbl, self.balance_lbl]:
                lbl.configure(text="")

        if self.unlock_timer is not None:
            self.after_cancel(self.unlock_timer)
        self.unlock_timer = self.after(50, lambda: self.render_pagination_controls(disable_all=False))

    def render_pagination_controls(self, disable_all=False):
        """Creates or updates the Navigation buttons bar at the bottom."""
        if self.total_pages <= 1:
            self.nav_bar.pack_forget()
            return

        self.nav_bar.pack(before=self.totals_frame, fill="x", pady=5)
        self.nav_bar.grid_columnconfigure((0, 2), weight=1)
        self.nav_bar.grid_columnconfigure(1, weight=0)

        first_state = "disabled" if (disable_all or self.current_page <= 0) else "normal"
        prev_state = "disabled" if (disable_all or self.current_page <= 0) else "normal"
        next_state = "disabled" if (disable_all or self.current_page >= self.total_pages - 1) else "normal"
        last_state = "disabled" if (disable_all or self.current_page >= self.total_pages - 1) else "normal"

        self._is_loading = disable_all

        if getattr(self, '_nav_built', False):
            self.btn_first.configure(state=first_state)
            self.btn_prev.configure(state=prev_state)
            self.btn_next.configure(state=next_state)
            self.btn_last.configure(state=last_state)
            if not disable_all:
                self.lbl_page.configure(text=f"of {self.total_pages}")

                if self.jump_entry is not None:
                    target_page = str(self.current_page + 1)
                    if self.jump_entry.get() != target_page:
                        self.jump_entry.delete(0, "end")
                        self.jump_entry.insert(0, target_page)
            return

        for widget in self.nav_bar.winfo_children():
            widget.destroy()

        # First & Previous Buttons
        left_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        left_group.grid(row=0, column=0, sticky="e", padx=20)

        self.btn_first = ctk.CTkButton(left_group, text="« First", width=60, state=first_state, fg_color="gray30", command=self.go_to_first_page)
        self.btn_first.pack(side="left", padx=2)

        self.btn_prev = ctk.CTkButton(
            left_group, text="‹ Prev", width=70, state=prev_state,
            command=self.prev_page, fg_color="gray30"
        )
        self.btn_prev.pack(side="left", padx=2)

        # Jump to Page & Page Indicator Buttons
        center_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        center_group.grid(row=0, column=1, sticky="n")

        ctk.CTkLabel(center_group, text="Page").pack(side="left", padx=2)

        self.jump_entry = ctk.CTkEntry(center_group, width=45, height=28, justify="center")
        self.jump_entry.insert(0, str(self.current_page + 1))
        self.jump_entry.pack(side="left", padx=5)
        self.jump_entry.bind("<Return>", self.jump_to_page)

        self.lbl_page = ctk.CTkLabel(center_group, text=f"of {self.total_pages}")
        self.lbl_page.pack(side="left", padx=2)

        # Next & Last Buttons
        right_group = ctk.CTkFrame(self.nav_bar, fg_color="transparent")
        right_group.grid(row=0, column=2, sticky="w", padx=20)

        self.btn_next = ctk.CTkButton(right_group, text="Next ›", width=70, state=next_state, fg_color="gray30",
                                      command=self.next_page)
        self.btn_next.pack(side="left", padx=2)

        self.btn_last = ctk.CTkButton(right_group, text="Last »", width=60, state=last_state, fg_color="gray30",
                                      command=self.go_to_last_page)
        self.btn_last.pack(side="left", padx=2)

        self._nav_built = True

    def _schedule_page_render(self):
        """Debounces pagination to prevent DB/Render lag on rapid clicks."""
        if self.page_timer is not None:
            self.after_cancel(self.page_timer)
        # noinspection PyTypeChecker
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
            self.render_pagination_controls()
            self._schedule_page_render()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            if self.jump_entry:
                self.jump_entry.delete(0, "end")
                self.jump_entry.insert(0, str(self.current_page + 1))
            self.render_pagination_controls()
            self._schedule_page_render()

    def go_to_first_page(self):
        if self.current_page != 0:
            self.current_page = 0
            if self.jump_entry:
                self.jump_entry.delete(0, "end")
                self.jump_entry.insert(0, "1")
            self.load_transactions()

    def go_to_last_page(self):
        last_page = max(0, self.total_pages - 1)
        if self.current_page != last_page:
            self.current_page = last_page
            if self.jump_entry:
                self.jump_entry.delete(0, "end")
                self.jump_entry.insert(0, str(self.current_page + 1))
            self.load_transactions()
            self.reset_scroll_to_top()

    def jump_to_page(self, _event=None):
        if getattr(self, '_is_loading', False):
            return
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

    def reset_scroll_to_top(self):
        """Forces the canvas back to coordinate 0."""
        self.update_idletasks()
        if hasattr(self.grid_component, "_parent_canvas"):
            # noinspection PyProtectedMember
            self.grid_component._parent_canvas.yview_moveto(0)

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

        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
        # noinspection PyTypeChecker
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

        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
            self.search_timer = None

        self.load_transactions()
        self.reset_scroll_to_top()

    def _on_time_nav_change(self, new_date):
        """Called automatically by the MonthYearSelector when the user changes the date."""
        self.current_view_date = new_date
        self._schedule_nav_load()

    def on_date_filter_change(self, selection):
        if selection in ["This Month", "This Year"]:
            self.current_view_date = datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            self.time_nav.set_date(self.current_view_date)
            self.custom_date_frame.pack_forget()

            self.time_nav.set_mode(show_month=(selection == "This Month"))
            self.time_nav.pack(side="left", padx=20, anchor="n")

            self.active_date_filter = selection
            self._schedule_nav_load()
        else:
            self.time_nav.pack_forget()
            if selection == "Custom...":
                self.custom_date_frame.pack(side="left", padx=5)
            else:
                self.custom_date_frame.pack_forget()
                self.active_date_filter = selection
                self._schedule_nav_load()

    def _schedule_nav_load(self):
        """Debounces DB calls to allow rapid clicking."""
        if self.nav_timer is not None:
            self.after_cancel(self.nav_timer)
        # noinspection PyTypeChecker
        self.nav_timer = self.after(300, self._execute_nav_load)

    def _execute_nav_load(self):
        self.nav_timer = None
        self.current_page = 0
        self.load_transactions()
        self.reset_scroll_to_top()

    def _schedule_type_filter(self):
        """Debounces DB calls to allow rapid clicking."""
        if self.type_timer is not None:
            self.after_cancel(self.type_timer)
        # noinspection PyTypeChecker
        self.type_timer = self.after(600, self._execute_type_filter)

    def _execute_type_filter(self):
        """Resets view and reloads when a type checkbox is toggled."""
        self.type_timer = None
        self.current_page = 0
        self.load_transactions()
        self.reset_scroll_to_top()

    def _on_project_filter_change(self, _selection):
        """Resets view and reloads when a new project is selected."""
        self.current_page = 0
        self.load_transactions()
        self.reset_scroll_to_top()

    def refresh_view(self):
        """Called automatically when switching back to this tab.
        Fetches the latest ledger data from the database."""
        curr_val = self.project_filter_var.get()
        projects = ["All Projects", "No Project"] + [p.name for p in
                                       self.db_session.query(Project).order_by(
                                           collate(Project.name, 'NOCASE')).all()]
        self.project_menu.configure(values=projects)

        if curr_val not in projects:
            self.project_filter_var.set("All Projects")

        self.load_transactions()


