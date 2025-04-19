from sqlalchemy import (
    Column, Integer, BigInteger, String, Numeric, Date, DateTime, ForeignKey, func
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now())

    categories = relationship('Category', cascade='all, delete-orphan', backref='user')
    expenses = relationship('Expense', cascade='all, delete-orphan', backref='user')


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    name = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    expenses = relationship('Expense', cascade='all, delete-orphan', backref='category')


class Expense(Base):
    __tablename__ = 'expenses'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    category_id = Column(Integer, ForeignKey('categories.id', ondelete='CASCADE'))
    amount = Column(Numeric(10, 2))
    spent_at = Column(Date, default=func.current_date())