import telebot
from telebot import types
import time
import sys
import re
import json
import os
import threading
import signal
import random
import string
import hashlib
from datetime import datetime, timedelta, date
from collections import defaultdict
from flask import Flask
import logging

# Конфигурация
BOT_TOKEN = '8713048190:AAEl8bPf1B89oOZhx3b9YO-ZuYvoHtELw4o'

# ID администраторов
ADMIN_IDS = [
    5712848734,
    380140985
]

# ID группы для чата поддержки
SUPPORT_GROUP_ID = -1003555288051

bot = telebot.TeleBot(BOT_TOKEN)

# Словари для хранения данных
user_data = {}
question_user_map = {}
admin_reply_data = {}

# Статистика
stats = {
    'total_questions': 0,
    'answered_questions': 0,
    'total_appointments': 0,
    'users': set()
}

# Файл для сохранения данных
DATA_FILE = 'bot_data.json'
BOT_RUNNING = True

# Создаем Flask приложение
app = Flask(__name__)

# Отключаем лишние логи Flask
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "🤖 Бот автосервиса работает!", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/stats')
def stats_page():
    return f"""
    <html>
        <head><title>Статус бота</title></head>
        <body style="font-family: Arial; padding: 20px;">
            <h1>🤖 Бот автосервиса</h1>
            <p>✅ Бот работает</p>
            <p>📊 Пользователей: {len(stats['users'])}</p>
            <p>❓ Активных вопросов: {len(question_user_map)}</p>
            <p>📝 Всего записей: {stats['total_appointments']}</p>
            <p>⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        </body>
    </html>
    """, 200

def run_flask():
    """Запускает Flask сервер в отдельном потоке"""
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# Загружаем сохраненные данные
def load_data():
    global question_user_map, stats
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                question_user_map = {k: v for k, v in data.get('questions', {}).items()}
                stats = data.get('stats', {
                    'total_questions': 0,
                    'answered_questions': 0,
                    'total_appointments': 0,
                    'users': []
                })
                stats['users'] = set(stats.get('users', []))
                print(f"✅ Загружены данные: {len(question_user_map)} активных вопросов, {len(stats['users'])} пользователей")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки данных: {e}")

# Сохраняем данные
def save_data():
    try:
        data = {
            'questions': question_user_map,
            'stats': {
                'total_questions': stats['total_questions'],
                'answered_questions': stats['answered_questions'],
                'total_appointments': stats['total_appointments'],
                'users': list(stats['users'])
            }
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Данные сохранены ({datetime.now().strftime('%H:%M:%S')})")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения данных: {e}")

# Загружаем данные
load_data()

# Каталог услуг
SERVICES_CATALOG = [
    "🔧 ТО автомобиля",
    "🔩 Ремонт передней подвески",
    "🔩 Ремонт задней подвески",
    "⚙️ Ремонт рулевого управления",
    "🛑 Ремонт тормозной системы",
    "⚙️ Ремонт трансмиссии",
    "❄️ Ремонт системы охлаждения",
    "🔥 Ремонт двигателя",
    "⚡ Автоэлектрика",
    "⛽ Ремонт топливной системы",
    "❓ Задать вопрос"
]

# Доступное время
AVAILABLE_TIMES = [
    "09:00", "10:00", "11:00", "12:00", "13:00", 
    "14:00", "15:00", "16:00", "17:00", "18:00"
]

# Создание клавиатур
def create_main_menu(is_admin_user=False):
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu.add(
        types.KeyboardButton("🔧 Услуги"),
        types.KeyboardButton("📍 Адреса"),
        types.KeyboardButton("📝 Записаться")
    )
    if is_admin_user:
        menu.add(types.KeyboardButton("👑 Админ панель"))
    return menu

def create_back_button():
    back = types.ReplyKeyboardMarkup(resize_keyboard=True)
    back.add(types.KeyboardButton("◀️ Назад"))
    return back

def get_services_keyboard():
    services_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(service) for service in SERVICES_CATALOG]
    services_keyboard.add(*buttons)
    services_keyboard.add(types.KeyboardButton("◀️ Назад"))
    return services_keyboard

def get_dates_keyboard():
    dates_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = []
    today = date.today()
    for i in range(7):
        current_date = today + timedelta(days=i)
        if i == 0:
            date_text = f"📅 Сегодня ({current_date.strftime('%d.%m')})"
        elif i == 1:
            date_text = f"📅 Завтра ({current_date.strftime('%d.%m')})"
        else:
            date_text = f"📅 {current_date.strftime('%d.%m.%Y')}"
        buttons.append(types.KeyboardButton(date_text))
    dates_keyboard.add(*buttons)
    dates_keyboard.add(types.KeyboardButton("◀️ Назад"))
    return dates_keyboard

