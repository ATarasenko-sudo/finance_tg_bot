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
    get_monthly_expense_report,
    get_monthly_income_report


)
from models import Category

from models import Expense, Category
from decimal import Decimal
from datetime import date
from datetime import datetime, time as dtime, timedelta


from database import add_income

# 🔐 Вставь сюда свой Telegram Bot Token
API_TOKEN = 

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Категории расходов"), KeyboardButton(text="Категории доходов")],
        [KeyboardButton(text="Добавить расход"), KeyboardButton(text="Добавить доход")],
        [KeyboardButton(text="Отчет")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выбери действие ↓"
)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅ Назад")]],
    resize_keyboard=True
)


expense_categories_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить категорию расхода")],
        [KeyboardButton(text="🗑 Удалить категорию расхода")],
        [KeyboardButton(text="✏️ Редактировать категорию расхода")],
        [KeyboardButton(text="⬅ Назад")],
    ],
    resize_keyboard=True
)

income_categories_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить категорию дохода")],
        [KeyboardButton(text="🗑 Удалить категорию дохода")],
        [KeyboardButton(text="✏️ Редактировать категорию дохода")],
        [KeyboardButton(text="⬅ Назад")],
    ],
    resize_keyboard=True
)

# FSM состояния
class CategoryStates(StatesGroup):
    waiting_for_category_name = State()

class ExpenseStates(StatesGroup):
    waiting_for_category_choice = State()
    waiting_for_amount_and_description = State()

class IncomeStates(StatesGroup):
    waiting_for_income_category_choice = State()
    waiting_for_income_amount = State()


class ExpenseCategoryManageStates(StatesGroup):
    waiting_for_expense_category_name = State()
    waiting_for_expense_category_to_delete = State()
    waiting_for_expense_category_to_edit = State()  
    waiting_for_new_expense_category_name = State()  


class IncomeCategoryManageStates(StatesGroup):
    waiting_for_income_category_name = State()
    waiting_for_income_category_to_delete = State()
    waiting_for_income_category_to_edit = State()
    waiting_for_new_income_category_name = State()

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
        await message.answer("👋 Привет! Ты зарегистрирован в системе учёта расходов. \n \tЯ твой личный ассистент, с помощью меня ты можешь фиксировать все свои расходы, для начала тебе надо добавить хотя бы одну категорию, чтобы в дальнейшем записывать в неё соответсвующие траты!", reply_markup=main_menu)
    except Exception as e:
        logging.exception("Ошибка при регистрации пользователя:")
        await message.answer("Произошла ошибка. Попробуй позже.")
    finally:
        db.close()



#--------------------------------------------------------------------------------------------Категории расходов------------------------------------------------------------------------------------

