from database.models import (
    calculate_conversion,
    Category, Vendor, Account, PaymentMethod,
    Project, Expense, ExchangeRate, Transfer,
    Stream, Payer, Gain
)
from decimal import Decimal
from sqlalchemy import func
import datetime


class TransactionManager:
    def __init__(self, db_session):
        self.db_session = db_session
        self.last_used = {
            "currency": "EUR",
            "pm": "",
            "acc": "",
            "orig_acc": "",
            "dest_acc": "",
            "project": "",
            "date": datetime.datetime.now().strftime("%Y-%m-%d")
        }

    @staticmethod
    def _safe_add(val1, val2):
        """Safely adds two floats using Decimal to prevent precision drift."""
        return float(Decimal(str(val1)) + Decimal(str(val2)))

    @staticmethod
    def _safe_sub(val1, val2):
        """Safely subtracts val2 from val1 using Decimal."""
        return float(Decimal(str(val1)) - Decimal(str(val2)))

    def _resolve_fx_rate(self, currency_code, exchange_rate):
        """Resolves the FX rate, fetching the latest historical rate if none is provided."""
        if exchange_rate:
            return exchange_rate
        if currency_code == "EUR":
            return None

        rate_entry = (self.db_session.query(ExchangeRate)
                      .filter_by(currency_code=currency_code)
                      .order_by(ExchangeRate.timestamp.desc())
                      .first())
        if not rate_entry:
            raise ValueError(f"No exchange rate found for {currency_code}.")
        return rate_entry.fx_multiplier

    def _get_or_create_dimension(self, model, name):
        """
        Handles the 'Master Data' lookup.
        If the item exists but is inactive, it reactivates it.
        If it doesn't exist, it creates it.
        """
        name = name.strip()
        item = self.db_session.query(model).filter_by(name=name).first()
        if item:
            if not item.active_bool:
                item.active_bool = True
            return item

        new_item = model(name=name)
        self.db_session.add(new_item)
        self.db_session.flush()
        return new_item

    def add_expense(self, amount, currency_code, payment_method_name, exchange_rate=None, category_name=None, vendor_name=None,
                    project_name=None, description=None,
                    timestamp=None, expense_id=None):
        """Adds an expense to DB or edits an existing one."""
        # 1. Resolve Master Data
        category = self._get_or_create_dimension(Category, category_name) if category_name else None
        vendor = self._get_or_create_dimension(Vendor, vendor_name) if vendor_name else None
        project = self._get_or_create_dimension(Project, project_name) if project_name else None

        # 2. Resolve Payment Method & Account
        pm = self.db_session.query(PaymentMethod).filter_by(name=payment_method_name).first()

        if not pm:
            raise ValueError(f"Payment Method '{payment_method_name}' not found.")

        account = pm.account

        # 3. FX Logic
        fx_rate = self._resolve_fx_rate(currency_code, exchange_rate)

        # 4. Upsert Object & Revert Balance
        if expense_id:
            new_expense = self.db_session.get(Expense, expense_id)
            old_account = new_expense.payment_method.account
            old_account.balance = self._safe_add(old_account.balance, new_expense.amount)
        else:
            new_expense = Expense()

        cat_id = category.id if category and hasattr(category, 'id') else None
        ven_id = vendor.id if vendor and hasattr(vendor, 'id') else None
        proj_id = project.id if project and hasattr(project, 'id') else None

        # 5. Update Fields
        new_expense.amount = amount
        new_expense.currency_code = currency_code
        new_expense.fx_rate = fx_rate
        new_expense.category_id = cat_id
        new_expense.vendor_id = ven_id
        new_expense.payment_method_id = pm.id
        new_expense.project_id = proj_id
        new_expense.description = description
        new_expense.timestamp = timestamp or datetime.datetime.now()

        new_expense = calculate_conversion(new_expense)

        account.balance = self._safe_sub(account.balance, amount)

        try:
            if not expense_id: self.db_session.add(new_expense)
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e

        # 6. Update the Memory after a successful save
        self.last_used["currency"] = currency_code
        self.last_used["pm"] = payment_method_name
        self.last_used["project"] = project_name
        if timestamp and hasattr(timestamp, 'strftime'):
            self.last_used["date"] = timestamp.strftime("%Y-%m-%d")
        else:
            self.last_used["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

        return new_expense

    def add_gain(self, amount, currency_code, account_id, exchange_rate=None, stream_name=None, payer_name=None,
                    project_name=None, description=None,
                    timestamp=None, gain_id=None):
        """Adds a gain to DB or edits an existing one."""
        # 1. Resolve Master Data
        stream = self._get_or_create_dimension(Stream, stream_name) if stream_name else None
        payer = self._get_or_create_dimension(Payer, payer_name) if payer_name else None
        project = self._get_or_create_dimension(Project, project_name) if project_name else None

        # 2. Resolve Account
        account = self.db_session.query(Account).filter_by(id=account_id).first()

        # 3. FX Logic
        fx_rate = self._resolve_fx_rate(currency_code, exchange_rate)

        # 4. Upsert Object & Revert Balance
        if gain_id:
            new_gain = self.db_session.get(Gain, gain_id)
            old_account = new_gain.account
            old_account.balance = self._safe_sub(old_account.balance, new_gain.amount)
        else:
            new_gain = Gain()

        str_id = stream.id if stream and hasattr(stream, 'id') else None
        pay_id = payer.id if payer and hasattr(payer, 'id') else None
        proj_id = project.id if project and hasattr(project, 'id') else None

        # 5. Update Fields
        new_gain.amount = amount
        new_gain.currency_code = currency_code
        new_gain.fx_rate = fx_rate
        new_gain.stream_id = str_id
        new_gain.payer_id = pay_id
        new_gain.account_id = account_id
        new_gain.project_id = proj_id
        new_gain.description = description
        new_gain.timestamp = timestamp or datetime.datetime.now()

        new_gain = calculate_conversion(new_gain)

        account.balance = self._safe_add(account.balance, amount)

        try:
            if not gain_id: self.db_session.add(new_gain)
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            raise e

        # 6. Update the Memory after a successful save
        self.last_used["currency"] = currency_code
        self.last_used["acc"] = account.name
        self.last_used["project"] = project_name
        if timestamp and hasattr(timestamp, 'strftime'):
            self.last_used["date"] = timestamp.strftime("%Y-%m-%d")
        else:
            self.last_used["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

        return new_gain

    def check_for_duplicate(self, amount, entity_name, date_str, transaction_type="expense", origin_id=None, destination_id=None, amount_dest=None, exclude_id=None):
        """Returns True if a transaction with same amount, entity (vendor/payer) / account (origin/destination), and date exists."""
        target_date = date_str.split(" ")[0]

        if transaction_type == "expense":
            query = self.db_session.query(Expense).join(Vendor).filter(
                Expense.amount == amount,
                Vendor.name == entity_name,
                func.date(Expense.timestamp) == target_date
            )
            if exclude_id:
                query = query.filter(Expense.id != exclude_id)

            exists = query.first()

        elif transaction_type == "gain":
            query = self.db_session.query(Gain).join(Payer).filter(
                Gain.amount == amount,
                Payer.name == entity_name,
                func.date(Gain.timestamp) == target_date
            )
            if exclude_id:
                query = query.filter(Gain.id != exclude_id)

            exists = query.first()

        elif transaction_type == "transfer":
            query = self.db_session.query(Transfer).filter(
                Transfer.amount_origin == amount,
                Transfer.amount_destination == amount_dest,
                Transfer.origin_account_id == origin_id,
                Transfer.destination_account_id == destination_id,
                func.date(Transfer.timestamp) == target_date
            )
            if exclude_id:
                query = query.filter(Transfer.id != exclude_id)

            exists = query.first()

        else:
            exists = None

        return exists is not None

    def get_historical_fx_rate(self, currency_code, target_date):
        """
        Finds the closest exchange rate for the given currency
        that was recorded ON or BEFORE the target_date.
        """
        rate_entry = (self.db_session.query(ExchangeRate)
                      .filter(ExchangeRate.currency_code == currency_code)
                      .filter(ExchangeRate.timestamp <= target_date)
                      .order_by(ExchangeRate.timestamp.desc())
                      .first())
        if rate_entry:
            return rate_entry.fx_multiplier, rate_entry.timestamp

        return None

    def get_net_worth(self):
        """Calculates total balance of all accounts, converted to EUR."""
        accounts = self.db_session.query(Account).all()
        total_eur = 0.0

        for acc in accounts:
            if acc.currency_code == "EUR":
                total_eur = self._safe_add(total_eur, acc.balance)
            else:
                # Get the latest rate
                rate = (self.db_session.query(ExchangeRate)
                        .filter(ExchangeRate.currency_code == acc.currency_code)
                        .order_by(ExchangeRate.timestamp.desc())
                        .first())

                multiplier = rate.fx_multiplier if rate else 1.0
                converted_balance = float(Decimal(str(acc.balance)) / Decimal(str(multiplier)))
                total_eur = self._safe_add(total_eur, converted_balance)

        return total_eur

    def transfer_funds(self, origin_id, destination_id, amount_orig, amount_dest, desc, ts=None, transfer_id=None):
        """Transfers funds between two accounts or edits an existing transfer."""
        try:
            origin = self.db_session.get(Account, origin_id)
            destination = self.db_session.get(Account, destination_id)

            prefix = f"{origin.currency_code} -> {destination.currency_code}{' | ' if desc else ''}"
            full_desc = prefix + desc

            if transfer_id:
                new_transfer = self.db_session.get(Transfer, transfer_id)
                old_origin_account = new_transfer.origin_account
                old_origin_account.balance = self._safe_add(old_origin_account.balance, new_transfer.amount_origin)
                old_destination_account = new_transfer.destination_account
                old_destination_account.balance = self._safe_sub(old_destination_account.balance, new_transfer.amount_destination)
            else:
                new_transfer = Transfer()

            new_transfer.origin_account_id = origin_id
            new_transfer.destination_account_id = destination_id
            new_transfer.amount_origin = amount_orig
            new_transfer.amount_destination = amount_dest
            new_transfer.description = full_desc
            new_transfer.timestamp = ts or datetime.datetime.now()

            # Update balances
            origin.balance = self._safe_sub(origin.balance, amount_orig)
            destination.balance = self._safe_add(destination.balance, amount_dest)

            if not transfer_id: self.db_session.add(new_transfer)
            self.db_session.commit()

        except Exception as e:
            self.db_session.rollback()
            raise e

        self.last_used["orig_acc"] = origin.name
        self.last_used["dest_acc"] = destination.name

        if ts and hasattr(ts, 'strftime'):
            self.last_used["date"] = ts.strftime("%Y-%m-%d")
        else:
            self.last_used["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

        return new_transfer

    def delete_transaction(self, transaction_id, transaction_type):
        """Deletes a transaction and reverses its impact on account balances."""
        try:
            if transaction_type == "expense":
                item = self.db_session.get(Expense, transaction_id)
                if item:
                    account = item.payment_method.account
                    account.balance = self._safe_add(account.balance, item.amount)
                    self.db_session.delete(item)

            elif transaction_type == "gain":
                item = self.db_session.get(Gain, transaction_id)
                if item:
                    account = item.account
                    account.balance = self._safe_sub(account.balance, item.amount)
                    self.db_session.delete(item)

            elif transaction_type in ["transfer_out", "transfer_in"]:
                item = self.db_session.get(Transfer, transaction_id)
                if item:
                    origin = item.origin_account
                    destination = item.destination_account
                    origin.balance = self._safe_add(origin.balance, item.amount_origin)
                    destination.balance = self._safe_sub(destination.balance, item.amount_destination)
                    self.db_session.delete(item)

            self.db_session.commit()
            return True

        except Exception as e:
            self.db_session.rollback()
            raise e

