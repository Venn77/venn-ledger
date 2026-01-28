from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, func, ForeignKey
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship, validates, sessionmaker
import datetime, enum


engine = create_engine('sqlite:///tracker.db', echo=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()
session = Session()


class Currency(Base):
    __tablename__ = 'currencies'
    code = Column(String(3), primary_key=True, comment="The currency, e.g., EUR")
    name = Column(String(50), nullable=False, comment="e.g., Euro, United States Dollar, etc.")
    expenses = relationship("Expense", back_populates="currency")
    exchange_rate = relationship("ExchangeRate", back_populates="currencies")

class ExchangeRate(Base):
    __tablename__ = 'exchange_rates'
    currency_code = Column(String(3), ForeignKey('currencies.code'), primary_key=True, nullable=False)
    fx_multiplier = Column(Float, default=1.0, comment="Conversion rate if currency is not EUR")
    currencies = relationship("Currency", back_populates="exchange_rate")


class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False,
                  comment="e.g., 420, Rent, Gifts, Groceries, Transportation, Vacation, Subscription, Refreshment, or Medical")
    expenses = relationship("Expense", back_populates="category")

class Vendor(Base):
    __tablename__ = 'vendors'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False, comment="e.g., Mercadona, Pepephone, etc.")
    expenses = relationship("Expense", back_populates="vendor")

class PaymentMethod(Base):
    __tablename__ = 'payment_methods'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False,
                  comment="The payment method, e.g., LaLiga, Santander Debit, Wise, Revolut, or MercadoPago")
    expenses = relationship("Expense", back_populates="payment_method")

class Expense(Base):
    __tablename__ = 'expenses'
    # Foreign Keys
    currency_code = Column(String(3), ForeignKey('currencies.code'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    payment_method_id = Column(Integer, ForeignKey('payment_methods.id'), nullable=False)
    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False, comment="The numerical cost, e.g., 15.50")
    fx_rate = Column(Float, comment="Conversion rate if currency is not EUR")
    converted_amount = Column(Float, comment="Converted amount if currency is not EUR")
    split_boolean = Column(Boolean, default=False, comment="If the expense item will be paid in instalments")
    split_num_instalments = Column(Integer, comment="The number of instalments paid if split_boolean is True")
    description = Column(String, comment="A brief summary of what was bought")
    timestamp = Column(DateTime, server_default=func.now(), comment="UTC timestamp of entry")
    # Relationships
    currency = relationship("Currency", back_populates="expenses")
    category = relationship("Category", back_populates="expenses")
    vendor = relationship("Vendor", back_populates="expenses")
    payment_method = relationship("PaymentMethod", back_populates="expenses")

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
    # new_currency = Currency(code="EUR", name="Euro")
    # session.add(new_currency)
    # new_currency2 = Currency(code="ARS", name="Argentina Peso")
    # session.add(new_currency2)
    # new_fx_rate = ExchangeRate(currency_code=new_currency2.code, fx_multiplier=1750.0)
    # session.add(new_fx_rate)
    # new_category = Category(name="420")
    # session.add(new_category)
    # new_vendor = Vendor(name="Planta Santa")
    # session.add(new_vendor)
    # new_payment_method = PaymentMethod(name="Cash")
    # session.add(new_payment_method)
    # session.commit()
    # cat = session.query(Category).filter_by(name="420").first()
    # ven = session.query(Vendor).filter_by(name="Planta Santa").first()
    # pay = session.query(PaymentMethod).filter_by(name="Cash").first()
    # rate_entry = session.query(ExchangeRate).filter_by(currency_code="ARS").first()
    # new_expense = Expense(amount=17500.00, currency_code="ARS", fx_rate=rate_entry.fx_multiplier,
    #                       category_id=cat.id, vendor_id=ven.id,
    #                       payment_method_id=pay.id, description="Fasito", timestamp=datetime.datetime.now())
    # new_expense.calculate_conversion()
    # session.add(new_expense)
    # session.commit()