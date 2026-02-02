from models import (
    Category, Vendor, Account, PaymentMethod,
    Project, Expense, ExchangeRate, Currency
)
import datetime


class TransactionManager:
    def __init__(self, session):
        self.session = session

    def _get_or_create_dimension(self, model, name):
        """
        Handles the 'Master Data' lookup.
        If the item exists but is inactive, it reactivates it.
        """
        item = self.session.query(model).filter_by(name=name).first()
        if item:
            if not item.active_bool:
                item.active_bool = True  # Reactivate if used again
            return item

        new_item = model(name=name)
        self.session.add(new_item)
        self.session.flush()  # Populate the ID
        return new_item

    def add_expense(self, amount, currency_code, category_name, vendor_name,
                    payment_method_name, project_name=None, description=None,
                    timestamp=None):

        # 1. Resolve Master Data
        category = self._get_or_create_dimension(Category, category_name)
        vendor = self._get_or_create_dimension(Vendor, vendor_name)
        project = self._get_or_create_dimension(Project, project_name) if project_name else None

        # 2. Resolve Payment Method & Account
        # We assume the PaymentMethod already exists for manual entry
        pm = self.session.query(PaymentMethod).filter_by(name=payment_method_name).first()

        if not pm:
            raise ValueError(f"Payment Method '{payment_method_name}' not found. Please create it first.")

        account = pm.account

        # 3. Currency & FX Logic
        fx_rate = None
        if currency_code != "EUR":
            rate_entry = (self.session.query(ExchangeRate)
                          .filter_by(currency_code=currency_code)
                          .order_by(ExchangeRate.timestamp.desc())
                          .first())
            if not rate_entry:
                raise ValueError(f"No exchange rate found for {currency_code}. Please seed rates.")
            fx_rate = rate_entry.fx_multiplier

        # 4. Create Expense Object
        new_expense = Expense(
            amount=amount,
            currency_code=currency_code,
            fx_rate=fx_rate,
            category_id=category.id,
            vendor_id=vendor.id,
            payment_method_id=pm.id,
            project_id=project.id if project else None,
            description=description,
            timestamp=timestamp or datetime.datetime.now()
        )
        new_expense.calculate_conversion()

        # 5. THE CRITICAL STEP: Liquidity Update
        # Subtract the 'raw' amount from the account balance
        account.balance -= amount

        try:
            self.session.add(new_expense)
            self.session.commit()
            return new_expense
        except Exception as e:
            self.session.rollback()
            raise e