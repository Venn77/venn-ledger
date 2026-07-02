import customtkinter as ctk
from sqlalchemy import collate
from sqlalchemy.exc import IntegrityError
from database.models import (
    Currency, ExchangeRate, Account, PaymentMethod
)
from gui.dialogs import (
    SimpleDataDialog, CurrencyDialog, FXDialog,
    AccountDialog, PMDialog, show_popup
)

class SimpleMasterDataGrid(ctk.CTkFrame):
    """Renders a dynamic grid for simple CRUD operations on db."""
    def __init__(self, parent, db_session, model, title, has_desc=False):
        super().__init__(parent, fg_color="transparent")
        self.db_session = db_session
        self.model = model
        self.title = title
        self.has_desc = has_desc
        self.current_results = None
        self.total_items = None

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header_frame, text=title, font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header_frame, text="+ Add New", width=130, command=self.add_new).pack(side="right")

        self.loading_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.loading_lbl = ctk.CTkLabel(self.loading_frame, text="Loading...", font=("JetBrains Mono", 16, "bold"),
                                        text_color="#5AC8FA")
        self.loading_lbl.pack(pady=50)

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)

        self.load_data()

    def load_data(self):
        if hasattr(self, '_render_job') and self._render_job:
            self.after_cancel(self._render_job)

        self.scroll.pack_forget()
        self.loading_frame.pack(fill="both", expand=True)
        self.loading_lbl.configure(text="Fetching data...")

        for widget in self.scroll.winfo_children():
            widget.destroy()

        self.current_results = self.db_session.query(self.model).order_by(collate(self.model.name, 'NOCASE')).all()
        self.total_items = len(self.current_results)

        if self.total_items > 0:
            self._render_batch(start_idx=0, batch_size=25)
        else:
            self._finish_loading()

    def _render_batch(self, start_idx, batch_size):
        end_idx = min(start_idx + batch_size, len(self.current_results))

        self.loading_lbl.configure(text=f"Loading... {end_idx} / {self.total_items}")

        for idx in range(start_idx, end_idx):
            item = self.current_results[idx]
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            name_lbl = ctk.CTkLabel(row, text=item.name, width=150, anchor="w", font=("JetBrains Mono", 12, "bold"))
            name_lbl.pack(side="left", padx=10, pady=8)

            if self.has_desc and hasattr(item, 'description'):
                desc_text = (item.description[:30] + '...') if item.description and len(
                    item.description) > 30 else item.description
                ctk.CTkLabel(row, text=desc_text or "", width=150, anchor="w", text_color="gray60").pack(side="left",
                                                                                                         padx=10)

            # Action Buttons
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            toggle_text = "Deactivate" if item.active_bool else "Activate"
            toggle_color = "#b13e3e" if item.active_bool else "#1f538d"

            ctk.CTkButton(btn_frame, text=toggle_text, width=80, height=24, fg_color=toggle_color,
                          command=lambda i=item.id: self.toggle_status(i)).pack(side="right", padx=2)

            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit_item(i)).pack(side="right", padx=2)

            # Status Label
            status_text = "Active" if item.active_bool else "Inactive"
            status_color = "#4CD964" if item.active_bool else "gray50"
            ctk.CTkLabel(row, text=status_text, text_color=status_color, width=60, font=("JetBrains Mono", 11)).pack(
                side="right", padx=10)

        if end_idx < self.total_items:
            self._render_job = self.after(10, self._render_batch, end_idx, batch_size)
        else:
            self._finish_loading()

    def _finish_loading(self):
        self.loading_frame.pack_forget()
        self.scroll.pack(fill="both", expand=True)

    def toggle_status(self, item_id):
        try:
            item = self.db_session.get(self.model, item_id)
            if item:
                item.active_bool = not item.active_bool
                self.db_session.commit()
                self.load_data()
        except Exception as e:
            self.db_session.rollback()
            show_popup(self, "Database Error", f"Failed to toggle status:\n{e}", is_error=True)

    def add_new(self):
        def _save(new_name, new_desc):
            try:
                if self.model.__name__ == "Project" and new_name.strip().lower() in ["all projects", "no project"]:
                    return False, "This is a reserved system name."

                existing_item = self.db_session.query(self.model).filter_by(name=new_name).first()

                if existing_item:
                    if not existing_item.active_bool:
                        existing_item.active_bool = True
                        if self.has_desc and hasattr(existing_item, 'description'):
                            existing_item.description = new_desc
                        self.db_session.commit()
                        self.load_data()
                        return True, ""
                    else:
                        return False, f"'{new_name}' already exists and is active."

                if self.has_desc:
                    new_item = self.model(name=new_name, description=new_desc)
                else:
                    new_item = self.model(name=new_name)

                self.db_session.add(new_item)
                self.db_session.commit()
                self.load_data()
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, "Database Integrity Error."
            except Exception as e:
                self.db_session.rollback()
                return False, str(e)

        SimpleDataDialog(self, f"Add {self.model.__name__}", has_desc=self.has_desc, on_submit=_save)

    def edit_item(self, item):
        initial_desc = item.description if self.has_desc and hasattr(item, 'description') else ""

        def _update(new_name, new_desc):
            try:
                if self.model.__name__ == "Project" and new_name.strip().lower() in ["all projects", "no project"]:
                    return False, "This is a reserved system name."

                existing_item = self.db_session.query(self.model).filter_by(name=new_name).first()
                if existing_item and existing_item.id != item.id:
                    status = "active" if existing_item.active_bool else "deactivated"
                    return False, f"Name already used by a {status} item."

                item.name = new_name
                if self.has_desc and hasattr(item, 'description'):
                    item.description = new_desc

                self.db_session.commit()
                self.load_data()
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, "Database Integrity Error."
            except Exception as e:
                self.db_session.rollback()
                return False, str(e)

        SimpleDataDialog(self, f"Edit {self.model.__name__}", initial_name=item.name, initial_desc=initial_desc,
                         has_desc=self.has_desc, on_submit=_update)