@dp.message(F.text == "Категории расходов")
async def handle_expense_categories(message: Message):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="expense").order_by(Category.name).all()

        if not categories:
            await message.answer("🗂️ У тебя пока нет категорий расходов.", reply_markup=expense_categories_menu)
        else:
            category_list = "\n".join(f"• {c.name}" for c in categories)
            await message.answer(f"🗂️ Твои категории расходов:\n{category_list}", reply_markup=expense_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при получении категорий расходов:")
        await message.answer("Произошла ошибка при получении категорий расходов.")
    finally:
        db.close()

@dp.message(F.text == "➕ Добавить категорию расхода")
async def add_expense_category_start(message: Message, state: FSMContext):
    await message.answer("🆕 Введи название новой категории расхода:", reply_markup=cancel_keyboard)
    await state.set_state(ExpenseCategoryManageStates.waiting_for_expense_category_name)


@dp.message(ExpenseCategoryManageStates.waiting_for_expense_category_name)
async def receive_expense_category_name(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_menu)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        category_name = message.text.strip()

        # Проверим, нет ли уже такой категории расходов
        existing = db.query(Category).filter_by(user_id=user.id, name=category_name, type="expense").first()
        if existing:
            await message.answer("⚠️ Такая категория расходов уже существует.", reply_markup=expense_categories_menu)
        else:
            new_category = Category(user_id=user.id, name=category_name, type="expense")
            db.add(new_category)
            db.commit()
            await message.answer(f"✅ Категория расхода \"{category_name}\" добавлена!", reply_markup=expense_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при добавлении категории расхода:")
        await message.answer("Произошла ошибка при добавлении категории расхода.")
    finally:
        db.close()
        await state.clear()


@dp.message(F.text == "🗑 Удалить категорию расхода")
async def delete_expense_category_start(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="expense").order_by(Category.name).all()

        if not categories:
            await message.answer("❗ У тебя нет категорий расходов для удаления.", reply_markup=expense_categories_menu)
            return

        # Кнопки с категориями
        buttons = [KeyboardButton(text=cat.name) for cat in categories]
        buttons.append(KeyboardButton(text="⬅ Назад"))
        row_width = 2
        rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
        delete_category_keyboard = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

        await message.answer("🗑 Выбери категорию расхода, которую хочешь удалить:", reply_markup=delete_category_keyboard)
        await state.set_state(ExpenseCategoryManageStates.waiting_for_expense_category_to_delete)

    finally:
        db.close()


@dp.message(ExpenseCategoryManageStates.waiting_for_expense_category_to_delete)
async def delete_expense_category_confirm(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=expense_categories_menu)
        return

    db = SessionLocal()
    try:
        category_name = message.text.strip()
        user = get_user_by_telegram_id(db, message.from_user.id)

        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        category = db.query(Category).filter_by(user_id=user.id, name=category_name, type="expense").first()

        if not category:
            await message.answer("❗ Категория расхода не найдена.", reply_markup=expense_categories_menu)
        else:
            db.delete(category)
            db.commit()
            await message.answer(f"✅ Категория расхода \"{category_name}\" удалена!", reply_markup=expense_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при удалении категории расхода:")
        await message.answer("Произошла ошибка при удалении категории расхода.")
    finally:
        db.close()
        await state.clear()

@dp.message(F.text == "✏️ Редактировать категорию расхода")
async def edit_expense_category_start(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="expense").order_by(Category.name).all()

        if not categories:
            await message.answer("❗ У тебя нет категорий расходов для редактирования.", reply_markup=expense_categories_menu)
            return

        # Кнопки с категориями
        buttons = [KeyboardButton(text=cat.name) for cat in categories]
        buttons.append(KeyboardButton(text="⬅ Назад"))
        row_width = 2
        rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
        edit_category_keyboard = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

        await message.answer("✏️ Выбери категорию расхода для редактирования:", reply_markup=edit_category_keyboard)
        await state.set_state(ExpenseCategoryManageStates.waiting_for_expense_category_to_edit)

    finally:
        db.close()


@dp.message(ExpenseCategoryManageStates.waiting_for_expense_category_to_edit)
async def choose_expense_category_to_edit(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=expense_categories_menu)
        return

    await state.update_data(old_category_name=message.text.strip())
    await message.answer("✏️ Введи новое название для выбранной категории:", reply_markup=cancel_keyboard)
    await state.set_state(ExpenseCategoryManageStates.waiting_for_new_expense_category_name)


@dp.message(ExpenseCategoryManageStates.waiting_for_new_expense_category_name)
async def save_new_expense_category_name(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=expense_categories_menu)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        data = await state.get_data()
        old_category_name = data.get("old_category_name")
        new_category_name = message.text.strip()

        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        category = db.query(Category).filter_by(user_id=user.id, name=old_category_name, type="expense").first()

        if not category:
            await message.answer("❗ Выбранная категория расхода не найдена.", reply_markup=expense_categories_menu)
        else:
            category.name = new_category_name
            db.commit()
            await message.answer(f"✅ Категория расхода переименована в \"{new_category_name}\"!", reply_markup=expense_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при редактировании категории расхода:")
        await message.answer("Произошла ошибка при редактировании категории расхода.")
    finally:
        db.close()
        await state.clear()

#------------------------------------------------------------------Категории доходов---------------------------------------------------------------
@dp.message(F.text == "Категории доходов")
async def handle_income_categories(message: Message):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="income").order_by(Category.name).all()

        if not categories:
            await message.answer("🗂️ У тебя пока нет категорий доходов.", reply_markup=income_categories_menu)
        else:
            category_list = "\n".join(f"• {c.name}" for c in categories)
            await message.answer(f"🗂️ Твои категории доходов:\n{category_list}", reply_markup=income_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при получении категорий доходов:")
        await message.answer("Произошла ошибка при получении категорий доходов.")
    finally:
        db.close()

@dp.message(F.text == "➕ Добавить категорию дохода")
async def add_income_category_start(message: Message, state: FSMContext):
    await message.answer("🆕 Введи название новой категории дохода:", reply_markup=cancel_keyboard)
    await state.set_state(IncomeCategoryManageStates.waiting_for_income_category_name)


@dp.message(IncomeCategoryManageStates.waiting_for_income_category_name)
async def receive_income_category_name(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_menu)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        category_name = message.text.strip()

        # Проверим, нет ли уже такой категории доходов
        existing = db.query(Category).filter_by(user_id=user.id, name=category_name, type="income").first()
        if existing:
            await message.answer("⚠️ Такая категория дохода уже существует.", reply_markup=income_categories_menu)
        else:
            new_category = Category(user_id=user.id, name=category_name, type="income")
            db.add(new_category)
            db.commit()
            await message.answer(f"✅ Категория дохода \"{category_name}\" добавлена!", reply_markup=income_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при добавлении категории дохода:")
        await message.answer("Произошла ошибка при добавлении категории дохода.")
    finally:
        db.close()
        await state.clear()



@dp.message(F.text == "🗑 Удалить категорию дохода")
async def delete_income_category_start(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="income").order_by(Category.name).all()

        if not categories:
            await message.answer("❗ У тебя нет категорий доходов для удаления.", reply_markup=income_categories_menu)
            return

        # Кнопки с названиями категорий доходов
        buttons = [KeyboardButton(text=cat.name) for cat in categories]
        buttons.append(KeyboardButton(text="⬅ Назад"))
        row_width = 2
        rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
        delete_income_category_keyboard = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

        await message.answer("🗑 Выбери категорию дохода для удаления:", reply_markup=delete_income_category_keyboard)
        await state.set_state(IncomeCategoryManageStates.waiting_for_income_category_to_delete)

    finally:
        db.close()

@dp.message(IncomeCategoryManageStates.waiting_for_income_category_to_delete)
async def delete_income_category_confirm(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=income_categories_menu)
        return

    db = SessionLocal()
    try:
        category_name = message.text.strip()
        user = get_user_by_telegram_id(db, message.from_user.id)

        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        category = db.query(Category).filter_by(user_id=user.id, name=category_name, type="income").first()

        if not category:
            await message.answer("❗ Категория дохода не найдена.", reply_markup=income_categories_menu)
        else:
            db.delete(category)
            db.commit()
            await message.answer(f"✅ Категория дохода \"{category_name}\" удалена!", reply_markup=income_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при удалении категории дохода:")
        await message.answer("Произошла ошибка при удалении категории дохода.")
    finally:
        db.close()
        await state.clear()


@dp.message(F.text == "✏️ Редактировать категорию дохода")
async def edit_income_category_start(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="income").order_by(Category.name).all()

        if not categories:
            await message.answer("❗ У тебя нет категорий доходов для редактирования.", reply_markup=income_categories_menu)
            return

        # Кнопки с категориями доходов
        buttons = [KeyboardButton(text=cat.name) for cat in categories]
        buttons.append(KeyboardButton(text="⬅ Назад"))
        row_width = 2
        rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
        edit_income_category_keyboard = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

        await message.answer("✏️ Выбери категорию дохода для редактирования:", reply_markup=edit_income_category_keyboard)
        await state.set_state(IncomeCategoryManageStates.waiting_for_income_category_to_edit)

    finally:
        db.close()


@dp.message(IncomeCategoryManageStates.waiting_for_income_category_to_edit)
async def choose_income_category_to_edit(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=income_categories_menu)
        return

    await state.update_data(old_income_category_name=message.text.strip())
    await message.answer("✏️ Введи новое название для выбранной категории дохода:", reply_markup=cancel_keyboard)
    await state.set_state(IncomeCategoryManageStates.waiting_for_new_income_category_name)


@dp.message(IncomeCategoryManageStates.waiting_for_new_income_category_name)
async def save_new_income_category_name(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=income_categories_menu)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        data = await state.get_data()
        old_category_name = data.get("old_income_category_name")
        new_category_name = message.text.strip()

        if not user:
            await message.answer("Сначала зарегистрируйся командой /start.")
            return

        category = db.query(Category).filter_by(user_id=user.id, name=old_category_name, type="income").first()

        if not category:
            await message.answer("❗ Выбранная категория дохода не найдена.", reply_markup=income_categories_menu)
        else:
            category.name = new_category_name
            db.commit()
            await message.answer(f"✅ Категория дохода переименована в \"{new_category_name}\"!", reply_markup=income_categories_menu)

    except Exception as e:
        logging.exception("Ошибка при редактировании категории дохода:")
        await message.answer("Произошла ошибка при редактировании категории дохода.")
    finally:
        db.close()
        await state.clear()


#----------------------------------------------------------------Добавление дохода--------------------------------------------------

@dp.message(F.text == "Добавить доход")
async def handle_add_income(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала напиши /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="income").order_by(Category.name).all()

        if not categories:
            await message.answer("❗ У тебя нет категорий доходов. Сначала добавь хотя бы одну.", reply_markup=main_menu)
            return

        # Кнопки с категориями доходов
        buttons = [KeyboardButton(text=cat.name) for cat in categories]
        buttons.append(KeyboardButton(text="⬅ Назад"))
        row_width = 2
        rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
        income_category_keyboard = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

        await message.answer("💸 Из какой категории доход?", reply_markup=income_category_keyboard)
        await state.set_state(IncomeStates.waiting_for_income_category_choice)

    finally:
        db.close()


@dp.message(IncomeStates.waiting_for_income_category_choice)
async def handle_income_category_chosen(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_menu)
        return

    selected_category = message.text.strip()
    await state.update_data(selected_income_category=selected_category)

    await message.answer("✍️ Введи сумму дохода (только число):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(IncomeStates.waiting_for_income_amount)



@dp.message(IncomeStates.waiting_for_income_amount)
async def handle_income_amount(message: Message, state: FSMContext):
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_menu)
        return

    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала напиши /start.")
            return

        data = await state.get_data()
        category_name = data.get("selected_income_category")

        category = db.query(Category).filter_by(user_id=user.id, name=category_name, type="income").first()

        if not category:
            await message.answer("❗ Категория дохода не найдена.", reply_markup=main_menu)
            await state.clear()
            return

        try:
            amount = Decimal(message.text.strip().replace(",", "."))
        except:
            await message.answer("❗ Введи только сумму, например: `5000.00`")
            return

        # Сохраняем доход
        add_income(db, user_id=user.id, category_id=category.id, amount=amount)

        await message.answer(f"✅ Доход {amount}₽ в категории \"{category_name}\" добавлен!", reply_markup=main_menu)

    except Exception as e:
        logging.exception("Ошибка при добавлении дохода:")
        await message.answer("Произошла ошибка при добавлении дохода.")
    finally:
        db.close()
        await state.clear()




#----------------------------------------------------------------Добавление расхода-------------------------------------------------


@dp.message(F.text == "Добавить расход")
async def handle_add_expense(message: Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала напиши /start.")
            return

        categories = db.query(Category).filter_by(user_id=user.id, type="expense").order_by(Category.name).all()
        if not categories:
            await message.answer("У тебя пока нет категорий. Добавь хотя бы одну.")
            return

        # Кнопки с категориями
        buttons = [KeyboardButton(text=cat.name) for cat in categories]
        buttons.append(KeyboardButton(text="⬅ Назад"))
        row_width = 2
        rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
        category_keyboard = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

        await message.answer("💸 Из какой категории трата?", reply_markup=category_keyboard)
        await state.set_state(ExpenseStates.waiting_for_category_choice)

    finally:
        db.close()

@dp.message(ExpenseStates.waiting_for_category_choice)
async def handle_category_chosen(message: Message, state: FSMContext):

    if message.text == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_menu)
        return
    selected_category = message.text.strip()
    await state.update_data(selected_category=selected_category)

    await message.answer("✍️ Введи сумму траты (только число):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ExpenseStates.waiting_for_amount_and_description)

@dp.message(ExpenseStates.waiting_for_amount_and_description)
async def handle_amount_only(message: Message, state: FSMContext):
    if message.text == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_menu)
        return
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("Сначала напиши /start.")
            return

        data = await state.get_data()
        category_name = data.get("selected_category")

        # Найдём категорию
        category = db.query(Category).filter_by(user_id=user.id, name=category_name, type="expense").first()
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
    if message.text.strip() == "⬅ Назад":
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_menu)
        return

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

        # Получение расходов и доходов
        try:
            expense_report = get_monthly_expense_report(db, user.id)
        except Exception as e:
            expense_report = []
            logging.error(f"Ошибка при получении расходов: {e}")

        try:
            income_report = get_monthly_income_report(db, user.id)
        except Exception as e:
            income_report = []
            logging.error(f"Ошибка при получении доходов: {e}")

        lines = []

        # Блок расходов
        if expense_report:
            total_expenses = sum([(row[1] or 0) for row in expense_report])
            lines.append(f"📊 Расходы за {date.today():%B}:\n")
            for name, amount in expense_report:
                lines.append(f"• {name}: {float(amount or 0):,.2f} ₽")
            lines.append(f"💰 Всего расходов: {float(total_expenses):,.2f} ₽\n")
        else:
            lines.append("📭 В этом месяце расходов не найдено.\n")

        # Блок доходов
        if income_report:
            total_incomes = sum([(row[1] or 0) for row in income_report])
            lines.append(f"📈 Доходы за {date.today():%B}:\n")
            for name, amount in income_report:
                lines.append(f"• {name}: {float(amount or 0):,.2f} ₽")
            lines.append(f"💵 Всего доходов: {float(total_incomes):,.2f} ₽\n")
        else:
            lines.append("📭 В этом месяце доходов не найдено.\n")

        # Баланс
        if expense_report or income_report:
            total_expenses = sum([(row[1] or 0) for row in expense_report]) if expense_report else 0
            total_incomes = sum([(row[1] or 0) for row in income_report]) if income_report else 0
            balance = total_incomes - total_expenses
            balance_sign = "➕" if balance >= 0 else "➖"
            lines.append(f"🏦 Баланс за месяц: {balance_sign} {abs(balance):,.2f} ₽")

        await message.answer("\n".join(lines))

    except Exception as e:
        logging.exception(f"Глобальная ошибка при формировании отчета: {e}")
        await message.answer("Произошла ошибка при формировании отчёта.")
    finally:
        db.close()




from aiogram.fsm.state import any_state

@dp.message(F.text == "⬅ Назад", any_state)
async def handle_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🚫 Действие отменено.", reply_markup=main_menu)

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
