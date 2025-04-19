from sqlalchemy import create_engine
from models import Base

# Создание SQLite базы данных
engine = create_engine('sqlite:///finance_bot.db')

# Создание всех таблиц
Base.metadata.create_all(engine)

print("База данных и таблицы успешно созданы!")