def get_time_keyboard():
    time_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = [types.KeyboardButton(f"🕐 {time_slot}") for time_slot in AVAILABLE_TIMES]
    time_keyboard.add(*buttons)
    time_keyboard.add(types.KeyboardButton("◀️ Назад"))
    return time_keyboard

def get_phone_keyboard():
    phone_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    phone_keyboard.add(
        types.KeyboardButton("📱 Отправить номер телефона", request_contact=True),
        types.KeyboardButton("◀️ Назад")
    )
    return phone_keyboard

def get_vin_choice_keyboard():
    vin_choice_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    vin_choice_keyboard.add(
        types.KeyboardButton("✅ Да, указать VIN"),
        types.KeyboardButton("❌ Нет, продолжить без VIN"),
        types.KeyboardButton("◀️ Назад")
    )
    return vin_choice_keyboard

def get_answer_keyboard(question_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("✏️ Ответить на вопрос", callback_data=f"answer_{question_id}"),
        types.InlineKeyboardButton("👀 Просмотреть вопрос", callback_data=f"view_{question_id}")
    )
    return keyboard

def get_admin_panel_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("❓ Активные вопросы", callback_data="admin_questions")
    )
    keyboard.add(
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("💾 Резервное копирование", callback_data="admin_backup")
    )
    keyboard.add(
        types.InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh"),
        types.InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")
    )
    return keyboard

# Вспомогательные функции
def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_all_users():
    return list(stats['users'])

def notify_admins(message_text, question_id=None, parse_mode=None):
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, message_text, parse_mode=parse_mode)
        except Exception as e:
            print(f"❌ Не удалось отправить уведомление админу {admin_id}: {e}")
    
    if SUPPORT_GROUP_ID:
        try:
            if question_id:
                bot.send_message(
                    SUPPORT_GROUP_ID, 
                    message_text,
                    reply_markup=get_answer_keyboard(question_id),
                    parse_mode=parse_mode
                )
            else:
                bot.send_message(SUPPORT_GROUP_ID, message_text, parse_mode=parse_mode)
        except Exception as e:
            print(f"❌ Не удалось отправить уведомление в группу: {e}")

def clear_user_data(user_id):
    if user_id in user_data:
        del user_data[user_id]

def extract_date_from_button(button_text):
    if "Сегодня" in button_text:
        return date.today()
    elif "Завтра" in button_text:
        return date.today() + timedelta(days=1)
    else:
        date_str = button_text.replace("📅 ", "").strip()
        try:
            return datetime.strptime(date_str, "%d.%m.%Y").date()
        except:
            return None

def format_time(seconds):
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    if days > 0:
        return f"{days} дн. {hours % 24} ч."
    elif hours > 0:
        return f"{hours} ч. {minutes % 60} мин."
    elif minutes > 0:
        return f"{minutes} мин."
    else:
        return f"{seconds} сек."

def log_error(error_msg):
    """Логирование ошибок"""
    try:
        with open('error_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now()}: {error_msg}\n")
    except:
        pass

# Обработчики команд
@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = message.from_user.id
    
    # Добавляем пользователя в статистику
    stats['users'].add(user_id)
    save_data()
    
    if message.chat.type in ['group', 'supergroup']:
        bot.send_message(
            message.chat.id,
            "👋 Привет! Я бот автосервиса.\n"
            "Для личного общения напишите мне в личные сообщения."
        )
        return
    
    welcome_text = (
        "🚗 Добро пожаловать в автосервис!\n\n"
        "Мы предлагаем полный спектр услуг по ремонту и обслуживанию автомобилей.\n"
        "Воспользуйтесь кнопками меню для навигации."
    )
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=create_main_menu(is_admin(user_id))
    )

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды.")
        return
    
    show_admin_panel(message.chat.id)

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды.")
        return
    
    show_stats(message)

