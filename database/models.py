import os
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    Boolean, DateTime, func, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "tracker.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()


def calculate_conversion(item):
    """Returns converted amount in EUR with two decimals."""
    if item.currency_code == "EUR":
        # Convert to decimal, round, prep for DB
        val = Decimal(str(item.amount)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        item.converted_amount = float(val)
        item.fx_rate = None
    elif item.fx_rate:
        # Divide as Decimal for precision
        raw_val = Decimal(str(item.amount)) / Decimal(str(item.fx_rate))
        val = raw_val.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        item.converted_amount = float(val)
    return item

class Currency(Base):
    __tablename__ = 'currencies'
    code = Column(String(3), primary_key=True, comment="The currency, e.g., EUR")
    name = Column(String(50), nullable=False, comment="e.g., Euro, United States Dollar, etc.")
    active_bool = Column(Boolean, default=True, comment="If the currency is active (so it is selectable in-app)")
    # Relationships
    accounts = relationship("Account", back_populates="currency")
    expenses = relationship("Expense", back_populates="currency")
    gains = relationship("Gain", back_populates="currency")
    exchange_rate = relationship("ExchangeRate", back_populates="currencies", cascade="all, delete, delete-orphan")

    def __repr__(self):
        return f"<Currency(code='{self.code}', name='{self.name}', active_bool='{self.active_bool}')>"

class ExchangeRate(Base):
    __tablename__ = 'exchange_rates'
    # Foreign Keys
    currency_code = Column(String(3), ForeignKey('currencies.code'), nullable=False)
    id = Column(Integer, primary_key=True)
    fx_multiplier = Column(Float, default=1.0, comment="Conversion rate if currency is not EUR")
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), comment="UTC timestamp of entry")
    # Relationships
    currencies = relationship("Currency", back_populates="exchange_rate")

    __table_args__ = (
        UniqueConstraint('currency_code', 'timestamp',name='_currency_timestamp_uc'),
                      )

    def __repr__(self):
        return f"<ExchangeRate(code='{self.currency_code}', rate={self.fx_multiplier} at {self.timestamp})>"

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False,
                  comment="e.g., 420, Rent, Gifts, Groceries, Transportation, Vacation, Subscription, Refreshment, or Medical")
    active_bool = Column(Boolean, default=True, comment="If the category is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="category")

    def __repr__(self):
        return f"<Category(name='{self.name}', active_bool='{self.active_bool}')>"

class Stream(Base):
    __tablename__ = 'streams'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False,
                  comment="e.g., Salary, Reimbursement or Unemployment")
    active_bool = Column(Boolean, default=True, comment="If the category is active (so it is selectable in-app)")
    # Relationships
    gains = relationship("Gain", back_populates="stream")

    def __repr__(self):
        return f"<Stream(name='{self.name}', active_bool='{self.active_bool}')>"

class Vendor(Base):
    __tablename__ = 'vendors'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, comment="e.g., Mercadona, Pepephone, etc.")
    active_bool = Column(Boolean, default=True, comment="If the vendor is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor(name='{self.name}', active_bool='{self.active_bool}')>"

class Payer(Base):
    __tablename__ = 'payers'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, comment="e.g., DOMO, SEPE, Amazon, etc.")
    active_bool = Column(Boolean, default=True, comment="If the payer is active (so it is selectable in-app)")
    # Relationships
    gains = relationship("Gain", back_populates="payer")

    def __repr__(self):
        return f"<Payer(name='{self.name}', active_bool='{self.active_bool}')>"

class Account(Base):
    __tablename__ = 'accounts'
    #Foreign Keys
    currency_code = Column(String(3), ForeignKey('currencies.code'), nullable=False)
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, comment="The name of the account")
    description = Column(String, comment="A brief summary of the account's purpose")
    balance = Column(Float, default=0, comment="The balance of the account")
    initial_balance = Column(Float, default=0, comment="The initial balance of the account")
    active_bool = Column(Boolean, default=True, comment="If the account is active (so it is selectable in-app)")
    # Relationships
    currency = relationship("Currency", back_populates="accounts")
    payment_methods = relationship("PaymentMethod", back_populates="account")
    gains = relationship("Gain", back_populates="account")

    def __repr__(self):
        return f"<Account(name='{self.name}', balance='{self.balance}', active_bool='{self.active_bool}')>"

