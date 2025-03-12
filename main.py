import asyncio
import sqlite3
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters
import random
import string
import csv
from config import TOKEN, ADMIN_IDS
from database import init_db, get_db_data, get_db_single, execute_db

# Состояния для ConversationHandler
CATEGORY, GAME, PRODUCT, DEPOSIT, PROMO, SUPPORT, ADD_PRODUCT, ADD_PROMO, REPLY, SET_PIN, MANAGE_CITIES, ADD_CITY, EDIT_CITY, MANAGE_ASSORTMENT, ADD_ASSORTMENT_NAME, ADD_ASSORTMENT_WEIGHT, ADD_ASSORTMENT_PRICE, EDIT_ASSORTMENT_NAME, EDIT_ASSORTMENT_WEIGHT, EDIT_ASSORTMENT_PRICE, MANAGE_DISTRICTS, ADD_DISTRICT, MANAGE_USERS, SEARCH_CHAT, SEARCH_SYSTEM_ID, SEARCH_USERNAME, USER_PROFILE = range(27)

# Генерация реферального кода
def generate_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Генерация уникального system_id (7 цифр)
def generate_system_id(existing_ids):
    while True:
        system_id = random.randint(1000000, 9999999)  # 7-значное число
        if system_id not in existing_ids and not get_db_single("SELECT system_id FROM users WHERE system_id = ?", (system_id,)):
            return system_id