class CurrencyGrid(ctk.CTkFrame):
    """Renders a dynamic grid for CRUD operations on currencies table."""
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.db_session = db_session

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Currencies", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add Currency", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self):
        for widget in self.scroll.winfo_children(): widget.destroy()
        items = self.db_session.query(Currency).order_by(collate(Currency.code, 'NOCASE')).all()
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=item.code, width=40, font=("JetBrains Mono", 12, "bold"), text_color="#5AC8FA").pack(
                side="left", padx=(10, 5), pady=8)
            ctk.CTkLabel(row, text=item.name, width=150, anchor="w", font=("JetBrains Mono", 11)).pack(side="left",
                                                                                                       padx=5)
            if item.is_base:
                ctk.CTkLabel(row, text="[BASE]", text_color="#4CD964", font=("JetBrains Mono", 10, "bold")).pack(
                    side="left", padx=5)
            else:
                math_symbol = "[ × ]" if item.quotation_method == "multiply" else "[ ÷ ]"
                ctk.CTkLabel(row, text=math_symbol, text_color="gray50", font=("JetBrains Mono", 12, "bold")).pack(
                    side="left", padx=5)

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            toggle_text, toggle_color = ("Deactivate", "#b13e3e") if item.active_bool else ("Activate", "#1f538d")
            state = "disabled" if item.is_base == True else "normal"
            ctk.CTkButton(btn_frame, text=toggle_text, width=80, height=24, fg_color=toggle_color, state=state,
                          command=lambda i=item.code: self.toggle(i)).pack(side="right", padx=2)
            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit(i)).pack(side="right", padx=2)

            status = "Active" if item.active_bool else "Inactive"
            color = "#4CD964" if item.active_bool else "gray50"
            ctk.CTkLabel(row, text=status, text_color=color, width=60, font=("JetBrains Mono", 11)).pack(side="right",
                                                                                                         padx=10)

    def toggle(self, code):
        try:
            item = self.db_session.get(Currency, code)
            if item.is_base:
                show_popup(self, "Error", "You cannot deactivate the base currency.", is_error=True)
                return
            item.active_bool = not item.active_bool
            self.db_session.commit()
            self.load_data()
            self.winfo_toplevel().event_generate("<<SettingsUpdate>>")
        except Exception as e:
            self.db_session.rollback()
            show_popup(self, "Database Error", f"Failed to toggle currency:\n{e}", is_error=True)

    def add_new(self):
        def _save(code, name, q_method, decimals):
            try:
                if self.db_session.get(Currency, code): return False, "Currency Code already exists."
                self.db_session.add(Currency(code=code[:10], name=name, is_base=False, quotation_method=q_method, decimals=decimals))
                self.db_session.commit()
                self.load_data()
                self.winfo_toplevel().event_generate("<<SettingsUpdate>>")
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, "Database Integrity Error."
            except Exception as e:
                self.db_session.rollback()
                return False, f"Database error: {str(e)}"

        CurrencyDialog(self, "Add Currency", on_submit=_save)

    def edit(self, item):
        def _update(_code, name):
            try:
                item.name = name
                self.db_session.commit()
                self.load_data()
                return True, ""
            except Exception as e:
                self.db_session.rollback()
                return False, f"Database error: {str(e)}"

        CurrencyDialog(self, "Edit Currency Name", initial_code=item.code, initial_name=item.name, is_edit=True,
                       on_submit=_update)

