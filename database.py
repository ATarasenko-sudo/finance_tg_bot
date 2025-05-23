from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, User, Category, Expense
from sqlalchemy.exc import NoResultFound
from sqlalchemy import func
from datetime import date
# Путь к SQLite-базе
DATABASE_URL = "sqlite:///finance_bot.db"

# Создание движка базы данных
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Создание сессии
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


# Получение пользователя по Telegram ID
def get_user_by_telegram_id(db, telegram_id: int):
    return db.query(User).filter(User.telegram_id == telegram_id).first()


# Создание пользователя, если его нет
import hashlib

def hash_username(username: str) -> str:
    if not username:
        return None
    return hashlib.sha256(username.encode()).hexdigest()

def create_user_if_not_exists(db, telegram_id: int, username: str = None):
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        hashed_name = hash_username(username)
        user = User(
            telegram_id=telegram_id,
            username=hashed_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_categories_by_user(db, user_id: int):
    return db.query(Category).filter(Category.user_id == user_id).order_by(Category.name).all()

def get_monthly_expense_report(db, user_id: int):
    today = date.today()
    first_day = date(today.year, today.month, 1)

    # Группируем по категориям
    results = (
        db.query(Category.name, func.sum(Expense.amount))
        .join(Expense, Expense.category_id == Category.id)
        .filter(
            Expense.user_id == user_id,
            Expense.spent_at >= first_day
        )
        .group_by(Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    return results


from models import Income

def add_income(db, user_id: int, category_id: int, amount: float):
    income = Income(
        user_id=user_id,
        category_id=category_id,
        amount=amount
    )
    db.add(income)
    db.commit()
    db.refresh(income)
    return income

def get_incomes_by_user(db, user_id: int):
    return db.query(Income).filter(Income.user_id == user_id).order_by(Income.received_at.desc()).all()


def get_monthly_income_report(db, user_id: int):
    today = date.today()
    first_day = date(today.year, today.month, 1)

    results = (
        db.query(Category.name, func.sum(Income.amount))
        .join(Income, Income.category_id == Category.id)
        .filter(
            Income.user_id == user_id,
            Income.received_at >= first_day
        )
        .group_by(Category.name)
        .order_by(func.sum(Income.amount).desc())
        .all()
    )

    return results