@bot.message_handler(commands=['questions'])
def questions_command(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды.")
        return
    
    list_questions(message)

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды.")
        return
    
    msg = bot.send_message(
        message.chat.id,
        "📢 Введите сообщение для рассылки всем пользователям:\n"
        f"(Всего пользователей: {len(get_all_users())})",
        reply_markup=create_back_button()
    )
    bot.register_next_step_handler(msg, process_broadcast)

@bot.message_handler(commands=['ping'])
def ping(message):
    """Команда для проверки работоспособности"""
    bot.reply_to(message, "pong 🏓")

@bot.message_handler(commands=['myid'])
def send_id(message):
    user_id = message.from_user.id
    admin_status = "✅ Вы администратор" if is_admin(user_id) else "❌ Вы не администратор"
    bot.send_message(
        message.chat.id, 
        f"👤 Ваш Chat ID: {user_id}\n"
        f"{admin_status}\n"
        f"📱 Username: @{message.from_user.username if message.from_user.username else 'нет'}\n"
        f"📝 Chat type: {message.chat.type}",
        reply_markup=create_main_menu(is_admin(user_id))
    )

@bot.message_handler(commands=['admins'])
def admins_list(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды.")
        return
    
    admins_text = "👑 Список администраторов:\n\n"
    for i, admin_id in enumerate(ADMIN_IDS, 1):
        admins_text += f"{i}. ID: {admin_id}\n"
    
    bot.send_message(message.chat.id, admins_text)

def process_broadcast(message):
    if message.text == "◀️ Назад":
        bot.send_message(
            message.chat.id, 
            "🏠 Рассылка отменена.", 
            reply_markup=create_main_menu(True)
        )
        return
    
    broadcast_text = message.text
    users = get_all_users()
    
    if not users:
        bot.send_message(message.chat.id, "❌ Нет пользователей для рассылки.")
        return
    
    # Отправляем подтверждение
    status_msg = bot.send_message(
        message.chat.id,
        f"📢 Начинаю рассылку {len(users)} пользователям...\n"
        f"Это может занять некоторое время.",
        reply_markup=create_main_menu(True)
    )
    
    success = 0
    failed = 0
    failed_users = []
    
    # Отправляем сообщение всем пользователям
    for user_id in users:
        try:
            bot.send_message(
                user_id,
                f"📢 РАССЫЛКА ОТ АДМИНИСТРАЦИИ\n\n"
                f"{broadcast_text}\n\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Чтобы отписаться от рассылки, свяжитесь с администратором."
            )
            success += 1
            
            # Обновляем статус каждые 10 сообщений
            if success % 10 == 0:
                try:
                    bot.edit_message_text(
                        f"📢 Рассылка в процессе...\n"
                        f"✅ Отправлено: {success}\n"
                        f"❌ Ошибок: {failed}\n"
                        f"⏳ Осталось: {len(users) - success - failed}",
                        status_msg.chat.id,
                        status_msg.message_id
                    )
                except:
                    pass
            
            time.sleep(0.05)  # Небольшая задержка
        except Exception as e:
            failed += 1
            failed_users.append(str(user_id))
            print(f"❌ Ошибка отправки пользователю {user_id}: {e}")
    
    # Отправляем итоговый отчет
    result_text = (
        f"✅ Рассылка завершена!\n\n"
        f"📊 Статистика:\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📨 Всего пользователей: {len(users)}\n"
        f"✅ Успешно отправлено: {success}\n"
        f"❌ Не удалось отправить: {failed}\n"
        f"━━━━━━━━━━━━━━━"
    )
    
    if failed_users:
        result_text += f"\n\n❌ ID пользователей с ошибкой:\n{', '.join(failed_users[:10])}"
        if len(failed_users) > 10:
            result_text += f"\n... и еще {len(failed_users) - 10}"
    
    bot.send_message(message.chat.id, result_text)
    
    # Сохраняем историю рассылки
    broadcast_history = {
        'admin': message.from_user.id,
        'admin_name': message.from_user.username or message.from_user.first_name,
        'text': broadcast_text,
        'time': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
        'total': len(users),
        'success': success,
        'failed': failed
    }
    
    try:
        history_file = 'broadcast_history.json'
        history = []
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        history.append(broadcast_history)
        
        # Оставляем только последние 50 записей
        if len(history) > 50:
            history = history[-50:]
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except:
        pass

@bot.message_handler(commands=['backup'])
def backup_command(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды.")
        return
    
    try:
        backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        backup_data = {
            'questions': question_user_map,
            'stats': {
                'total_questions': stats['total_questions'],
                'answered_questions': stats['answered_questions'],
                'total_appointments': stats['total_appointments'],
                'users': list(stats['users'])
            },
            'backup_time': datetime.now().strftime('%d.%m.%Y %H:%M:%S'),
            'version': '1.0'
        }
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        with open(backup_file, 'rb') as f:
            bot.send_document(
                message.chat.id, 
                f,
                caption=f"📦 Резервная копия от {backup_data['backup_time']}"
            )
        
        os.remove(backup_file)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка создания резервной копии: {e}")

# Обработчики кнопок меню
@bot.message_handler(func=lambda message: message.text == "🔧 Услуги")
def services_handler(message):
    if message.chat.type != 'private':
        return
    
    text = "🔧 НАШИ УСЛУГИ:\n\n" + "\n".join(SERVICES_CATALOG)
    bot.send_message(message.chat.id, text, reply_markup=create_back_button())

@bot.message_handler(func=lambda message: message.text == "📍 Адреса")
def address_handler(message):
    if message.chat.type != 'private':
        return
    
    text = (
        "📍 НАШ АДРЕС:\n\n"
        "🏢 Чечёрский пр., вл5Ас1, Москва\n"
        "🕒 Работаем ежедневно с 9:00 до 19:00\n\n"
        "📞 Телефон: +7 (XXX) XXX-XX-XX\n\n"
        "🗺️ Схема проезда: https://yandex.ru/maps/-/CPu4Z04f"
    )
    bot.send_message(message.chat.id, text, reply_markup=create_back_button())

@bot.message_handler(func=lambda message: message.text == "📝 Записаться")
def sign_up_handler(message):
    if message.chat.type != 'private':
        bot.send_message(
            message.chat.id, 
            "Для записи напишите мне в личные сообщения."
        )
        return
    
    user_id = message.from_user.id
    user_data[user_id] = {'step': 'name'}
    
    bot.send_message(
        message.chat.id, 
        "📝 ДАВАЙТЕ ЗАПОЛНИМ ЗАЯВКУ\n\n"
        "Введите ваше имя:",
        reply_markup=create_back_button()
    )
    bot.register_next_step_handler(message, process_name)

@bot.message_handler(func=lambda message: message.text == "👑 Админ панель")
def admin_panel_button(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав для этой команды.")
        return
    
    show_admin_panel(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "◀️ Назад")
def back_handler(message):
    user_id = message.from_user.id
    
    if user_id in user_data:
        current_step = user_data[user_id].get('step')
        
        if current_step == 'service':
            clear_user_data(user_id)
            bot.send_message(
                message.chat.id, 
                "🏠 Главное меню:", 
                reply_markup=create_main_menu(is_admin(user_id))
            )
        elif current_step == 'date':
            user_data[user_id]['step'] = 'service'
            bot.send_message(
                message.chat.id,
                "📋 ВЫБЕРИТЕ УСЛУГУ ИЗ СПИСКА:",
                reply_markup=get_services_keyboard()
            )
        elif current_step == 'time':
            user_data[user_id]['step'] = 'date'
            bot.send_message(
                message.chat.id,
                "📅 ВЫБЕРИТЕ ДАТУ ЗАПИСИ:",
                reply_markup=get_dates_keyboard()
            )
        elif current_step == 'vin_choice':
            user_data[user_id]['step'] = 'time'
            bot.send_message(
                message.chat.id,
                "🕐 ВЫБЕРИТЕ УДОБНОЕ ВРЕМЯ:",
                reply_markup=get_time_keyboard()
            )
        elif current_step == 'vin':
            user_data[user_id]['step'] = 'vin_choice'
            bot.send_message(
                message.chat.id,
                "🔢 ХОТИТЕ УКАЗАТЬ VIN НОМЕР АВТОМОБИЛЯ?",
                reply_markup=get_vin_choice_keyboard()
            )
        elif current_step == 'phone':
            user_data[user_id]['step'] = 'vin_choice'
            bot.send_message(
                message.chat.id,
                "🔢 ХОТИТЕ УКАЗАТЬ VIN НОМЕР АВТОМОБИЛЯ?",
                reply_markup=get_vin_choice_keyboard()
            )
        elif current_step in ['question_phone', 'question_text']:
            user_data[user_id]['step'] = 'service'
            bot.send_message(
                message.chat.id,
                "📋 ВЫБЕРИТЕ УСЛУГУ ИЗ СПИСКА:",
                reply_markup=get_services_keyboard()
            )
        else:
            clear_user_data(user_id)
            bot.send_message(
                message.chat.id, 
                "🏠 Главное меню:", 
                reply_markup=create_main_menu(is_admin(user_id))
            )
    else:
        bot.send_message(
            message.chat.id, 
            "🏠 Главное меню:", 
            reply_markup=create_main_menu(is_admin(user_id))
        )

# Процессы записи
def process_name(message):
    user_id = message.from_user.id
    
    if message.text == "◀️ Назад":
        clear_user_data(user_id)
        back_handler(message)
        return
    
    user_data[user_id]['name'] = message.text
    user_data[user_id]['step'] = 'service'
    
    bot.send_message(
        message.chat.id,
        f"✅ Имя сохранено: {message.text}\n\n"
        f"📋 ВЫБЕРИТЕ УСЛУГУ ИЗ СПИСКА:",
        reply_markup=get_services_keyboard()
    )

@bot.message_handler(func=lambda message: message.text in SERVICES_CATALOG)
def handle_service_selection(message):
    user_id = message.from_user.id
    
    if message.chat.type != 'private':
        return
    
    if user_id not in user_data or user_data[user_id].get('step') != 'service':
        bot.send_message(
            message.chat.id, 
            "Пожалуйста, начните запись с кнопки 'Записаться'", 
            reply_markup=create_main_menu(is_admin(user_id))
        )
        return
    
    user_data[user_id]['service'] = message.text
    user_data[user_id]['step'] = 'date'
    
    if message.text == "❓ Задать вопрос":
        user_data[user_id]['step'] = 'question_phone'
        bot.send_message(
            message.chat.id,
            "📱 Для связи с вами, укажите ваш номер телефона.\n"
            "Вы можете нажать кнопку или ввести номер вручную:",
            reply_markup=get_phone_keyboard()
        )
        return
    
    bot.send_message(
        message.chat.id,
        f"✅ Услуга выбрана: {message.text}\n\n"
        f"📅 ВЫБЕРИТЕ ДАТУ ЗАПИСИ:",
        reply_markup=get_dates_keyboard()
    )

@bot.message_handler(func=lambda message: message.text and message.text.startswith("📅"))
def handle_date_selection(message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('step') != 'date':
        bot.send_message(
            message.chat.id, 
            "Пожалуйста, начните запись с кнопки 'Записаться'", 
            reply_markup=create_main_menu(is_admin(user_id))
        )
        return
    
    selected_date = extract_date_from_button(message.text)
    if selected_date:
        user_data[user_id]['date'] = selected_date.strftime("%d.%m.%Y")
        user_data[user_id]['step'] = 'time'
        
        bot.send_message(
            message.chat.id,
            f"✅ Дата выбрана: {user_data[user_id]['date']}\n\n"
            f"🕐 ВЫБЕРИТЕ УДОБНОЕ ВРЕМЯ:",
            reply_markup=get_time_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Не удалось распознать дату. Пожалуйста, выберите дату из списка:",
            reply_markup=get_dates_keyboard()
        )

@bot.message_handler(func=lambda message: message.text and message.text.startswith("🕐"))
def handle_time_selection(message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('step') != 'time':
        bot.send_message(
            message.chat.id, 
            "Пожалуйста, начните запись с кнопки 'Записаться'", 
            reply_markup=create_main_menu(is_admin(user_id))
        )
        return
    
    time_str = message.text.replace("🕐 ", "")
    user_data[user_id]['time'] = time_str
    user_data[user_id]['datetime'] = f"{user_data[user_id]['date']} {time_str}"
    user_data[user_id]['step'] = 'vin_choice'
    
    bot.send_message(
        message.chat.id,
        f"✅ Время выбрано: {time_str}\n\n"
        f"🔢 ХОТИТЕ УКАЗАТЬ VIN НОМЕР АВТОМОБИЛЯ?\n"
        f"(Это поможет нам лучше подготовиться к ремонту)",
        reply_markup=get_vin_choice_keyboard()
    )

@bot.message_handler(func=lambda message: message.text in ["✅ Да, указать VIN", "❌ Нет, продолжить без VIN"])
def handle_vin_choice(message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('step') != 'vin_choice':
        bot.send_message(
            message.chat.id, 
            "Пожалуйста, начните запись с кнопки 'Записаться'", 
            reply_markup=create_main_menu(is_admin(user_id))
        )
        return
    
    if message.text == "✅ Да, указать VIN":
        user_data[user_id]['step'] = 'vin'
        bot.send_message(
            message.chat.id,
            f"🔢 ВВЕДИТЕ VIN НОМЕР АВТОМОБИЛЯ:\n"
            f"(17 символов, например: WVWZZZ3CZ9P012345)",
            reply_markup=create_back_button()
        )
        bot.register_next_step_handler(message, process_vin)
    else:
        user_data[user_id]['vin'] = "Не указан"
        user_data[user_id]['step'] = 'phone'
        bot.send_message(
            message.chat.id,
            f"📱 ТЕПЕРЬ УКАЖИТЕ ВАШ НОМЕР ТЕЛЕФОНА.\n"
            f"Вы можете нажать кнопку или ввести номер вручную:",
            reply_markup=get_phone_keyboard()
        )

def process_vin(message):
    user_id = message.from_user.id
    
    if message.text == "◀️ Назад":
        user_data[user_id]['step'] = 'vin_choice'
        bot.send_message(
            message.chat.id,
            "🔢 ХОТИТЕ УКАЗАТЬ VIN НОМЕР АВТОМОБИЛЯ?",
            reply_markup=get_vin_choice_keyboard()
        )
        return
    
    vin = message.text.upper()
    if len(vin) != 17:
        bot.send_message(
            message.chat.id,
            "❌ VIN номер должен содержать 17 символов.\n"
            "Пожалуйста, введите корректный VIN:",
            reply_markup=create_back_button()
        )
        bot.register_next_step_handler(message, process_vin)
        return
    
    user_data[user_id]['vin'] = vin
    user_data[user_id]['step'] = 'phone'
    
    bot.send_message(
        message.chat.id,
        f"✅ VIN номер сохранен: {vin}\n\n"
        f"📱 ТЕПЕРЬ УКАЖИТЕ ВАШ НОМЕР ТЕЛЕФОНА.\n"
        f"Вы можете нажать кнопку или ввести номер вручную:",
        reply_markup=get_phone_keyboard()
    )

@bot.message_handler(content_types=['contact'])
def handle_contact(message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        return
    
    step = user_data[user_id].get('step')
    phone = message.contact.phone_number
    
    if step == 'question_phone':
        user_data[user_id]['phone'] = phone
        user_data[user_id]['step'] = 'question_text'
        bot.send_message(
            message.chat.id,
            f"✅ Спасибо! Теперь напишите ваш вопрос:",
            reply_markup=create_back_button()
        )
        bot.register_next_step_handler(message, process_question_text)
    
    elif step == 'phone':
        user_data[user_id]['phone'] = phone
        finalize_sign_up(message, user_id)

def process_question_text(message):
    user_id = message.from_user.id
    
    if message.text == "◀️ Назад":
        user_data[user_id]['step'] = 'question_phone'
        bot.send_message(
            message.chat.id,
            "📱 Укажите ваш номер телефона:",
            reply_markup=get_phone_keyboard()
        )
        return
    
    process_question_final(message, user_id, message.text)

def process_question_final(message, user_id, question_text):
    user_name = user_data[user_id].get('name', 'Не указано')
    phone = user_data[user_id].get('phone', 'Не указан')
    
    question_id = f"Q{int(time.time())}_{user_id}"
    
    question_user_map[question_id] = {
        'user_id': user_id,
        'user_name': user_name,
        'phone': phone,
        'question': question_text,
        'time': datetime.now().strftime('%d.%m.%Y %H:%M'),
        'status': 'new'
    }
    
    stats['total_questions'] += 1
    save_data()
    
    bot.send_message(
        message.chat.id,
        "✅ Ваш вопрос отправлен администратору!\n"
        "Ответ придет в ближайшее время.\n\n"
        f"📋 Номер вопроса: {question_id}",
        reply_markup=create_main_menu(is_admin(user_id))
    )
    
    admin_notification = (
        f"❓ НОВЫЙ ВОПРОС #{question_id}\n\n"
        f"👤 Имя: {user_name}\n"
        f"🆔 ID: {user_id}\n"
        f"📞 Телефон: {phone}\n\n"
        f"📝 ВОПРОС:\n{question_text}\n\n"
        f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    notify_admins(admin_notification, question_id)
    clear_user_data(user_id)

def finalize_sign_up(message, user_id):
    data = user_data[user_id]
    user_name = message.from_user.first_name
    username = message.from_user.username
    
    stats['total_appointments'] += 1
    save_data()
    
    details = (
        f"👤 Имя: {data['name']}\n"
        f"🔧 Услуга: {data['service']}\n"
        f"📅 Дата: {data['date']}\n"
        f"🕐 Время: {data['time']}\n"
        f"🔢 VIN: {data['vin']}\n"
        f"📞 Телефон: {data['phone']}"
    )
    
    confirmation = (
        f"✅ СПАСИБО, {data['name']}!\n\n"
        f"📋 ВАША ЗАЯВКА ПРИНЯТА:\n{details}\n\n"
        f"📞 Администратор свяжется с вами для подтверждения записи.\n\n"
        f"📍 Наш адрес: вл. 5А, строение 1, Чечерский пр., Москва"
    )
    
    bot.send_message(
        message.chat.id, 
        confirmation, 
        reply_markup=create_main_menu(is_admin(user_id))
    )
    
    admin_notification = (
        f"🔔 НОВАЯ ЗАПИСЬ!\n\n"
        f"👤 Клиент: {data['name']}\n"
        f"🆔 ID: {user_id}\n"
        f"📱 Username: @{username if username else 'нет'}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"📝 ДЕТАЛИ ЗАПИСИ:\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔧 Услуга: {data['service']}\n"
        f"📅 Дата: {data['date']}\n"
        f"🕐 Время: {data['time']}\n"
        f"🔢 VIN: {data['vin']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⏰ Время заявки: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    notify_admins(admin_notification)
    clear_user_data(user_id)

# Inline кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data.startswith('answer_'):
        handle_answer_callback(call)
    elif call.data.startswith('view_'):
        handle_view_callback(call)
    elif call.data == 'admin_stats':
        show_stats(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == 'admin_questions':
        list_questions(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == 'admin_broadcast':
        bot.send_message(
            call.from_user.id,
            f"📢 Введите сообщение для рассылки всем пользователям:\n"
            f"(Всего пользователей: {len(get_all_users())})",
            reply_markup=create_back_button()
        )
        bot.answer_callback_query(call.id)
    elif call.data == 'admin_backup':
        backup_command(call.message)
        bot.answer_callback_query(call.id)
    elif call.data == 'admin_refresh':
        bot.edit_message_text(
            "👑 АДМИН-ПАНЕЛЬ\n\nВыберите действие:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_admin_panel_keyboard()
        )
        bot.answer_callback_query(call.id, "🔄 Панель обновлена")
    elif call.data == 'admin_close':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "❌ Панель закрыта")

def show_admin_panel(chat_id):
    admin_text = (
        "👑 АДМИН-ПАНЕЛЬ\n\n"
        f"📊 Всего пользователей: {len(get_all_users())}\n"
        f"❓ Активных вопросов: {len(question_user_map)}\n"
        f"📝 Всего записей: {stats['total_appointments']}\n\n"
        f"Выберите действие:"
    )
    bot.send_message(
        chat_id,
        admin_text,
        reply_markup=get_admin_panel_keyboard()
    )

def show_stats(message):
    active_questions = len(question_user_map)
    total_users = len(stats['users'])
    
    stats_text = (
        "📊 СТАТИСТИКА БОТА\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"❓ Всего вопросов: {stats['total_questions']}\n"
        f"✅ Отвечено вопросов: {stats['answered_questions']}\n"
        f"📝 Всего записей: {stats['total_appointments']}\n"
        f"🕐 Активных вопросов: {active_questions}\n"
    )
    
    if active_questions > 0:
        stats_text += "\n📋 Активные вопросы (первые 5):\n"
        for qid, info in list(question_user_map.items())[:5]:
            stats_text += f"  {qid}: {info['user_name']} - {info['question'][:30]}...\n"
    
    bot.send_message(message.chat.id, stats_text, reply_markup=create_back_button())

def list_questions(message):
    if not question_user_map:
        bot.send_message(message.chat.id, "📭 Нет активных вопросов.")
        return
    
    text = "📋 АКТИВНЫЕ ВОПРОСЫ:\n\n"
    for qid, info in question_user_map.items():
        question_time = datetime.strptime(info['time'], '%d.%m.%Y %H:%M')
        wait_time = datetime.now() - question_time
        wait_str = format_time(int(wait_time.total_seconds()))
        
        text += f"ID: {qid}\n"
        text += f"От: {info['user_name']}\n"
        text += f"📞 Телефон: {info.get('phone', 'Не указан')}\n"
        text += f"⏰ Ожидание: {wait_str}\n"
        text += f"Вопрос: {info['question'][:50]}...\n"
        text += "─" * 20 + "\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000])
    else:
        bot.send_message(message.chat.id, text)

def handle_view_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только администраторы могут просматривать вопросы.")
        return
    
    question_id = call.data.replace('view_', '')
    
    if question_id not in question_user_map:
        bot.answer_callback_query(call.id, "❌ Вопрос не найден.")
        return
    
    question_info = question_user_map[question_id]
    
    view_text = (
        f"📋 ДЕТАЛИ ВОПРОСА #{question_id}\n\n"
        f"👤 Имя: {question_info['user_name']}\n"
        f"🆔 ID: {question_info['user_id']}\n"
        f"📞 Телефон: {question_info.get('phone', 'Не указан')}\n"
        f"⏰ Время: {question_info['time']}\n\n"
        f"📝 ВОПРОС:\n{question_info['question']}"
    )
    
    bot.send_message(call.from_user.id, view_text)
    bot.answer_callback_query(call.id)

def handle_answer_callback(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Только администраторы могут отвечать на вопросы.")
        return
    
    question_id = call.data.replace('answer_', '')
    
    if question_id not in question_user_map:
        bot.answer_callback_query(call.id, "❌ Вопрос не найден или уже отвечен.")
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except:
            pass
        return
    
    admin_reply_data[call.from_user.id] = {
        'question_id': question_id,
        'question_info': question_user_map[question_id],
        'original_message': call.message
    }
    
    bot.send_message(
        call.from_user.id,
        f"✏️ Введите ответ на вопрос #{question_id}\n\n"
        f"❓ Вопрос: {question_user_map[question_id]['question']}\n"
        f"👤 От: {question_user_map[question_id]['user_name']}\n"
        f"📞 Телефон: {question_user_map[question_id].get('phone', 'Не указан')}\n\n"
        f"📝 Напишите ваш ответ (или /skip чтобы пропустить):",
        reply_markup=create_back_button()
    )
    
    bot.register_next_step_handler_by_chat_id(call.from_user.id, process_admin_answer)
    bot.answer_callback_query(call.id, "✅ Введите ваш ответ")

def process_admin_answer(message):
    admin_id = message.from_user.id
    
    if message.text == "◀️ Назад" or message.text == "/skip":
        if admin_id in admin_reply_data:
            del admin_reply_data[admin_id]
        bot.send_message(
            message.chat.id, 
            "🏠 Ответ отменен.", 
            reply_markup=create_main_menu(True)
        )
        return
    
    if admin_id not in admin_reply_data:
        bot.send_message(
            message.chat.id, 
            "❌ Сессия ответа истекла. Начните заново.", 
            reply_markup=create_main_menu(True)
        )
        return
    
    reply_data = admin_reply_data[admin_id]
    question_id = reply_data['question_id']
    question_info = reply_data['question_info']
    original_message = reply_data['original_message']
    
    answer_text = message.text
    user_id = question_info['user_id']
    
    try:
        bot.send_message(
            user_id,
            f"📬 ОТВЕТ НА ВАШ ВОПРОС #{question_id}\n\n"
            f"❓ Ваш вопрос: {question_info['question']}\n\n"
            f"💬 Ответ администратора:\n{answer_text}\n\n"
            f"Спасибо, что обратились в наш автосервис!\n"
            f"Если у вас остались вопросы, вы можете задать их снова."
        )
        
        bot.send_message(
            admin_id,
            f"✅ Ответ успешно отправлен пользователю {question_info['user_name']}!",
            reply_markup=create_main_menu(True)
        )
        
        stats['answered_questions'] += 1
        save_data()
        
        try:
            bot.edit_message_reply_markup(
                chat_id=original_message.chat.id,
                message_id=original_message.message_id,
                reply_markup=None
            )
            
            admin_name = message.from_user.username or f"ID {admin_id}"
            bot.send_message(
                original_message.chat.id,
                f"✅ Администратор @{admin_name} ответил на вопрос #{question_id}"
            )
        except Exception as e:
            print(f"Не удалось обновить сообщение в группе: {e}")
        
        del question_user_map[question_id]
        save_data()
        
    except Exception as e:
        bot.send_message(
            admin_id,
            f"❌ Не удалось отправить ответ пользователю.\n"
            f"Ошибка: {e}\n\n"
            f"📞 Телефон пользователя: {question_info.get('phone', 'Не указан')}\n\n"
            f"Вы можете связаться с ним по телефону.",
            reply_markup=create_main_menu(True)
        )
    
    if admin_id in admin_reply_data:
        del admin_reply_data[admin_id]

# Функция для автосохранения данных
def auto_save():
    while BOT_RUNNING:
        time.sleep(300)  # Сохраняем каждые 5 минут
        save_data()

# Функция для проверки соединения
def check_connection():
    reconnect_count = 0
    while BOT_RUNNING:
        try:
            bot.get_me()
            reconnect_count = 0  # Сбрасываем счетчик при успешном подключении
            time.sleep(60)
        except Exception as e:
            reconnect_count += 1
            print(f"⚠️ Проблема с соединением: {e}")
            log_error(f"Connection error: {e}")
            time.sleep(min(30, 5 * reconnect_count))  # Экспоненциальная задержка

# Обработчик сигналов для graceful shutdown
def signal_handler(signum, frame):
    global BOT_RUNNING
    print("\n🛑 Получен сигнал остановки...")
    BOT_RUNNING = False
    save_data()
    print("👋 Данные сохранены. Завершение работы...")
    sys.exit(0)

if __name__ == "__main__":
    # Устанавливаем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 50)
    print("🤖 Бот автосервиса запущен")
    print("=" * 50)
    print(f"📊 Статистика при запуске:")
    print(f"   👥 Пользователей: {len(stats['users'])}")
    print(f"   ❓ Активных вопросов: {len(question_user_map)}")
    print(f"   📝 Всего записей: {stats['total_appointments']}")
    print("=" * 50)
    print(f"👑 Администраторы ({len(ADMIN_IDS)}):")
    for i, admin_id in enumerate(ADMIN_IDS, 1):
        print(f"   {i}. ID: {admin_id}")
    print("=" * 50)
    print(f"📢 Группа поддержки ID: {SUPPORT_GROUP_ID}")
    print("=" * 50)
    
    # Запускаем Flask сервер
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Веб-сервер запущен на порту 8080")
    print("=" * 50)
    
    # Запускаем поток автосохранения
    save_thread = threading.Thread(target=auto_save, daemon=True)
    save_thread.start()
    print("✅ Автосохранение: Каждые 5 минут")
    
    # Запускаем поток проверки соединения
    check_thread = threading.Thread(target=check_connection, daemon=True)
    check_thread.start()
    print("✅ Мониторинг соединения активен")
    print("=" * 50)
    print("❌ Нажмите Ctrl+C для остановки")
    print("=" * 50)
    
    # Улучшенный цикл с автоматическим переподключением
    reconnect_count = 0
    max_reconnect_delay = 60
    
    while BOT_RUNNING:
        try:
            print("🔄 Запуск бота...")
            # Используем бесконечный polling с обработкой ошибок
            bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)
        except KeyboardInterrupt:
            break
        except Exception as e:
            reconnect_count += 1
            error_msg = f"Ошибка в основном цикле (попытка #{reconnect_count}): {e}"
            print(f"⚠️ {error_msg}")
            log_error(error_msg)
            
            if not BOT_RUNNING:
                break
            
            # Экспоненциальная задержка при переподключении
            wait_time = min(max_reconnect_delay, 5 * (2 ** min(reconnect_count - 1, 4)))
            print(f"🔄 Перезапуск через {wait_time} секунд...")
            
            for i in range(wait_time, 0, -1):
                if not BOT_RUNNING:
                    break
                print(f"⏳ {i}...", end='\r')
                time.sleep(1)
            print("🔄 Перезапуск...                   ")
    
    # Сохраняем данные при выходе
    save_data()
    print("👋 Бот остановлен. До свидания!")