class ExchangeRateGrid(ctk.CTkFrame):
    """Renders a dynamic grid for CRUD operations on exchange_rates table."""
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.db_session = db_session
        self.current_results = None
        self.total_items = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Exchange Rates", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        self.btn_add = ctk.CTkButton(header, text="+ Log New Rate", width=130, command=self.add_new)
        self.btn_add.pack(side="right")

        self.lbl_warning = ctk.CTkLabel(self, text="⚠ Add a foreign currency in 'Currencies' to log rates.",
                                        text_color="orange", font=("JetBrains Mono", 11))

        self.loading_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.loading_lbl = ctk.CTkLabel(self.loading_frame, text="Loading...", font=("JetBrains Mono", 16, "bold"),
                                        text_color="#5AC8FA")
        self.loading_lbl.pack(pady=50)

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self):
        if hasattr(self, '_render_job') and self._render_job:
            self.after_cancel(self._render_job)

        self.scroll.pack_forget()
        self.loading_frame.pack(fill="both", expand=True)
        self.loading_lbl.configure(text="Fetching data...")

        for widget in self.scroll.winfo_children(): widget.destroy()

        self.current_results = (
                    self.db_session.query(ExchangeRate)
                    .join(Currency)
                    .filter(Currency.is_base == False)
                    .order_by(ExchangeRate.timestamp.desc())
                    .limit(500)
                    .all()
            )
        self.total_items = len(self.current_results)

        if self.total_items > 0:
            self._render_batch(start_idx=0, batch_size=25)
        else:
            self._finish_loading()

    def _render_batch(self, start_idx, batch_size):
        end_idx = min(start_idx + batch_size, len(self.current_results))

        self.loading_lbl.configure(text=f"Loading... {end_idx} / {self.total_items}")

        for idx in range(start_idx, end_idx):
            r = self.current_results[idx]
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=r.currency_code, width=40, font=("JetBrains Mono", 12, "bold"),
                         text_color="#5AC8FA").pack(side="left", padx=(10, 5), pady=8)
            ctk.CTkLabel(row, text=f"Rate: {r.fx_multiplier:,.4f}", width=120, anchor="w",
                         font=("JetBrains Mono", 11, "bold")).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=r.timestamp.strftime("%Y-%m-%d %H:%M"), text_color="gray50",
                         font=("JetBrains Mono", 10)).pack(side="left", padx=10)

            ctk.CTkButton(row, text="✕", width=30, height=24, fg_color="transparent", text_color="gray50",
                          hover_color="#8b2525",
                          command=lambda i=r.id: self.delete(i)).pack(side="right", padx=10)

        if end_idx < self.total_items:
            self._render_job = self.after(10, self._render_batch, end_idx, batch_size)
        else:
            self._finish_loading()

    def _finish_loading(self):
        self.loading_frame.pack_forget()
        act_currencies = [c for c in self.db_session.query(Currency).filter_by(active_bool=True).all() if not c.is_base]
        if not act_currencies:
            self.btn_add.configure(state="disabled")
            self.scroll.pack_forget()
            self.lbl_warning.pack(pady=5)
        else:
            self.btn_add.configure(state="normal")
            self.lbl_warning.pack_forget()
            self.scroll.pack(fill="both", expand=True)

    def delete(self, rate_id):
        rate = self.db_session.get(ExchangeRate, rate_id)
        context_text = f"[{rate.timestamp.strftime('%Y-%m-%d')}] {rate.currency_code} | {rate.fx_multiplier}" if rate else ""
        popup = ctk.CTkToplevel(self)
        popup.title("Confirm")
        width = 250
        height = 150
        popup.geometry(f"{width}x{height}")
        popup.attributes("-topmost", True)
        popup.grab_set()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        popup.geometry(f"+{x}+{y}")

        ctk.CTkLabel(popup, text="Delete this exchange rate?", font=("JetBrains Mono", 12)).pack(pady=(20, 5))
        ctk.CTkLabel(popup, text=context_text, font=("JetBrains Mono", 11), text_color="orange").pack(pady=(0, 15))

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack()

        def _confirm():
            if rate:
                try:
                    rate_count = self.db_session.query(ExchangeRate).filter_by(currency_code=rate.currency_code).count()
                    acc_count = self.db_session.query(Account).filter_by(currency_code=rate.currency_code).count()

                    if rate_count <= 1 and acc_count > 0:
                        show_popup(self, "Action Blocked",
                                   f"Cannot delete the last {rate.currency_code} rate.\nYou have accounts depending on it.",
                                   is_error=True)
                        popup.destroy()
                        return
                    self.db_session.delete(rate)
                    self.db_session.commit()
                    self.load_data()
                    self.winfo_toplevel().event_generate("<<SidebarUpdate>>")
                except Exception as e:
                    self.db_session.rollback()
                    show_popup(self, "Database Error", f"Failed to delete rate:\n{e}", is_error=True)
            popup.destroy()

        ctk.CTkButton(btn_frame, text="Cancel", width=70, fg_color="gray40", command=popup.destroy).pack(side="left",
                                                                                                         padx=5)
        ctk.CTkButton(btn_frame, text="Delete", width=70, fg_color="#8b2525", hover_color="#611a1a",
                      command=_confirm).pack(side="left", padx=5)

    def add_new(self):
        base_curr = self.db_session.query(Currency).filter_by(is_base=True).first()
        if not base_curr:
            return

        foreign_currs = self.db_session.query(Currency).filter_by(active_bool=True, is_base=False).order_by(collate(Currency.code, 'NOCASE')).all()
        if not foreign_currs:
            return

        curr_dict = {
            c.code: {
                "method": c.quotation_method,
                "decimals": c.decimals
            } for c in foreign_currs
        }

        def _save(code, rate, timestamp):
            try:
                self.db_session.add(ExchangeRate(currency_code=code, fx_multiplier=rate, timestamp=timestamp))
                self.db_session.commit()
                self.load_data()
                self.winfo_toplevel().event_generate("<<SidebarUpdate>>")
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, f"A rate for {code} exactly at this time already exists."
            except Exception as e:
                self.db_session.rollback()
                return False, f"Database error: {str(e)}"

        FXDialog(
            self,
            currency_data=curr_dict,
            base_code=base_curr.code,
            base_decimals=base_curr.decimals,
            on_submit=_save
        )

