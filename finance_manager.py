from models import (
    calculate_conversion,
    Category, Vendor, Account, PaymentMethod,
    Project, Expense, ExchangeRate, Transfer,
    Stream, Payer, Gain
)
from decimal import Decimal
from sqlalchemy import func
import datetime


class TransactionManager:
    def __init__(self, session):
        self.session = session
        self.last_used = {
            "currency": "EUR",
            "pm": "",
            "acc": "",
            "project": "",
            "date": datetime.datetime.now().strftime("%Y-%m-%d")
        }

    def _get_or_create_dimension(self, model, name):
        """
        Handles the 'Master Data' lookup.
        If the item exists but is inactive, it reactivates it.
        If it doesn't exist, it creates it.
        """
        name = name.strip()
        item = self.session.query(model).filter_by(name=name).first()
        if item:
            if not item.active_bool:
                item.active_bool = True
            return item

        new_item = model(name=name)
        self.session.add(new_item)
        self.session.flush()
        return new_item

    def add_expense(self, amount, currency_code, payment_method_name, exchange_rate=None, category_name=None, vendor_name=None,
                    project_name=None, description=None,
                    timestamp=None):
        """Adds an expense to DB."""
        # 1. Resolve Master Data
        category = self._get_or_create_dimension(Category, category_name) if category_name else None
        vendor = self._get_or_create_dimension(Vendor, vendor_name) if vendor_name else None
        project = self._get_or_create_dimension(Project, project_name) if project_name else None

        # 2. Resolve Payment Method & Account
        pm = self.session.query(PaymentMethod).filter_by(name=payment_method_name).first()

        if not pm:
            raise ValueError(f"Payment Method '{payment_method_name}' not found. Please create it first.")

        account = pm.account

        # 3. FX Logic
        if not exchange_rate:
            fx_rate = None
            if currency_code != "EUR":
                rate_entry = (self.session.query(ExchangeRate)
                              .filter_by(currency_code=currency_code)
                              .order_by(ExchangeRate.timestamp.desc())
                              .first())
                if not rate_entry:
                    raise ValueError(f"No exchange rate found for {currency_code}. Please seed rates.")
                fx_rate = rate_entry.fx_multiplier
        else:
            fx_rate = exchange_rate

        # 4. Create Expense Object
        new_expense = Expense(
            amount=amount,
            currency_code=currency_code,
            fx_rate=fx_rate,
            category_id=category.id if category else None,
            vendor_id=vendor.id if vendor else None,
            payment_method_id=pm.id,
            project_id=project.id if project else None,
            description=description,
            timestamp=timestamp or datetime.datetime.now()
        )
        new_expense = calculate_conversion(new_expense)

        # Subtract the 'raw' amount from the account balance
        account.balance = float(Decimal(str(account.balance)) - Decimal(str(amount)))

        try:
            self.session.add(new_expense)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e

        # Update the Memory after a successful save
        self.last_used["currency"] = currency_code
        self.last_used["pm"] = payment_method_name
        self.last_used["project"] = project_name
        # Store just the date part
        if timestamp and hasattr(timestamp, 'strftime'):
            self.last_used["date"] = timestamp.strftime("%Y-%m-%d")
        else:
            self.last_used["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

        return new_expense

    def add_gain(self, amount, currency_code, account_id, exchange_rate=None, stream_name=None, payer_name=None,
                    project_name=None, description=None,
                    timestamp=None):
        """Adds a gain to DB."""
        # 1. Resolve Master Data
        stream = self._get_or_create_dimension(Stream, stream_name) if stream_name else None
        payer = self._get_or_create_dimension(Payer, payer_name) if payer_name else None
        project = self._get_or_create_dimension(Project, project_name) if project_name else None

        # 2. Resolve Account
        account = self.session.query(Account).filter_by(id=account_id).first()

        # 3. FX Logic
        if not exchange_rate:
            fx_rate = None
            if currency_code != "EUR":
                rate_entry = (self.session.query(ExchangeRate)
                              .filter_by(currency_code=currency_code)
                              .order_by(ExchangeRate.timestamp.desc())
                              .first())
                if not rate_entry:
                    raise ValueError(f"No exchange rate found for {currency_code}. Please seed rates.")
                fx_rate = rate_entry.fx_multiplier
        else:
            fx_rate = exchange_rate

        # 4. Create Gain Object
        new_gain = Gain(
            amount=amount,
            currency_code=currency_code,
            fx_rate=fx_rate,
            stream_id=stream.id if stream else None,
            payer_id=payer.id if payer else None,
            account_id=account_id,
            project_id=project.id if project else None,
            description=description,
            timestamp=timestamp or datetime.datetime.now()
        )
        new_gain = calculate_conversion(new_gain)

        # Add the 'raw' amount from the account balance
        account.balance = float(Decimal(str(account.balance)) + Decimal(str(amount)))

        try:
            self.session.add(new_gain)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise e

        # Update the Memory after a successful save
        self.last_used["currency"] = currency_code
        self.last_used["acc"] = account.name
        self.last_used["project"] = project_name
        # Store just the date part
        if timestamp and hasattr(timestamp, 'strftime'):
            self.last_used["date"] = timestamp.strftime("%Y-%m-%d")
        else:
            self.last_used["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

        return new_gain

    def check_for_duplicate(self, amount, entity_name, date_str, transaction_type="expense"):
        """Returns True if a transaction with same amount, entity (vendor/payer), and date exists."""
        target_date = date_str.split(" ")[0]

        if transaction_type == "expense":
            exists = self.session.query(Expense).join(Vendor).filter(
                Expense.amount == amount,
                Vendor.name == entity_name,
                func.date(Expense.timestamp) == target_date
            ).first()

        elif transaction_type == "gain":
            exists = self.session.query(Gain).join(Payer).filter(
                Gain.amount == amount,
                Payer.name == entity_name,
                func.date(Gain.timestamp) == target_date
            ).first()

        else:
            exists = None

        return exists is not None

    def get_historical_fx_rate(self, currency_code, target_date):
        """
        Finds the closest exchange rate for the given currency
        that was recorded ON or BEFORE the target_date.
        """
        rate_entry = (self.session.query(ExchangeRate)
                      .filter(ExchangeRate.currency_code == currency_code)
                      .filter(ExchangeRate.timestamp <= target_date)
                      .order_by(ExchangeRate.timestamp.desc())
                      .first())
        if rate_entry:
            return rate_entry.fx_multiplier, rate_entry.timestamp

        return None

    def get_net_worth(self):
        """Calculates total balance of all accounts, converted to EUR."""
        accounts = self.session.query(Account).all()
        total_eur = 0.0

        for acc in accounts:
            if acc.currency_code == "EUR":
                total_eur += float(Decimal(str(acc.balance)))
            else:
                # Get the latest rate
                rate = (self.session.query(ExchangeRate)
                        .filter(ExchangeRate.currency_code == acc.currency_code)
                        .order_by(ExchangeRate.timestamp.desc())
                        .first())

                multiplier = rate.fx_multiplier if rate else 1.0
                total_eur += float(Decimal(str(acc.balance))) / multiplier

        return total_eur

    def transfer_funds(self, origin_id, destination_id, amount_orig, amount_dest, desc, ts=None):
        """Transfers funds between two accounts."""
        try:
            origin = self.session.query(Account).get(origin_id)
            destination = self.session.query(Account).get(destination_id)

            prefix = f"{origin.currency_code} -> {destination.currency_code}{' | ' if desc else ''}"
            full_desc = prefix + desc

            new_transfer = Transfer(
                origin_account_id=origin_id,
                destination_account_id=destination_id,
                amount_origin=amount_orig,
                amount_destination=amount_dest,
                description=full_desc,
                timestamp=ts or datetime.datetime.now()
            )

            # Update balances
            origin.balance = float(Decimal(str(origin.balance)) - Decimal(str(amount_orig)))
            destination.balance = float(Decimal(str(destination.balance)) + Decimal(str(amount_dest)))

            self.session.add(new_transfer)
            self.session.commit()
            return new_transfer
        except Exception as e:
            self.session.rollback()
            raise e