class PaymentMethod(Base):
    __tablename__ = 'payment_methods'
    #Foreign Keys
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False,
                  comment="The payment method, e.g., LaLiga, Santander Debit, Wise, Revolut, or MercadoPago")
    active_bool = Column(Boolean, default=True, comment="If the payment method is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="payment_method")
    account = relationship("Account", back_populates="payment_methods")

    def __repr__(self):
        return f"<PaymentMethod(name='{self.name}', active_bool='{self.active_bool}')>"

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, comment="The overarching project or plan to which the expenses will be linked - good for trends analysis")
    description = Column(String, comment="A brief summary of the project")
    active_bool = Column(Boolean, default=True, comment="If the project is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="project")
    gains = relationship("Gain", back_populates="project")

    def __repr__(self):
        return f"<Project(name='{self.name}', active_bool='{self.active_bool}')>"

class Expense(Base):
    __tablename__ = 'expenses'
    # Foreign Keys
    currency_code = Column(String(3), ForeignKey('currencies.code'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    payment_method_id = Column(Integer, ForeignKey('payment_methods.id'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'))
    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False, comment="The numerical cost, e.g., 15.50")
    fx_rate = Column(Float, comment="Conversion rate if currency is not EUR")
    converted_amount = Column(Float, comment="Converted amount if currency is not EUR")
    split_bool = Column(Boolean, default=False, comment="If the expense item will be paid in instalments")
    split_num_instalments = Column(Integer, comment="The number of instalments paid if split_boolean is True")
    description = Column(String, comment="A brief summary of what was bought")
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), comment="UTC timestamp of entry")
    # Relationships
    currency = relationship("Currency", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")
    vendor = relationship("Vendor", back_populates="expenses")
    payment_method = relationship("PaymentMethod", back_populates="expenses")
    project = relationship("Project", back_populates="expenses")

    def __repr__(self):
        return (f"<Expense(amount={self.amount} {self.currency_code}, "
                f"EUR={self.converted_amount:.2f}, vendor='{self.vendor_id}', category='{self.category_id}')>")

class Gain(Base):
    __tablename__ = 'gains'
    # Foreign Keys
    currency_code = Column(String(3), ForeignKey('currencies.code'), nullable=False)
    stream_id = Column(Integer, ForeignKey('streams.id'))
    payer_id = Column(Integer, ForeignKey('payers.id'))
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'))
    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False, comment="The numerical value, e.g., 1250.66")
    fx_rate = Column(Float, comment="Conversion rate if currency is not EUR")
    converted_amount = Column(Float, comment="Converted amount if currency is not EUR")
    split_bool = Column(Boolean, default=False, comment="If the gain item will be received in instalments")
    split_num_instalments = Column(Integer, comment="The number of instalments paid if split_boolean is True")
    description = Column(String, comment="A brief summary of what it was about")
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), comment="UTC timestamp of entry")
    # Relationships
    currency = relationship("Currency", back_populates="gains")
    stream = relationship("Stream", back_populates="gains")
    payer = relationship("Payer", back_populates="gains")
    account = relationship("Account", back_populates="gains")
    project = relationship("Project", back_populates="gains")

    def __repr__(self):
        return (f"<Gain(amount={self.amount} {self.currency_code}, "
                f"EUR={self.converted_amount:.2f}, payer='{self.payer_id}', stream='{self.stream_id}')>")

class Transfer(Base):
    __tablename__ = 'transfers'
    id = Column(Integer, primary_key=True)
    # Accounts
    origin_account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    destination_account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    # Amounts
    amount_origin = Column(Float, nullable=False, comment="Amount leaving the origin account")
    amount_destination = Column(Float, nullable=False, comment="Amount entering the destination account")

    description = Column(String)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    # Relationships
    origin_account = relationship("Account", foreign_keys=[origin_account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])

    def __repr__(self):
        return f"<Transfer({self.amount_origin} -> {self.amount_destination})>"


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    print("Database and tables created successfully!")
    # Example session for standalone script:
    # local_session = Session()
    # new_currency = Currency(code="EUR", name="Euro")
    # local_session.add(new_currency)
    # new_currency2 = Currency(code="ARS", name="Argentina Peso")
    # local_session.add(new_currency2)
    # new_fx_rate = ExchangeRate(currency_code=new_currency2.code, fx_multiplier=1850.0, timestamp=datetime.datetime.now())
    # local_session.add(new_fx_rate)
    # local_session.commit()
    # new_fx_rate2 = ExchangeRate(currency_code=new_currency2.code, fx_multiplier=1750.0,
    #                            timestamp=datetime.datetime.now())
    # local_session.add(new_fx_rate2)
    # new_category = Category(name="420")
    # local_session.add(new_category)
    # new_vendor = Vendor(name="Planta Santa")
    # local_session.add(new_vendor)
    # new_accounts = (
    #     Account(currency_code=new_currency.code, name="Santander ES", description="Main account", balance=1000),
    #     Account(currency_code=new_currency.code, name="Cash (EUR)", description="Cash in EUR", balance=100)
    # )
    # local_session.add_all(new_accounts)
    # local_session.commit()
    # new_payment_methods = (
    #     PaymentMethod(name="Santander Debit", account_id=new_accounts[0].id),
    #     PaymentMethod(name="Santander Bizum", account_id=new_accounts[0].id),
    #     PaymentMethod(name="Cash (EUR)", account_id=new_accounts[1].id)
    # )
    # local_session.add_all(new_payment_methods)
    # local_session.commit()
    # new_projects = (
    #     Project(name="Japan 2025", description="September/October trip with gf"),
    #     Project(name="Italy 2025", description="December trip with gf")
    # )
    # local_session.add_all(new_projects)
    # local_session.commit()
    # cat = local_session.query(Category).filter_by(name="420").first()
    # ven = local_session.query(Vendor).filter_by(name="Planta Santa").first()
    # pay = local_session.query(PaymentMethod).filter_by(name="Cash (EUR)").first()
    # rate_entry = (
    #     local_session.query(ExchangeRate).filter_by(currency_code="ARS")
    #                                .order_by(ExchangeRate.timestamp.desc())
    #                                .first()
    #               )
    # new_expense = Expense(amount=17500.00, currency_code="ARS", fx_rate=rate_entry.fx_multiplier,
    #                       category_id=cat.id, vendor_id=ven.id,
    #                       payment_method_id=pay.id, description="Fasito", timestamp=datetime.datetime.now())
    # new_expense.calculate_conversion()
    # local_session.add(new_expense)
    # local_session.commit()