class AccountGrid(ctk.CTkFrame):
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.db_session = db_session
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Accounts", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add Account", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self):
        for widget in self.scroll.winfo_children(): widget.destroy()
        items = self.db_session.query(Account).order_by(collate(Account.name, 'NOCASE')).all()
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=item.name, width=120, anchor="w", font=("JetBrains Mono", 12, "bold")).pack(
                side="left", padx=10, pady=8)
            ctk.CTkLabel(row, text=f"{item.balance:,.{item.currency.decimals}f} {item.currency_code}", width=100, anchor="w",
                         text_color="#5AC8FA", font=("JetBrains Mono", 11, "bold")).pack(side="left", padx=5)

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)
            t_text, t_color = ("Deactivate", "#b13e3e") if item.active_bool else ("Activate", "#1f538d")

            ctk.CTkButton(btn_frame, text=t_text, width=80, height=24, fg_color=t_color,
                          command=lambda i=item: self.toggle(i)).pack(side="right", padx=2)
            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit(i)).pack(side="right", padx=2)

            status, color = ("Active", "#4CD964") if item.active_bool else ("Inactive", "gray50")
            ctk.CTkLabel(row, text=status, text_color=color, width=60, font=("JetBrains Mono", 11)).pack(side="right",
                                                                                                         padx=10)

    def toggle(self, acc):
        if acc.active_bool and acc.balance != 0:
            popup = ctk.CTkToplevel(self)
            popup.title("Warning")
            popup.geometry("350x180")
            popup.attributes("-topmost", True)
            popup.grab_set()
            self.update_idletasks()
            popup.geometry(f"+{self.winfo_x() + 100}+{self.winfo_y() + 100}")

            msg = f"Account '{acc.name}' has a balance of {acc.balance:,.{acc.currency.decimals}f}.\n\nDeactivating it hides it from menus and\ndeactivates its Payment Methods, but the\nbalance will STILL count toward Net Worth.\n\nProceed?"
            ctk.CTkLabel(popup, text=msg, font=("JetBrains Mono", 11)).pack(pady=15)

            def _confirm():
                self._execute_toggle(acc)
                popup.destroy()

            bf = ctk.CTkFrame(popup, fg_color="transparent")
            bf.pack()
            ctk.CTkButton(bf, text="Cancel", width=80, fg_color="gray40", command=popup.destroy).pack(side="left",
                                                                                                      padx=10)
            ctk.CTkButton(bf, text="Deactivate", width=80, fg_color="#b13e3e", command=_confirm).pack(side="left",
                                                                                                      padx=10)
        else:
            self._execute_toggle(acc)

    def _execute_toggle(self, acc):
        try:
            acc.active_bool = not acc.active_bool
            if not acc.active_bool:
                for pm in acc.payment_methods: pm.active_bool = False
            self.db_session.commit()
            self.load_data()

            self.winfo_toplevel().event_generate("<<SidebarUpdate>>")
            self.winfo_toplevel().event_generate("<<SettingsUpdate>>")
        except Exception as e:
            self.db_session.rollback()
            show_popup(self, "Database Error", f"Failed to toggle account:\n{e}", is_error=True)

    def add_new(self):
        currencies = self.db_session.query(Currency).filter_by(active_bool=True).order_by(collate(Currency.code, 'NOCASE')).all()
        if not currencies: return

        curr_data = {c.code: c.decimals for c in currencies}

        def _save(name, descr, curr_code, bal):
            try:
                curr_obj = self.db_session.query(Currency).filter_by(code=curr_code).first()
                if not curr_obj.is_base:
                    has_rate = self.db_session.query(ExchangeRate).filter_by(currency_code=curr_code).first()
                    if not has_rate:
                        return False, f"You must log an Exchange Rate for {curr_code} first."
                if self.db_session.query(Account).filter_by(name=name).first(): return False, "Name already exists."
                self.db_session.add(Account(name=name, description=descr, currency_code=curr_code, balance=bal, initial_balance=bal))
                self.db_session.commit()
                self.load_data()
                self.winfo_toplevel().event_generate("<<SidebarUpdate>>")
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, "Database Integrity Error."
            except Exception as e:
                self.db_session.rollback()
                return False, f"Database error: {str(e)}"

        AccountDialog(self, currency_data=curr_data, on_submit=_save)

    def edit(self, acc):
        def _update(name, descr, _curr, _bal):
            try:
                existing = self.db_session.query(Account).filter_by(name=name).first()
                if existing and existing.id != acc.id: return False, "Name in use."
                acc.name = name
                acc.description = descr
                self.db_session.commit()
                self.load_data()
                self.winfo_toplevel().event_generate("<<SidebarUpdate>>")
                self.winfo_toplevel().event_generate("<<SettingsUpdate>>")
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, "Database Integrity Error."
            except Exception as e:
                self.db_session.rollback()
                return False, f"Database error: {str(e)}"

        curr_data = {acc.currency_code: acc.currency.decimals}

        AccountDialog(self, currency_data=curr_data, initial_name=acc.name, initial_desc=acc.description, initial_curr=acc.currency_code,
                      initial_bal=str(acc.initial_balance), is_edit=True, on_submit=_update)

