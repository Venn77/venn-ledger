from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import (
    create_engine, event, Column, Integer, Float, String,
    Boolean, DateTime, func, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import DB_PATH


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

def calculate_conversion(item, is_base_currency=False, quotation_method="divide", decimals=2):
    """Returns converted amount with two decimals."""
    precision_string = "0." + ("0" * decimals) if decimals > 0 else "0"
    if is_base_currency or not getattr(item, 'fx_rate', None):
        val = Decimal(str(item.amount)).quantize(Decimal(precision_string), rounding=ROUND_HALF_UP)
        item.converted_amount = float(val)
        item.fx_rate = None
    else:
        if quotation_method == "multiply":
            raw_val = Decimal(str(item.amount)) * Decimal(str(item.fx_rate))
        else:
            raw_val = Decimal(str(item.amount)) / Decimal(str(item.fx_rate))
        val = raw_val.quantize(Decimal(precision_string), rounding=ROUND_HALF_UP)
        item.converted_amount = float(val)
    return item

class Currency(Base):
    __tablename__ = 'currencies'
    code = Column(String(10), primary_key=True, comment="The currency, e.g., EUR")
    name = Column(String(50), nullable=False, comment="e.g., Euro, United States Dollar, etc.")
    symbol = Column(String(5), default="", comment="e.g., €, $, £")
    is_base = Column(Boolean, default=False, comment="True if this is the user's primary/home currency")
    quotation_method = Column(String(10), default="divide", comment="For conversion purposes - 'multiply' or 'divide'")
    decimals = Column(Integer, default=2, comment="Number of decimals: 0 for JPY, 2 for USD, etc.")
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
    fx_multiplier = Column(Float, default=1.0, comment="Conversion rate if currency is not the base currency")
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
    fx_rate = Column(Float, comment="Conversion rate if currency is not the base currency")
    converted_amount = Column(Float, comment="Converted amount if currency is not base currency")
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
                f"BASE={self.converted_amount:.{self.currency.decimals}f}, vendor='{self.vendor_id}', category='{self.category_id}')>")

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
    fx_rate = Column(Float, comment="Conversion rate if currency is not the base currency")
    converted_amount = Column(Float, comment="Converted amount if currency is not the base currency")
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
                f"BASE={self.converted_amount:.{self.currency.decimals}f}, payer='{self.payer_id}', stream='{self.stream_id}')>")

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


Base.metadata.create_all(engine)


