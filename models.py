from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, func, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship, validates, sessionmaker
import datetime, enum


engine = create_engine('sqlite:///tracker.db', echo=False)
Session = sessionmaker(bind=engine)
Base = declarative_base()
session = Session()


class Currency(Base):
    __tablename__ = 'currencies'
    code = Column(String(3), primary_key=True, comment="The currency, e.g., EUR")
    name = Column(String(50), nullable=False, comment="e.g., Euro, United States Dollar, etc.")
    active = Column(Boolean, default=True, comment="If the currency is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="currency")
    exchange_rate = relationship("ExchangeRate", back_populates="currencies")

    def __repr__(self):
        return f"<Currency(code='{self.code}', name='{self.name}', active='{self.active}')>"

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
    active = Column(Boolean, default=True, comment="If the category is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="category")

    def __repr__(self):
        return f"<Category(name='{self.name}', active='{self.active}')>"

class Vendor(Base):
    __tablename__ = 'vendors'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, comment="e.g., Mercadona, Pepephone, etc.")
    active = Column(Boolean, default=True, comment="If the vendor is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="vendor")

    def __repr__(self):
        return f"<Vendor(name='{self.name}', active='{self.active}')>"

class PaymentMethod(Base):
    __tablename__ = 'payment_methods'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False,
                  comment="The payment method, e.g., LaLiga, Santander Debit, Wise, Revolut, or MercadoPago")
    active = Column(Boolean, default=True, comment="If the payment method is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="payment_method")

    def __repr__(self):
        return f"<PaymentMethod(name='{self.name}', active='{self.active}')>"

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False, comment="The overarching project or plan to which the expenses will be linked - good for trends analysis")
    description = Column(String, comment="A brief summary of the project")
    active = Column(Boolean, default=True, comment="If the project is active (so it is selectable in-app)")
    # Relationships
    expenses = relationship("Expense", back_populates="project")

    def __repr__(self):
        return f"<Project(name='{self.name}', active='{self.active}')>"

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
    split_boolean = Column(Boolean, default=False, comment="If the expense item will be paid in instalments")
    split_num_instalments = Column(Integer, comment="The number of instalments paid if split_boolean is True")
    description = Column(String, comment="A brief summary of what was bought")
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), comment="UTC timestamp of entry")
    # Relationships
    currency = relationship("Currency", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")
    vendor = relationship("Vendor", back_populates="expenses")
    payment_method = relationship("PaymentMethod", back_populates="expenses")
    project = relationship("Project", back_populates="expenses")

    def calculate_conversion(self):
        if self.currency_code == "EUR":
            self.converted_amount = self.amount
            self.fx_rate = None
        elif self.fx_rate:
            self.converted_amount = self.amount / self.fx_rate

    def __repr__(self):
        return f"<Expense(amount={self.amount}, category='{self.category_id}')>"


if __name__ == '__main__':
    Base.metadata.create_all(engine)
    print("Database and tables created successfully!")
    new_currency = Currency(code="EUR", name="Euro")
    session.add(new_currency)
    new_currency2 = Currency(code="ARS", name="Argentina Peso")
    session.add(new_currency2)
    new_fx_rate = ExchangeRate(currency_code=new_currency2.code, fx_multiplier=1850.0, timestamp=datetime.datetime.now())
    session.add(new_fx_rate)
    session.commit()
    new_fx_rate2 = ExchangeRate(currency_code=new_currency2.code, fx_multiplier=1750.0,
                               timestamp=datetime.datetime.now())
    session.add(new_fx_rate2)
    new_category = Category(name="420")
    session.add(new_category)
    new_vendor = Vendor(name="Planta Santa")
    session.add(new_vendor)
    new_payment_method = PaymentMethod(name="Cash")
    session.add(new_payment_method)
    session.commit()
    new_projects = (
        Project(name="Japan 2025", description="September/October trip with gf"),
        Project(name="Italy 2025", description="December trip with gf")
    )
    session.add_all(new_projects)
    session.commit()
    cat = session.query(Category).filter_by(name="420").first()
    ven = session.query(Vendor).filter_by(name="Planta Santa").first()
    pay = session.query(PaymentMethod).filter_by(name="Cash").first()
    rate_entry = (
        session.query(ExchangeRate).filter_by(currency_code="ARS")
                                   .order_by(ExchangeRate.timestamp.desc())
                                   .first()
                  )
    new_expense = Expense(amount=17500.00, currency_code="ARS", fx_rate=rate_entry.fx_multiplier,
                          category_id=cat.id, vendor_id=ven.id,
                          payment_method_id=pay.id, description="Fasito", timestamp=datetime.datetime.now())
    new_expense.calculate_conversion()
    session.add(new_expense)
    session.commit()