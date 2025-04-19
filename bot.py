import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from database import (
    SessionLocal,
    create_user_if_not_exists,
    get_user_by_telegram_id,
    get_categories_by_user,
    get_monthly_expense_report

)
from models import Category

from models import Expense, Category
from decimal import Decimal
from datetime import date
from datetime import datetime, time as dtime, timedelta

# 🔐 Вставь сюда свой Telegram Bot Token
API_TOKEN = ""

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Категории")],
        [KeyboardButton(text="Добавить расход"), KeyboardButton(text="Добавить категорию")],
        [KeyboardButton(text="Отчет")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выбери действие ↓"
)

# FSM состояния
class CategoryStates(StatesGroup):
    waiting_for_category_name = State()

class ExpenseStates(StatesGroup):
    waiting_for_category_choice = State()
    waiting_for_amount_and_description = State()




async def send_daily_reminders():
    while True:
        now = datetime.now()
        target_time = datetime.combine(now.date(), dtime(20, 0))  # 20:00
        if now >= target_time:
            target_time += timedelta(days=1)

        # Сколько ждать до 20:00
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        # Отправляем напоминания
        db = SessionLocal()
        try:
            users = db.query(get_user_by_telegram_id.__annotations__["db"].class_).all()
            for user in users:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text="💬 Не забудь внести свои расходы за сегодня!"
                    )
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}")
        finally:
            db.close()

# Команда /start
@dp.message(CommandStart())
async def handle_start(message: Message):
    db = SessionLocal()
    try:
        user = create_user_if_not_exists(
            db=db,
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )
        await message.answer("👋 Привет! Ты зарегистрирован в системе учёта расходов.", reply_markup=main_menu)
    except Exception as e:
        logging.exception("Ошибка при регистрации пользователя:")
        await message.answer("Произошла ошибка. Попробуй позже.")
    finally:
        db.close()


# Кнопка "Категории"
@dp.message(F.text == "Категории")
async def handle_categories_button(message: Message):
    await handle_categories(message)


# Функция показа категорий
async def handle_categories(message: Message):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Ты ещё не зарегистрирован. Напиши /start.")
            return

        categories = get_categories_by_user(db, user.id)
        if not categories:
            await message.answer("🗂️ У тебя пока нет категорий расходов.")
        else:
            category_list = "\n".join(f"• {c.name}" for c in categories)
            await message.answer(f"🗂️ Твои категории:\n{category_list}")
    except Exception as e:
        logging.exception("Ошибка при получении категорий:")
        await message.answer("Произошла ошибка при получении категорий.")
    finally:
        db.close()


# Кнопка "Добавить категорию"
@dp.message(F.text == "Добавить категорию")
async def start_adding_category(message: Message, state: FSMContext):
    await message.answer("🆕 Введи название новой категории:")
    await state.set_state(CategoryStates.waiting_for_category_name)



@dp.message(F.text == "Добавить расход")
async def handle_add_expense(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала напиши /start.")
            return

        categories = get_categories_by_user(db, user.id)
        if not categories:
            await message.answer("У тебя пока нет категорий. Добавь хотя бы одну.")
            return

        # Кнопки с категориями
        buttons = [KeyboardButton(text=cat.name) for cat in categories]
        row_width = 2
        rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
        category_keyboard = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

        await message.answer("💸 Из какой категории трата?", reply_markup=category_keyboard)
        await state.set_state(ExpenseStates.waiting_for_category_choice)

    finally:
        db.close()

@dp.message(ExpenseStates.waiting_for_category_choice)
async def handle_category_chosen(message: Message, state: FSMContext):
    selected_category = message.text.strip()
    await state.update_data(selected_category=selected_category)

    await message.answer("✍️ Введи сумму траты (только число):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ExpenseStates.waiting_for_amount_and_description)

@dp.message(ExpenseStates.waiting_for_amount_and_description)
async def handle_amount_only(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала напиши /start.")
            return

        data = await state.get_data()
        category_name = data.get("selected_category")

        # Найдём категорию
        category = db.query(Category).filter_by(user_id=user.id, name=category_name).first()
        if not category:
            await message.answer("Категория не найдена. Попробуй заново.")
            await state.clear()
            return

        try:
            amount = Decimal(message.text.strip().replace(",", "."))
        except:
            await message.answer("❗ Введи только сумму, например: `450.50`")
            return

        expense = Expense(
            user_id=user.id,
            category_id=category.id,
            amount=amount,
            spent_at=date.today()
        )

        db.add(expense)
        db.commit()

        await message.answer(
            f"✅ Расход {amount}₽ в категории \"{category_name}\" добавлен!",
            reply_markup=main_menu
        )

    except Exception as e:
        logging.exception("Ошибка при добавлении расхода:")
        await message.answer("Произошла ошибка.")
    finally:
        db.close()
        await state.clear()


# Обработка ввода категории
@dp.message(CategoryStates.waiting_for_category_name)
async def receive_category_name(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        category_name = message.text.strip()

        # Проверим, есть ли уже такая категория
        existing = db.query(Category).filter_by(user_id=user.id, name=category_name).first()
        if existing:
            await message.answer("⚠️ Такая категория уже существует.")
        else:
            category = Category(user_id=user.id, name=category_name)
            db.add(category)
            db.commit()
            await message.answer(f"✅ Категория \"{category_name}\" добавлена!", reply_markup=main_menu)

    except Exception as e:
        logging.exception("Ошибка при добавлении категории:")
        await message.answer("Произошла ошибка при добавлении категории.")
    finally:
        db.close()
        await state.clear()




@dp.message(F.text == "Отчет")
async def handle_report(message: Message):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала напиши /start.")
            return

        report = get_monthly_expense_report(db, user.id)

        if not report:
            await message.answer("📭 В этом месяце у тебя ещё нет расходов.")
            return

        total = sum([row[1] for row in report])
        lines = [f"📊 Расходы за {date.today():%B}:\n"]
        for name, amount in report:
            lines.append(f"• {name}: {float(amount):,.2f} ₽")
        lines.append(f"\n💰 Всего: {float(total):,.2f} ₽")

        await message.answer("\n".join(lines))
    except Exception as e:
        logging.exception("Ошибка при формировании отчета:")
        await message.answer("Произошла ошибка при формировании отчёта.")
    finally:
        db.close()



# Запуск бота
async def main():
    reminder_task = asyncio.create_task(send_daily_reminders())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