class PMGrid(ctk.CTkFrame):
    def __init__(self, parent, db_session):
        super().__init__(parent, fg_color="transparent")
        self.db_session = db_session
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Payment Methods", font=("JetBrains Mono", 16, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ Add Method", width=130, command=self.add_new).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True)
        self.load_data()

    def load_data(self, _event=None):
        for widget in self.scroll.winfo_children(): widget.destroy()
        items = self.db_session.query(PaymentMethod).join(Account).order_by(collate(Account.name, 'NOCASE'), collate(PaymentMethod.name, 'NOCASE')).all()
        for item in items:
            row = ctk.CTkFrame(self.scroll, fg_color="gray20", corner_radius=6)
            row.pack(fill="x", pady=2, padx=2)

            ctk.CTkLabel(row, text=item.name, width=120, anchor="w", font=("JetBrains Mono", 12, "bold")).pack(
                side="left", padx=10, pady=8)

            acc_color = "gray60" if not item.account.active_bool else "#5AC8FA"
            acc_text = f"→ {item.account.name}"
            ctk.CTkLabel(row, text=acc_text, width=140, anchor="w", text_color=acc_color,
                         font=("JetBrains Mono", 11)).pack(side="left", padx=5)

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=10)

            t_text, t_color = ("Deactivate", "#b13e3e") if item.active_bool else ("Activate", "#1f538d")

            state = "disabled" if not item.active_bool and not item.account.active_bool else "normal"
            ctk.CTkButton(btn_frame, text=t_text, width=80, height=24, fg_color=t_color, state=state,
                          command=lambda i=item.id: self.toggle(i)).pack(side="right", padx=2)
            ctk.CTkButton(btn_frame, text="Edit", width=60, height=24, fg_color="gray30", hover_color="gray40",
                          command=lambda i=item: self.edit(i)).pack(side="right", padx=2)

            status, color = ("Active", "#4CD964") if item.active_bool else ("Inactive", "gray50")
            ctk.CTkLabel(row, text=status, text_color=color, width=60, font=("JetBrains Mono", 11)).pack(side="right",
                                                                                                         padx=10)

    def toggle(self, item_id):
        try:
            item = self.db_session.get(PaymentMethod, item_id)
            item.active_bool = not item.active_bool
            self.db_session.commit()
            self.load_data()
        except Exception as e:
            self.db_session.rollback()
            show_popup(self, "Database Error", f"Failed to toggle Payment Method:\n{e}", is_error=True)

    def add_new(self):
        act_accounts = [a.name for a in self.db_session.query(Account).filter_by(active_bool=True).order_by(collate(Account.name, 'NOCASE')).all()]
        if not act_accounts: return

        def _save(name, acc_name):
            try:
                if self.db_session.query(PaymentMethod).filter_by(name=name).first(): return False, "Name in use."
                acc = self.db_session.query(Account).filter_by(name=acc_name).first()
                self.db_session.add(PaymentMethod(name=name, account_id=acc.id))
                self.db_session.commit()
                self.load_data()
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, "Database Integrity Error."
            except Exception as e:
                self.db_session.rollback()
                return False, f"Database error: {str(e)}"

        PMDialog(self, act_accounts, on_submit=_save)

    def edit(self, item):
        act_accounts = [a.name for a in self.db_session.query(Account).filter_by(active_bool=True).order_by(collate(Account.name, 'NOCASE')).all()]
        if item.account.name not in act_accounts: act_accounts.append(item.account.name)

        def _update(name, acc_name):
            try:
                existing = self.db_session.query(PaymentMethod).filter_by(name=name).first()
                if existing and existing.id != item.id: return False, "Name in use."
                acc = self.db_session.query(Account).filter_by(name=acc_name).first()
                item.name = name
                item.account_id = acc.id
                self.db_session.commit()
                self.load_data()
                return True, ""
            except IntegrityError:
                self.db_session.rollback()
                return False, "Database Integrity Error."
            except Exception as e:
                self.db_session.rollback()
                return False, f"Database error: {str(e)}"

        PMDialog(self, act_accounts, initial_name=item.name, initial_acc=item.account.name, on_submit=_update)