# Главное меню
def main_menu(user_id):
    total_products = get_db_single("SELECT COUNT(*) FROM products")[0]
    stock_status = "в наличии" if total_products > 0 else "нет в наличии"
    keyboard = [
        [InlineKeyboardButton(f"Начать покупки [{stock_status}]", callback_data="categories")],
        [InlineKeyboardButton("Личный кабинет", callback_data="profile")],
        [InlineKeyboardButton("Отзывы клиентов", callback_data="reviews")],
        [InlineKeyboardButton("Обновить страницу", callback_data="main")],
        [InlineKeyboardButton("Контакты магазина", callback_data="contacts")],
        [InlineKeyboardButton("Получить 150Р на счёт!", callback_data="bonus")]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("Панель управления", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)

# Приветственное сообщение
WELCOME_MESSAGE = (
    "🌸 <b>Добро пожаловать в Pussy Riot</b> 🌸\n"
    "Твой уютный уголок чтобы отлично провести время!\n"
    "═══════════════════════════════\n"
    "💖 <b>Почему мы?</b> 💖\n"
    "🌟 Самое качественный товар в городе! 🌟\n"
    "═══════════════════════════════\n"
    " 💌 Запомни нас: 💌\n"
    "    👇 <i>Лучшее место в городе!</i> 👇\n"
    "       💓 <b>Pussy Riot</b> 💓\n"
)

# Статусы для заявок на пополнение
status_map = {
    "pending": "🟡 В ожидании оплаты",
    "success": "🟢 Успешно",
    "expired": "🔴 Просрочен"
}

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args
    
    if not get_db_single("SELECT id FROM users WHERE id = ?", (user_id,)):
        existing_ids = [row[0] for row in get_db_data("SELECT id FROM users")]
        ref_code = generate_ref_code()
        system_id = generate_system_id(existing_ids)
        execute_db("INSERT INTO users (id, system_id, balance, ref_code, ref_count, role, banned) VALUES (?, ?, 0, ?, 0, 'client', 0)", (user_id, system_id, ref_code))
        if args and args[0] in [row[0] for row in get_db_data("SELECT ref_code FROM users")]:
            ref_owner = get_db_single("SELECT id FROM users WHERE ref_code = ?", (args[0],))[0]
            execute_db("UPDATE users SET ref_count = ref_count + 1, balance = balance + 50 WHERE id = ?", (ref_owner,))
            await context.bot.send_message(ref_owner, "По вашей реферальной ссылке зарегистрировался новый пользователь! +50 на баланс.")

    keyboard = [[InlineKeyboardButton("Продолжить >>", callback_data="main")]]
    await update.message.reply_text(WELCOME_MESSAGE, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# Панель управления администратора
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    query = update.callback_query
    total_users = get_db_single("SELECT COUNT(*) FROM users")[0]
    total_products = get_db_single("SELECT COUNT(*) FROM products")[0]
    total_products_value = get_db_single("SELECT SUM(price) FROM products")[0] or 0
    total_sales = get_db_single("SELECT COUNT(*) FROM purchases")[0]
    total_earnings = get_db_single("SELECT SUM(price) FROM purchases")[0] or 0
    total_tickets = get_db_single("SELECT COUNT(*) FROM support_requests")[0]
    total_categories = get_db_single("SELECT COUNT(*) FROM categories")[0]
    total_promo_codes = get_db_single("SELECT COUNT(*) FROM promo_codes")[0]
    total_deposits = get_db_single("SELECT COUNT(*) FROM deposit_requests")[0]
    
    pin_status = "Не установлен" if not get_db_single("SELECT pin FROM users WHERE id = ?", (user_id,))[0] else "Установлен"

    server_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    msg = (
        "⚙️ <b>Панель управления</b>\n"
        "═══════════════════════════════\n"
        f"🕒 <b>Время сервера:</b> {server_time}\n"
        "═══════════════════════════════\n"
        "<b>Общая информация</b>\n"
        f"┌ Клиентов в магазине: {total_users} чел.\n"
        f"├ Товаров в наличии: {total_products} шт. ({total_products_value:,} ₽)\n"
        f"├ Товаров продано всего: {total_sales} шт.\n"
        f"├ В активных рулетках: 0 адресов\n"
        f"├ В прошедших рулетках: 0 адресов\n"
        f"└ Заработано за 2025 год: {total_earnings:,} ₽\n"
        "<b>Статистика финансов (март)</b>\n"
        "┌ За 10 число, текущий день: 0 ₽\n"
        "├ За 09 число, вчерашний день: 0 ₽\n"
        "└ За март с 1 числа: 0 ₽\n"
        "<b>Статистика продаж (март)</b>\n"
        "┌ За 10 число, текущий день:\n"
        "├ Через API бот: 0 шт.\n"
        "├ Через USER бот: 0 шт.\n"
        "└ Через сайт: 0 шт.\n"
        "┌ За 09 число, вчерашний день:\n"
        "├ Через API бот: 0 шт.\n"
        "├ Через USER бот: 0 шт.\n"
        "└ Через сайт: 0 шт.\n"
        "═══════════════════════════════\n"
        f"🔒 <b>PIN-код:</b> [{pin_status}]"
    )

    keyboard = [
        [InlineKeyboardButton("🛒 Управление магазином", callback_data="admin_store")],
        [InlineKeyboardButton("💰 Финансы", callback_data="admin_finance")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="view_users")],
        [InlineKeyboardButton("🎫 Тикеты", callback_data="view_support")],
        [InlineKeyboardButton("🎁 Акции и бонусы", callback_data="admin_promotions")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [
            InlineKeyboardButton("<<", callback_data="main"),
            InlineKeyboardButton("Обновить страницу", callback_data="admin"),
            InlineKeyboardButton(">>", callback_data="main")
        ]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# Обработчик callback-запросов
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    await query.answer()

    if data == "categories":
        categories_data = get_db_data("SELECT name FROM categories")
        keyboard = [[InlineKeyboardButton(cat[0], callback_data=f"cat_{cat[0]}")] for cat in categories_data]
        keyboard.append([InlineKeyboardButton("Назад", callback_data="main")])
        await query.edit_message_text("Выберите город:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CATEGORY

    elif data.startswith("cat_"):
        category = data[4:]
        games = get_db_data("SELECT name FROM games WHERE category_id = (SELECT id FROM categories WHERE name = ?)", (category,))
        keyboard = [[InlineKeyboardButton(game[0], callback_data=f"game_{game[0]}")] for game in games]
        keyboard.append([InlineKeyboardButton("Назад", callback_data="categories")])
        await query.edit_message_text(f"Выберите товар в городе {category}:", reply_markup=InlineKeyboardMarkup(keyboard))
        return GAME

    elif data.startswith("game_"):
        game = data[5:]
        prods = get_db_data("SELECT name, price FROM products WHERE game_id = (SELECT id FROM games WHERE name = ?)", (game,))
        if prods:
            keyboard = [[InlineKeyboardButton(f"{prod[0]} — {prod[1]} руб.", callback_data=f"buy_{game}_{prod[0]}")] for prod in prods]
            keyboard.append([InlineKeyboardButton("Назад", callback_data="categories")])
            msg = f"🛒 Товары для {game}:\n\n" + "\n".join([f"• {prod[0]} — {prod[1]} руб." for prod in prods])
        else:
            keyboard = [[InlineKeyboardButton("Назад", callback_data="categories")]]
            msg = f"🛒 Товары для {game}:\n\nНет товаров в наличии."
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return PRODUCT

    elif data.startswith("buy_"):
        _, game, product = data.split("_", 2)
        prod = get_db_single("SELECT price, code FROM products WHERE name = ? AND game_id = (SELECT id FROM games WHERE name = ?)", (product, game))
        if prod:
            price, code = prod
            balance = get_db_single("SELECT balance FROM users WHERE id = ?", (user_id,))[0]
            if balance >= price:
                execute_db("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
                execute_db("INSERT INTO purchases (user_id, product_name, price) VALUES (?, ?, ?)", (user_id, f"{product} для {game}", price))
                await query.message.reply_text(f"✅ Вы купили *{product}* для *{game}*!\nВаш код: `{code}`\nСпасибо за покупку!", parse_mode="Markdown")
            else:
                await query.message.reply_text("❌ Недостаточно средств! Пополните баланс в личном кабинете.")
        else:
            await query.message.reply_text("❌ Товар не найден.")
        total_products = get_db_single("SELECT COUNT(*) FROM products")[0]
        await query.edit_message_text(f"🏬 <b>Магазин цифровых товаров</b>\n\nТоваров в наличии: {total_products}", 
                                      reply_markup=main_menu(user_id), parse_mode="HTML")
        return ConversationHandler.END

    elif data == "profile":
        user_data = get_db_single("SELECT balance, ref_count, ref_code, pin, system_id FROM users WHERE id = ?", (user_id,))
        balance, ref_count, ref_code, pin, system_id = user_data
        purchases = get_db_data("SELECT product_name, price FROM purchases WHERE user_id = ?", (user_id,))
        purchases_count = len(purchases) if purchases else 0
        pin_status = "Включено" if pin else "Выключено"
        support_requests = get_db_data("SELECT request_id FROM support_requests WHERE user_id = ?", (user_id,))
        support_count = len(support_requests) if support_requests else 0
        
        reviews_count = 0
        approved_tickets = 0
        rejected_tickets = 0

        msg = (
            "🌸 <b>Добро пожаловать в твой личный кабинет</b> 🌸\n"
            "Выбери нужный пункт меню:\n"
            "═══════════════════════════════\n"
            f"🆔 <b>Ваш ID внутри системы:</b> {system_id}\n"
            f"💬 <b>Ваш CHAT-ID:</b> {user_id}\n"
            "═══════════════════════════════\n"
            f"💰 <b>Баланс RUB:</b> {balance}\n"
            f"💰 <b>Баланс BTC:</b> 0.00000000\n"
            f"💰 <b>Баланс LTC:</b> 0.00000000\n"
            "═══════════════════════════════\n"
            f"🛒 <b>Покупок:</b> {purchases_count} шт\n"
            f"📝 <b>Отзывы:</b> {reviews_count} шт\n"
            f"✅ <b>Одобренных тикетов:</b> {approved_tickets} шт\n"
            f"❌ <b>Отказанных тикетов:</b> {rejected_tickets} шт\n"
        )
        keyboard = [
            [InlineKeyboardButton("Список ваших счетов", callback_data="accounts")],
            [InlineKeyboardButton(f"Список ваших покупок [{purchases_count}]", callback_data="purchases")],
            [InlineKeyboardButton(f"PIN-Код блокировки бота [{pin_status}]", callback_data="set_pin")],
            [InlineKeyboardButton("Пополнить баланс", callback_data="deposit")],
            [InlineKeyboardButton("Управление вашим ботом", callback_data="bot_management")],
            [InlineKeyboardButton(f"Обращения в поддержку [{support_count}]", callback_data="support")],
            [InlineKeyboardButton("<< Вернуться на главную", callback_data="main")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return ConversationHandler.END

    elif data == "reviews":
        await query.edit_message_text("📝 <b>Отзывы клиентов</b>\n\nФункция в разработке.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main")]]))
        return ConversationHandler.END

    elif data == "contacts":
        await query.edit_message_text("📞 <b>Контакты магазина</b>\n\nTelegram: @PussyRiotSupport\nEmail: support@pussyriot.ru", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main")]]))
        return ConversationHandler.END

    elif data == "bonus":
        user_data = get_db_single("SELECT ref_count FROM users WHERE id = ?", (user_id,))[0]
        if user_data < 3:
            await query.edit_message_text("🎁 <b>Получить 150Р</b>\n\nПригласи 3 друзей по своей реферальной ссылке, чтобы получить бонус!", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main")]]))
        else:
            execute_db("UPDATE users SET balance = balance + 150 WHERE id = ?", (user_id,))
            await query.edit_message_text("🎁 <b>Поздравляем!</b>\n\nВы получили 150Р на баланс!", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="main")]]))
        return ConversationHandler.END

    elif data == "accounts":
        await query.edit_message_text("💳 <b>Список ваших счетов</b>\n\nRUB: {}\nBTC: 0.00000000\nLTC: 0.00000000".format(
            get_db_single("SELECT balance FROM users WHERE id = ?", (user_id,))[0]), 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="profile")]]))
        return ConversationHandler.END

    elif data == "purchases":
        purchases = get_db_data("SELECT product_name, price FROM purchases WHERE user_id = ?", (user_id,))
        if purchases:
            msg = "🛒 <b>Ваши покупки</b>\n\n" + "\n".join([f"• {p[0]} — {p[1]} руб." for p in purchases])
        else:
            msg = "🛒 <b>Ваши покупки</b>\n\nУ вас пока нет покупок."
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="profile")]]))
        return ConversationHandler.END

    elif data == "support":
        await query.edit_message_text("🎫 <b>Обращения в поддержку</b>\n\nФункция в разработке.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="profile")]]))
        return ConversationHandler.END

    elif data == "bot_management":
        await query.edit_message_text("🤖 <b>Управление вашим ботом</b>\n\nФункция в разработке.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="profile")]]))
        return ConversationHandler.END

    elif data == "deposit":
        keyboard = [
            [InlineKeyboardButton("Пополнить через BTC", callback_data="deposit_btc")],
            [InlineKeyboardButton("Пополнить через LTC", callback_data="deposit_ltc")],
            [InlineKeyboardButton("Пополнить через RUB", callback_data="deposit_rub")],
            [InlineKeyboardButton("Назад", callback_data="profile")]
        ]
        await query.edit_message_text("Выберите способ пополнения:", reply_markup=InlineKeyboardMarkup(keyboard))
        return DEPOSIT

    elif data in ["deposit_btc", "deposit_ltc", "deposit_rub"]:
        currency = {"deposit_btc": "BTC", "deposit_ltc": "LTC", "deposit_rub": "RUB"}[data]
        await query.edit_message_text(f"💸 <b>Пополнение через {currency}</b>\n\nВведите сумму для пополнения:", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="deposit")]]))
        return DEPOSIT

    elif data == "admin_store" and user_id in ADMIN_IDS:
        total_categories = get_db_single("SELECT COUNT(*) FROM categories")[0]
        total_games = get_db_single("SELECT COUNT(*) FROM games")[0]
        total_products = get_db_single("SELECT COUNT(*) FROM products")[0]
        keyboard = [
            [InlineKeyboardButton(f"Управление городами [{total_categories}]", callback_data="manage_cities")],
            [InlineKeyboardButton(f"Управление ассортиментом [{total_games}]", callback_data="manage_assortment")],
            [InlineKeyboardButton(f"Добавить товар [{total_products}]", callback_data="add_product")],
            [InlineKeyboardButton("Назад", callback_data="admin")]
        ]
        await query.edit_message_text("🛒 <b>Управление магазином</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return MANAGE_CITIES

    elif data == "manage_cities" and user_id in ADMIN_IDS:
        categories = get_db_data("SELECT id, name FROM categories")
        keyboard = [[InlineKeyboardButton(cat[1], callback_data=f"edit_city_{cat[0]}")] for cat in categories]
        keyboard.extend([
            [InlineKeyboardButton("Добавить город", callback_data="add_city")],
            [InlineKeyboardButton("Назад", callback_data="admin_store")]
        ])
        await query.edit_message_text("🏙 <b>Управление городами</b>\nВыберите город для редактирования или добавьте новый:", 
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return MANAGE_CITIES

    elif data == "add_city" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите название нового города:")
        return ADD_CITY

    elif data.startswith("edit_city_") and user_id in ADMIN_IDS:
        city_id = data.split("_")[2]
        context.user_data["city_id"] = city_id
        city_name = get_db_single("SELECT name FROM categories WHERE id = ?", (city_id,))[0]
        keyboard = [
            [InlineKeyboardButton("Изменить название", callback_data="edit_city_name")],
            [InlineKeyboardButton("Удалить город", callback_data="delete_city")],
            [InlineKeyboardButton("Назад", callback_data="manage_cities")]
        ]
        await query.edit_message_text(f"🏙 <b>Редактирование города:</b> {city_name}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return MANAGE_CITIES

    elif data == "edit_city_name" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите новое название города:")
        return EDIT_CITY

    elif data == "delete_city" and user_id in ADMIN_IDS:
        city_id = context.user_data.get("city_id")
        if city_id:
            execute_db("DELETE FROM categories WHERE id = ?", (city_id,))
            await query.edit_message_text("✅ Город удалён.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="manage_cities")]]))
        return MANAGE_CITIES

    elif data == "manage_assortment" and user_id in ADMIN_IDS:
        games = get_db_data("SELECT id, name FROM games")
        keyboard = [[InlineKeyboardButton(game[1], callback_data=f"edit_game_{game[0]}")] for game in games]
        keyboard.extend([
            [InlineKeyboardButton("Добавить элемент ассортимента", callback_data="add_assortment")],
            [InlineKeyboardButton("Назад", callback_data="admin_store")]
        ])
        await query.edit_message_text("📦 <b>Управление ассортиментом</b>\nВыберите элемент для редактирования или добавьте новый:", 
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return MANAGE_ASSORTMENT

    elif data == "add_assortment" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите название нового элемента ассортимента:")
        return ADD_ASSORTMENT_NAME

    elif data.startswith("edit_game_") and user_id in ADMIN_IDS:
        game_id = data.split("_")[2]
        context.user_data["game_id"] = game_id
        game_name = get_db_single("SELECT name FROM games WHERE id = ?", (game_id,))[0]
        keyboard = [
            [InlineKeyboardButton("Изменить данные", callback_data="edit_assortment_name")],
            [InlineKeyboardButton("Удалить элемент", callback_data="delete_assortment")],
            [InlineKeyboardButton("Назад", callback_data="manage_assortment")]
        ]
        await query.edit_message_text(f"📦 <b>Редактирование элемента:</b> {game_name}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return MANAGE_ASSORTMENT

    elif data == "delete_assortment" and user_id in ADMIN_IDS:
        game_id = context.user_data.get("game_id")
        if game_id:
            execute_db("DELETE FROM games WHERE id = ?", (game_id,))
            execute_db("DELETE FROM products WHERE game_id = ?", (game_id,))
            await query.edit_message_text("✅ Элемент ассортимента удалён.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="manage_assortment")]]))
        return MANAGE_ASSORTMENT

    elif data == "view_users" and user_id in ADMIN_IDS:
        if "user_filter" not in context.user_data:
            context.user_data["user_filter"] = "client"  # По умолчанию показываем клиентов
        filter_role = context.user_data["user_filter"]
        users = get_db_data("SELECT id, system_id, balance, role, banned FROM users WHERE role = ?", (filter_role,))
        user_buttons = []
        for u_id, system_id, balance, role, banned in users:
            status = "🟢" if not banned else "🔴"
            name = context.bot.get_chat(u_id).first_name or "Без имени"
            role_display = {"client": "Клиент", "courier": "Курьер", "admin": "Админ", "operator": "Оператор"}.get(role, "Клиент")
            user_buttons.append([InlineKeyboardButton(f"{status} [{role_display}] {name} [{balance} руб.]", callback_data=f"user_{u_id}")])
        if not user_buttons:
            user_buttons.append([InlineKeyboardButton("Список пуст", callback_data="no_action")])
        keyboard = [
            [InlineKeyboardButton("Поиск по CHAT", callback_data="search_chat"), InlineKeyboardButton("Поиск по ID в системе", callback_data="search_system_id")],
            [InlineKeyboardButton("Поиск по USERNAME", callback_data="search_username"), InlineKeyboardButton("Экспорт клиентов", callback_data="export_users")],
            [
                InlineKeyboardButton("☀️ Все" if filter_role == "client" else "🌙 Все", callback_data="filter_client"),
                InlineKeyboardButton("☀️ Курьеры" if filter_role == "courier" else "🌙 Курьеры", callback_data="filter_courier")
            ],
            [
                InlineKeyboardButton("☀️ Админы" if filter_role == "admin" else "🌙 Админы", callback_data="filter_admin"),
                InlineKeyboardButton("☀️ Операторы" if filter_role == "operator" else "🌙 Операторы", callback_data="filter_operator")
            ]
        ]
        back_button = [[InlineKeyboardButton("Назад", callback_data="admin")]]
        msg = ("Поиск и управление пользователями.\n═════════════════════════\nВыберите нужного пользователя или воспользуйтесь поиском.\n")
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard + user_buttons + back_button), parse_mode="HTML")
        return MANAGE_USERS

    elif data.startswith("filter_") and user_id in ADMIN_IDS:
        context.user_data["user_filter"] = data.split("_")[1]
        await button(update, context)
        return MANAGE_USERS

    elif data.startswith("user_") and user_id in ADMIN_IDS:
        target_user_id = int(data.split("_")[1])
        user_data = get_db_single("SELECT system_id, balance, role, banned FROM users WHERE id = ?", (target_user_id,))
        if user_data:
            system_id, balance, role, banned = user_data
            status = "🟢" if not banned else "🔴"
            name = context.bot.get_chat(target_user_id).first_name or "Без имени"
            role_display = {"client": "Клиент", "courier": "Курьер", "admin": "Админ", "operator": "Оператор"}.get(role, "Клиент")
            keyboard = [
                [InlineKeyboardButton("Забанить" if not banned else "Разбанить", callback_data=f"ban_{target_user_id}" if not banned else f"unban_{target_user_id}")],
                [InlineKeyboardButton("Изменить роль", callback_data=f"change_role_{target_user_id}")],
                [InlineKeyboardButton("Назад", callback_data="view_users")]
            ]
            msg = f"👤 <b>Пользователь:</b> {name}\nСтатус: {status}\nРоль: {role_display}\nБаланс: {balance} руб.\nSystem ID: {system_id}"
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return USER_PROFILE

    elif data.startswith("ban_") and user_id in ADMIN_IDS:
        target_user_id = int(data.split("_")[1])
        execute_db("UPDATE users SET banned = 1 WHERE id = ?", (target_user_id,))
        await query.edit_message_text("✅ Пользователь забанен.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
        return MANAGE_USERS

    elif data.startswith("unban_") and user_id in ADMIN_IDS:
        target_user_id = int(data.split("_")[1])
        execute_db("UPDATE users SET banned = 0 WHERE id = ?", (target_user_id,))
        await query.edit_message_text("✅ Пользователь разбанен.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
        return MANAGE_USERS

    elif data.startswith("change_role_") and user_id in ADMIN_IDS:
        target_user_id = int(data.split("_")[2])
        keyboard = [
            [InlineKeyboardButton("Клиент", callback_data=f"set_role_{target_user_id}_client")],
            [InlineKeyboardButton("Курьер", callback_data=f"set_role_{target_user_id}_courier")],
            [InlineKeyboardButton("Админ", callback_data=f"set_role_{target_user_id}_admin")],
            [InlineKeyboardButton("Оператор", callback_data=f"set_role_{target_user_id}_operator")],
            [InlineKeyboardButton("Назад", callback_data=f"user_{target_user_id}")]
        ]
        await query.edit_message_text("Выберите новую роль:", reply_markup=InlineKeyboardMarkup(keyboard))
        return USER_PROFILE

    elif data.startswith("set_role_") and user_id in ADMIN_IDS:
        parts = data.split("_")
        target_user_id, new_role = int(parts[2]), parts[3]
        execute_db("UPDATE users SET role = ? WHERE id = ?", (new_role, target_user_id))
        await query.edit_message_text(f"✅ Роль изменена на {new_role}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
        return MANAGE_USERS

    elif data == "search_chat" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите Telegram ID (CHAT-ID):")
        return SEARCH_CHAT

    elif data == "search_system_id" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите ID в системе (7 цифр):")
        return SEARCH_SYSTEM_ID

    elif data == "search_username" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите Telegram username (например, @example):")
        return SEARCH_USERNAME

    elif data == "export_users" and user_id in ADMIN_IDS:
        users = get_db_data("SELECT id, system_id, balance, role, banned FROM users")
        with open("users_export.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Telegram ID", "System ID", "Balance", "Role", "Banned"])
            for user in users:
                writer.writerow(user)
        await query.message.reply_document(document=open("users_export.csv", "rb"), filename="users_export.csv")
        await query.edit_message_text("✅ Экспорт клиентов выполнен.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
        return MANAGE_USERS

    elif data == "view_support" and user_id in ADMIN_IDS:
        tickets = get_db_data("SELECT request_id, user_id, message FROM support_requests WHERE status = 'pending'")
        keyboard = []
        for ticket in tickets:
            request_id, user_id, message = ticket
            user_name = context.bot.get_chat(user_id).first_name or "Без имени"
            keyboard.append([InlineKeyboardButton(f"Тикет #{request_id} от {user_name}", callback_data=f"ticket_{request_id}")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="admin")])
        await query.edit_message_text("🎫 <b>Тикеты поддержки</b>\nВыберите тикет для обработки:", 
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return SUPPORT

    elif data.startswith("ticket_") and user_id in ADMIN_IDS:
        request_id = data.split("_")[1]
        ticket = get_db_single("SELECT user_id, message FROM support_requests WHERE request_id = ?", (request_id,))
        if ticket:
            user_id, message = ticket
            user_name = context.bot.get_chat(user_id).first_name or "Без имени"
            keyboard = [
                [InlineKeyboardButton("Ответить", callback_data=f"reply_{request_id}")],
                [InlineKeyboardButton("Закрыть тикет", callback_data=f"close_{request_id}")],
                [InlineKeyboardButton("Назад", callback_data="view_support")]
            ]
            await query.edit_message_text(f"🎫 <b>Тикет #{request_id}</b>\nОт: {user_name}\nСообщение: {message}", 
                                          reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return SUPPORT

    elif data.startswith("reply_") and user_id in ADMIN_IDS:
        context.user_data["request_id"] = data.split("_")[1]
        await query.message.reply_text("Введите ответ на тикет:")
        return REPLY

    elif data.startswith("close_") and user_id in ADMIN_IDS:
        request_id = data.split("_")[1]
        execute_db("UPDATE support_requests SET status = 'closed' WHERE request_id = ?", (request_id,))
        await query.edit_message_text("✅ Тикет закрыт.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_support")]]))
        return SUPPORT

    elif data == "admin_promotions" and user_id in ADMIN_IDS:
        total_promo_codes = get_db_single("SELECT COUNT(*) FROM promo_codes")[0]
        keyboard = [
            [InlineKeyboardButton(f"Добавить промокод [{total_promo_codes}]", callback_data="add_promo")],
            [InlineKeyboardButton("Назад", callback_data="admin")]
        ]
        await query.edit_message_text("🎁 <b>Акции и бонусы</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return ADD_PROMO

    elif data == "add_promo" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите новый промокод:")
        return ADD_PROMO

    elif data == "admin_finance" and user_id in ADMIN_IDS:
        await query.edit_message_text("💰 <b>Финансы</b>\n\nФункция в разработке.", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin")]]))
        return ConversationHandler.END

    elif data == "admin_settings" and user_id in ADMIN_IDS:
        pin_status = "Не установлен" if not get_db_single("SELECT pin FROM users WHERE id = ?", (user_id,))[0] else "Установлен"
        keyboard = [
            [InlineKeyboardButton(f"Установить PIN-код [{pin_status}]", callback_data="set_pin_admin")],
            [InlineKeyboardButton("Назад", callback_data="admin")]
        ]
        await query.edit_message_text("⚙️ <b>Настройки</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return SET_PIN

    elif data == "set_pin_admin" and user_id in ADMIN_IDS:
        await query.message.reply_text("Введите новый PIN-код (4 цифры):")
        return SET_PIN

    elif data.startswith("add_prod_to_") and user_id in ADMIN_IDS:
        game_id = data.split("_")[3]
        product = context.user_data.get("new_product")
        if product:
            execute_db("INSERT INTO products (game_id, name, price, code) VALUES (?, ?, ?, ?)", 
                       (game_id, product["name"], product["price"], product["code"]))
            await query.edit_message_text(f"✅ Товар {product['name']} добавлен в ассортимент.", 
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_store")]]))
            context.user_data.pop("new_product", None)
        return ConversationHandler.END

    elif data == "main":
        total_products = get_db_single("SELECT COUNT(*) FROM products")[0]
        await query.edit_message_text(f"🏬 <b>Магазин цифровых товаров</b>\n\nТоваров в наличии: {total_products}", 
                                      reply_markup=main_menu(user_id), parse_mode="HTML")
        return ConversationHandler.END

    elif data == "admin" and user_id in ADMIN_IDS:
        await admin_panel(update, context, user_id)
        return ConversationHandler.END

# Обработка добавления города
async def process_add_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    city_name = update.message.text.strip()
    if city_name:
        execute_db("INSERT INTO categories (name) VALUES (?)", (city_name,))
        await update.message.reply_text(f"✅ Город {city_name} добавлен.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="manage_cities")]]))
    else:
        await update.message.reply_text("❌ Введите корректное название города!")
    return ConversationHandler.END

# Обработка редактирования города
async def process_edit_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    city_id = context.user_data.get("city_id")
    new_name = update.message.text.strip()
    if new_name and city_id:
        execute_db("UPDATE categories SET name = ? WHERE id = ?", (new_name, city_id))
        await update.message.reply_text(f"✅ Название города обновлено на {new_name}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="manage_cities")]]))
    else:
        await update.message.reply_text("❌ Введите корректное название города!")
    return ConversationHandler.END

# Обработка добавления ассортимента (название)
async def process_add_assortment_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    name = update.message.text.strip()
    if name:
        context.user_data["new_assortment_name"] = name
        await update.message.reply_text("Введите вес элемента:")
        return ADD_ASSORTMENT_WEIGHT
    else:
        await update.message.reply_text("❌ Введите корректное название товара!")
        return ConversationHandler.END

# Обработка добавления ассортимента (вес)
async def process_add_assortment_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    weight = update.message.text.strip()
    if weight:
        context.user_data["new_assortment_weight"] = weight
        await update.message.reply_text("Введите цену элемента (в рублях):")
        return ADD_ASSORTMENT_PRICE
    else:
        await update.message.reply_text("❌ Введите корректный вес!")
        return ConversationHandler.END

# Обработка добавления ассортимента (цена)
async def process_add_assortment_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    try:
        price = int(update.message.text)
        name = context.user_data.get("new_assortment_name")
        weight = context.user_data.get("new_assortment_weight")
        if price >= 0 and name and weight:
            execute_db("INSERT INTO games (name, weight, category_id) VALUES (?, ?, ?)", (name, weight, None))
            game_id = get_db_single("SELECT id FROM games WHERE name = ? AND weight = ?", (name, weight))[0]
            execute_db("INSERT INTO products (game_id, name, price, code) VALUES (?, ?, ?, ?)", (game_id, name, price, "DEFAULT_CODE"))
            await update.message.reply_text(f"✅ Элемент ассортимента {name} [{weight}] [{price} руб.] добавлен.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="manage_assortment")]]))
            context.user_data.pop("new_assortment_name", None)
            context.user_data.pop("new_assortment_weight", None)
        else:
            await update.message.reply_text("❌ Ошибка при добавлении элемента!")
    except ValueError:
        await update.message.reply_text("❌ Введите корректную цену (целое число)!")
    return ConversationHandler.END

# Обработка редактирования ассортимента (название)
async def process_edit_assortment_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    name = update.message.text.strip()
    if name:
        context.user_data["edit_assortment_name"] = name
        await update.message.reply_text("Введите новый вес элемента:")
        return EDIT_ASSORTMENT_WEIGHT
    else:
        await update.message.reply_text("❌ Введите корректное название товара!")
        return ConversationHandler.END

# Обработка редактирования ассортимента (вес)
async def process_edit_assortment_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    weight = update.message.text.strip()
    if weight:
        context.user_data["edit_assortment_weight"] = weight
        await update.message.reply_text("Введите новую цену элемента (в рублях):")
        return EDIT_ASSORTMENT_PRICE
    else:
        await update.message.reply_text("❌ Введите корректный вес!")
        return ConversationHandler.END

# Обработка редактирования ассортимента (цена)
async def process_edit_assortment_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    try:
        price = int(update.message.text)
        game_id = context.user_data.get("game_id")
        name = context.user_data.get("edit_assortment_name")
        weight = context.user_data.get("edit_assortment_weight")
        if price >= 0 and game_id and name and weight:
            execute_db("UPDATE games SET name = ?, weight = ? WHERE id = ?", (name, weight, game_id))
            execute_db("UPDATE products SET price = ? WHERE game_id = ?", (price, game_id))
            await update.message.reply_text(f"✅ Ассортимент обновлен: {name} [{weight}] [{price} руб].", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="manage_assortment")]]))
            context.user_data.pop("edit_assortment_name", None)
            context.user_data.pop("edit_assortment_weight", None)
            return ConversationHandler.END
        else:
            await update.message.reply_text("❌ Ошибка при редактировании элемента! Убедитесь, что все данные введены корректно.")
            return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Введите корректную цену (целое число)! Повторите попытку:")
        return EDIT_ASSORTMENT_PRICE

# Обработка поиска по Telegram ID
async def process_search_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    try:
        chat_id = int(update.message.text)
        user_data = get_db_single("SELECT system_id, balance, role, banned FROM users WHERE id = ?", (chat_id,))
        if user_data:
            system_id, balance, role, banned = user_data
            status = "🟢" if not banned else "🔴"
            name = context.bot.get_chat(chat_id).first_name or "Без имени"
            role_display = {"client": "Клиент", "courier": "Курьер", "admin": "Админ", "operator": "Оператор"}.get(role, "Клиент")
            msg = f"Кое-кого нашли:\n{status} [{role_display}] {name} [{balance} руб.]\nSystem ID: {system_id}"
            keyboard = [[InlineKeyboardButton("Назад", callback_data="view_users")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Такого пользователя нет в базе, пусть он авторизируется в боте.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
    except ValueError:
        await update.message.reply_text("❌ Введите корректный Telegram ID!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
    return ConversationHandler.END

# Обработка поиска по System ID
async def process_search_system_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    try:
        system_id = int(update.message.text)
        user_data = get_db_single("SELECT id, balance, role, banned FROM users WHERE system_id = ?", (system_id,))
        if user_data:
            chat_id, balance, role, banned = user_data
            status = "🟢" if not banned else "🔴"
            name = context.bot.get_chat(chat_id).first_name or "Без имени"
            role_display = {"client": "Клиент", "courier": "Курьер", "admin": "Админ", "operator": "Оператор"}.get(role, "Клиент")
            msg = f"Кое-кого нашли:\n{status} [{role_display}] {name} [{balance} руб.]\nSystem ID: {system_id}"
            keyboard = [[InlineKeyboardButton("Назад", callback_data="view_users")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Такого пользователя нет в базе, пусть он авторизируется в боте.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
    except ValueError:
        await update.message.reply_text("❌ Введите корректный System ID (7 цифр)!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
    return ConversationHandler.END

# Обработка поиска по username
async def process_search_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    username = update.message.text.strip()
    if not username.startswith("@"):
        username = "@" + username
    try:
        chat = context.bot.get_chat(username)
        user_data = get_db_single("SELECT system_id, balance, role, banned FROM users WHERE id = ?", (chat.id,))
        if user_data:
            system_id, balance, role, banned = user_data
            status = "🟢" if not banned else "🔴"
            name = chat.first_name or "Без имени"
            role_display = {"client": "Клиент", "courier": "Курьер", "admin": "Админ", "operator": "Оператор"}.get(role, "Клиент")
            msg = f"Кое-кого нашли:\n{status} [{role_display}] {name} [{balance} руб.]\nSystem ID: {system_id}"
            keyboard = [[InlineKeyboardButton("Назад", callback_data="view_users")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("Такого пользователя нет в базе, пусть он авторизируется в боте.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
    except:
        await update.message.reply_text("❌ Пользователь с таким username не найден!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_users")]]))
    return ConversationHandler.END

# Обработка ответа на тикет
async def process_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    request_id = context.user_data.get("request_id")
    reply_text = update.message.text.strip()
    if request_id and reply_text:
        ticket = get_db_single("SELECT user_id FROM support_requests WHERE request_id = ?", (request_id,))
        if ticket:
            await context.bot.send_message(ticket[0], f"Ответ на ваш тикет #{request_id}:\n{reply_text}")
            execute_db("UPDATE support_requests SET status = 'replied' WHERE request_id = ?", (request_id,))
            await update.message.reply_text("✅ Ответ отправлен.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="view_support")]]))
    return ConversationHandler.END

# Обработка установки PIN-кода
async def process_set_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    pin = update.message.text.strip()
    if pin.isdigit() and len(pin) == 4:
        execute_db("UPDATE users SET pin = ? WHERE id = ?", (pin, user_id))
        await update.message.reply_text("✅ PIN-код установлен.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_settings")]]))
    else:
        await update.message.reply_text("❌ Введите корректный PIN-код (4 цифры)!")
    return ConversationHandler.END

# Обработка добавления промокода
async def process_add_promo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    promo_code = update.message.text.strip()
    if promo_code:
        execute_db("INSERT INTO promo_codes (code, discount) VALUES (?, 10)", (promo_code,))
        await update.message.reply_text(f"✅ Промокод {promo_code} добавлен с скидкой 10%.", 
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_promotions")]]))
    else:
        await update.message.reply_text("❌ Введите корректный промокод!")
    return ConversationHandler.END

# Обработка добавления товара
async def process_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or update.message.text.startswith('/'):
        return ConversationHandler.END
    product_data = update.message.text.strip()
    try:
        name, price, code = product_data.split(',')
        price = float(price.strip())
        games = get_db_data("SELECT id, name FROM games")
        if not games:
            await update.message.reply_text("❌ Сначала добавьте элементы ассортимента в разделе 'Управление ассортиментом'!", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="admin_store")]]))
            return ConversationHandler.END
        keyboard = [[InlineKeyboardButton(game[1], callback_data=f"add_prod_to_{game[0]}")] for game in games]
        keyboard.append([InlineKeyboardButton("Назад", callback_data="admin_store")])
        context.user_data["new_product"] = {"name": name.strip(), "price": price, "code": code.strip()}
        await update.message.reply_text(f"Вы добавляете товар: {name} ({price} руб.)\nВыберите элемент ассортимента:", 
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return ADD_PRODUCT
    except ValueError:
        await update.message.reply_text("❌ Формат: название, цена, код (например: 'Ключ Steam, 100, ABC123')")
        return ConversationHandler.END

# Обработка пополнения баланса
async def process_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if update.message.text.startswith('/'):
        return ConversationHandler.END
    try:
        amount = float(update.message.text)
        if amount > 0:
            request_id = random.randint(1000, 9999)
            execute_db("INSERT INTO deposit_requests (user_id, amount, status) VALUES (?, ?, 'pending')", (user_id, amount))
            await update.message.reply_text(f"Заявка на пополнение #{request_id} на сумму {amount} руб. создана.\nОжидайте подтверждения.", 
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="profile")]]))
        else:
            await update.message.reply_text("❌ Введите сумму больше 0!")
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму!")
    return ConversationHandler.END

# Обновление system_id для существующих пользователей
def update_system_ids():
    users = get_db_data("SELECT id, system_id FROM users")
    existing_ids = [user[1] for user in users]
    for user_id, old_system_id in users:
        if len(str(old_system_id)) > 7:  # Если ID длиннее 7 цифр
            new_system_id = generate_system_id(existing_ids)
            execute_db("UPDATE users SET system_id = ? WHERE id = ?", (new_system_id, user_id))
            existing_ids.append(new_system_id)

# Основная функция
def main() -> None:
    update_system_ids()  # Обновляем system_id до 7 цифр
    init_db()
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            CATEGORY: [CallbackQueryHandler(button)],
            GAME: [CallbackQueryHandler(button)],
            PRODUCT: [CallbackQueryHandler(button)],
            DEPOSIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_deposit)],
            PROMO: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_promo)],
            SUPPORT: [CallbackQueryHandler(button)],
            ADD_PRODUCT: [CallbackQueryHandler(button)],
            ADD_PROMO: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_promo)],
            REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_reply)],
            SET_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_set_pin)],
            MANAGE_CITIES: [CallbackQueryHandler(button)],
            ADD_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_city)],
            EDIT_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_city)],
            MANAGE_ASSORTMENT: [CallbackQueryHandler(button)],
            ADD_ASSORTMENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_assortment_name)],
            ADD_ASSORTMENT_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_assortment_weight)],
            ADD_ASSORTMENT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_assortment_price)],
            EDIT_ASSORTMENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_assortment_name)],
            EDIT_ASSORTMENT_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_assortment_weight)],
            EDIT_ASSORTMENT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_assortment_price)],
            MANAGE_USERS: [CallbackQueryHandler(button)],
            SEARCH_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_search_chat)],
            SEARCH_SYSTEM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_search_system_id)],
            SEARCH_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_search_username)],
            MANAGE_DISTRICTS: [CallbackQueryHandler(button)],
            ADD_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_city)],
            USER_PROFILE: [CallbackQueryHandler(button)]
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()