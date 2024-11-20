import os
import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta, timezone
from aiogram.utils.deep_linking import decode_payload
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import requests
from sqlalchemy.sql import func  # Добавьте этот импорт

app = Flask(__name__)
db_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(db_dir, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

TELEGRAM_TOKEN = '8053872696:AAFQnRLQ1R01VdIgQXL5NMqaqVoUA7jVOGE'

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    telegram_username = db.Column(db.String(50), unique=True, nullable=True)
    balance_dct = db.Column(db.Integer, default=0)
    balance_usdt = db.Column(db.Integer, default=0)
    clicks_today = db.Column(db.Integer, default=0)
    last_click = db.Column(db.DateTime, nullable=True)
    last_reset = db.Column(db.DateTime, nullable=True)
    daily_earnings = db.Column(db.Integer, default=0)
    subscribed_telegram = db.Column(db.Boolean, default=False)
    subscribed_xcom = db.Column(db.Boolean, default=False)
    fortuna_spins = db.Column(db.Integer, default=0)
    sunduk_keys = db.Column(db.Integer, default=0)
    last_fortuna_spin = db.Column(db.DateTime, nullable=True)
    last_sunduk_open = db.Column(db.DateTime, nullable=True)
    energy_level = db.Column(db.Integer, default=1)
    boost_level = db.Column(db.Integer, default=1)
    energy_used_today = db.Column(db.Integer, default=0)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=3))
    last_update = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    mining_active = db.Column(db.Boolean, default=False)
    mining_end_time = db.Column(db.DateTime, nullable=True)
    mining_level = db.Column(db.Integer, default=1)
    start_time_usdt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time_usdt = db.Column(db.DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=3))
    last_update_usdt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    mining_active_usdt = db.Column(db.Boolean, default=False)
    mining_end_time_usdt = db.Column(db.DateTime, nullable=True)
    mining_level_usdt = db.Column(db.Integer, default=1)
    task_tg_completed = db.Column(db.Boolean, default=False)  # Выполнена ли задача с TG
    task_twitter_completed = db.Column(db.Boolean, default=False)  # Выполнена ли задача с Twitter
    task_chat_completed = db.Column(db.Boolean, default=False)  # Выполнена ли задача с чатом TG

    # Логика для USDT
    def get_upgrade_cost_usdt(self):
        upgrade_costs = [100, 200, 300, 500, 1000, 3000]
        return upgrade_costs[self.mining_level_usdt - 1] if self.mining_level_usdt <= len(upgrade_costs) else None

    def get_hourly_income_usdt(self):
        incomes = [0.01, 0.1, 0.5, 1, 2, 10]
        return incomes[self.mining_level_usdt - 1] if self.mining_level_usdt <= len(incomes) else None

    def get_upgrade_cost(self):
        upgrade_costs = [10000000, 20000000, 50000000, 70000000, 100000000, 500000000]
        return upgrade_costs[self.mining_level - 1] if self.mining_level <= len(upgrade_costs) else None

    def get_hourly_income(self):
        incomes = [25000, 50000, 75000, 100000, 125000, 150000]
        return incomes[self.mining_level - 1] if self.mining_level <= len(incomes) else None
    
    def get_click_value(self):
        click_values = [1, 2, 4, 6, 8, 10, 12, 13, 14, 15, 20, 21, 22]
        return click_values[self.boost_level - 1] if self.boost_level <= len(click_values) else 1

    def get_max_clicks(self):
        # Логика вычисления максимального количества кликов в день в зависимости от уровня энергии
        energy_clicks = [5000, 5500, 6000, 6500, 7000, 7500, 8000, 8500, 9000, 9500, 10000, 10500, 11000, 11500, 12000]
        return energy_clicks[self.energy_level - 1] if self.energy_level <= len(energy_clicks) else 5000
    
    def get_boost_name(self):
        level_names = [
            "Baby Duck",
            "Junior Duck",
            "Teenager Duck",
            "Senior Duck",
            "Silver Duck",
            "Gold Duck",
            "Elite Duck",
            "Master Duck",
            "Grand Master Duck",
            "Supreme Duck"
        ]
        return level_names[self.boost_level - 1] if self.boost_level <= len(level_names) else "Unknown Duck"


class Referral(db.Model):
    __tablename__ = 'referral'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    referral_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def init_db():
    with app.app_context():
        db.create_all()
        print("База данных инициализирована")
scheduler = BackgroundScheduler()
scheduler.start()

def check_active_miners():
    with app.app_context():
        users = User.query.filter_by(mining_active=True).all()
        for user in users:
            update_user_balance(user)

scheduler.add_job(check_active_miners, 'interval', minutes=1)

def update_user_balance(user):
    current_time = datetime.utcnow()

    # Проверка завершения времени майнинга для DCT
    if user.mining_active and current_time >= user.mining_end_time:
        user.mining_active = False  # Отключаем майнинг
        user.last_update = user.mining_end_time  # Обновляем время последнего обновления на время завершения майнинга

    # Проверка завершения времени майнинга для USDT
    if user.mining_active_usdt and current_time >= user.mining_end_time_usdt:
        user.mining_active_usdt = False  # Отключаем майнинг
        user.last_update_usdt = user.mining_end_time_usdt  # Обновляем время последнего обновления на время завершения майнинга

    # Обновление DCT
    if user.mining_active:
        elapsed_time_dct = (current_time - user.last_update).total_seconds()
        if elapsed_time_dct >= 60:  # Обновление происходит каждую минуту
            earned_dct = (elapsed_time_dct / 3600) * user.get_hourly_income()
            user.balance_dct += earned_dct
            user.last_update = current_time

    # Обновление USDT
    if user.mining_active_usdt:
        elapsed_time_usdt = (current_time - user.last_update_usdt).total_seconds()
        if elapsed_time_usdt >= 60:  # Обновление происходит каждую минуту
            earned_usdt = (elapsed_time_usdt / 3600) * user.get_hourly_income_usdt()
            user.balance_usdt += earned_usdt
            user.last_update_usdt = current_time

    db.session.commit()

def get_telegram_avatar(user_id):
    try:
        response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUserProfilePhotos", params={"user_id": user_id})
        data = response.json()

        if data['ok'] and data['result']['total_count'] > 0:
            file_id = data['result']['photos'][0][-1]['file_id']
            file_response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getFile", params={"file_id": file_id})
            file_data = file_response.json()

            if file_data['ok']:
                file_path = file_data['result']['file_path']
                avatar_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
                return avatar_url
    except Exception as e:
        print(f"Error fetching avatar: {e}")
    return None

@app.route('/')
def index():
    user_id = request.args.get('user_id')
    if user_id:
        try:
            user_id = int(user_id)
            user = db.session.get(User, user_id)
            if not user:
                user = User(id=user_id, daily_earnings=0)  # Инициализируем daily_earnings
                db.session.add(user)
                db.session.commit()

            avatar_url = get_telegram_avatar(user_id)
        except ValueError:
            return "Invalid user ID", 400
    else:
        return "User ID missing", 400

    return render_template('index.html', user_id=user.id, balance_dct=user.balance_dct, balance_usdt=user.balance_usdt, telegram_username=user.telegram_username, avatar_url=avatar_url)

@app.route('/start', methods=['GET'])
def start():
    referral_code = request.args.get('start')
    user_id = request.args.get('user_id')

    # Проверка и создание пользователя по user_id
    if user_id:
        try:
            user_id = int(user_id)
            user = db.session.get(User, user_id)
            if not user:
                user = User(id=user_id, daily_earnings=0)  # Инициализируем daily_earnings
                db.session.add(user)
                db.session.commit()
        except ValueError:
            return "Invalid user ID", 400
    else:
        return "User ID missing", 400

    # Обработка реферального кода
    if referral_code:
        try:
            # Декодирование реферального кода
            referral_id = int(referral_code.replace("user_", ""))
            referrer = db.session.get(User, referral_id)
            if not referrer:
                return "User not found", 404

            # Создание нового пользователя
            new_user = User(balance_dct=0, balance_usdt=0, clicks_today=0, last_click=None, last_reset=None, daily_earnings=0)
            db.session.add(new_user)
            db.session.flush()  # Используем flush() для получения нового ID пользователя

            # Обновление или создание записи реферала
            new_referral = Referral(user_id=referrer.id, referral_id=referrer.id, referred_user_id=new_user.id)
            existing_referral = db.session.query(Referral).filter_by(referral_id=referrer.id, referred_user_id=new_user.id).first()
            if not existing_referral:
                db.session.add(new_referral)
                db.session.commit()

            return render_template('index.html', user_id=new_user.id, balance_dct=new_user.balance_dct, balance_usdt=new_user.balance_usdt)

        except (IndexError, ValueError) as e:
            return "Invalid referral code", 400

    # Если нет referral_code, проверяем и создаем запись реферала, если ее нет
    if user_id:
        try:
            user_id = int(user_id)
            user = db.session.get(User, user_id)
            if not user:
                return "User not found", 404
            
            # Проверка и создание записи реферала
            existing_referral = db.session.query(Referral).filter_by(user_id=user_id).first()
            if not existing_referral:
                new_referral = Referral(user_id=user_id, referral_id=user_id)
                db.session.add(new_referral)
                db.session.commit()

        except ValueError:
            return "Invalid user ID", 400
    else:
        return "User ID missing", 400

    return render_template('index.html', user_id=user.id, balance_dct=user.balance_dct, balance_usdt=user.balance_usdt)



@app.route('/balance/dct')
def get_balance_dct():
    user_id = request.args.get('user_id')
    user = db.session.get(User, user_id)
    if user:
        return jsonify(balance=round(user.balance_dct, 3))
    return jsonify({"error": "User not found"}), 404

@app.route('/balance/usdt')
def get_balance_usdt():
    user_id = request.args.get('user_id')
    user = db.session.get(User, user_id)
    if user:
        return jsonify(balance=round(user.balance_usdt, 3))
    return jsonify({"error": "User not found"}), 404


@app.route('/click', methods=['POST'])
def click():
    user_id = request.form.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return "User not found", 404

    dubai_tz = pytz.timezone('Asia/Dubai')
    current_time = datetime.now(dubai_tz)
    if user.last_reset:
        user_last_reset_aware = user.last_reset.replace(tzinfo=dubai_tz)
        if (current_time - user_last_reset_aware) >= timedelta(hours=24):
            user.clicks_today = 0
            user.last_reset = current_time
            user.daily_earnings = 0
    else:
        user.last_reset = current_time
        user.clicks_today = 0
        user.daily_earnings = 0

    max_clicks = user.get_max_clicks()
    if user.clicks_today >= max_clicks:
        return jsonify({"message": "Click limit reached for today"}), 429

    click_value = user.get_click_value()
    user.clicks_today += 1
    user.balance_dct += click_value
    user.daily_earnings += click_value
    user.last_click = current_time

    db.session.commit()

    return jsonify({
        "message": "Success",
        "clicks_today": user.clicks_today,
        "click_value": click_value,
        "clicks_remaining": max_clicks - user.clicks_today
    }), 200

@app.route('/clicks', methods=['GET'])
def get_clicks():
    user_id = int(request.args.get('user_id'))
    user = db.session.get(User, user_id)
    if not user:
        return "User not found", 404

    return jsonify({
        "clicks_today": user.clicks_today,
        "clicks_remaining": user.get_max_clicks() - user.clicks_today
    }), 200

@app.route('/update_balance', methods=['POST'])
def update_balance():
    data = request.get_json()
    user_id = data.get('user_id')
    balance = data.get('balance')
    game_type = data.get('game_type')

    user = db.session.get(User, user_id)
    if user:
        if game_type == 'DCT':
            user.balance_dct += balance
        elif game_type == 'USDT':
            user.balance_usdt += balance
        db.session.commit()
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

@app.route('/complete-task', methods=['POST'])
def complete_task():
    user_id = request.json.get('user_id')
    task_type = request.json.get('task_type')

    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if task_type == 'TG':
        if not user.task_tg_completed:
            user.task_tg_completed = True
            user.balance_dct += 100000  # Награда за выполнение задачи
    elif task_type == 'TWITTER':
        if not user.task_twitter_completed:
            user.task_twitter_completed = True
            user.balance_dct += 100000
    elif task_type == 'CHAT':
        if not user.task_chat_completed:
            user.task_chat_completed = True
            user.balance_dct += 100000
    # Добавьте остальные задачи аналогичным образом
    
    db.session.commit()
    return jsonify({"status": "success", "balance": user.balance_dct})

@app.route('/check-task-status', methods=['GET'])
def check_task_status():
    user_id = request.args.get('user_id')
    task_type = request.args.get('task_type')

    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    task_status = False
    if task_type == 'TG':
        task_status = user.task_tg_completed
    elif task_type == 'TWITTER':
        task_status = user.task_twitter_completed
    elif task_type == 'CHAT':
        task_status = user.task_chat_completed
    # Добавьте проверку других задач

    return jsonify({"completed": task_status})

@app.route('/task-states', methods=['GET'])
def get_task_states():
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)
    if user:
        # Замените это реальными полями и значениями из вашей базы данных
        task_states = {
            "TG": {"completed": user.subscribed_telegram},
            "TWITTER": {"completed": user.subscribed_xcom},
            "CHAT": {"completed": user.task_chat_completed},
            # Добавьте остальные задачи аналогично
        }
        return jsonify(task_states)
    return jsonify({"error": "User not found"}), 404

@app.route('/purchase-energy', methods=['POST'])
def purchase_energy():
    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    upgrade_cost = user.energy_level * 2000  # Пример стоимости
    if user.balance_dct >= upgrade_cost:
        user.balance_dct -= upgrade_cost
        user.energy_level += 1
        
        # Обновляем максимальное количество кликов
        new_max_clicks = user.get_max_clicks()
        user.clicks_today = min(user.clicks_today, new_max_clicks)

        db.session.commit()
        return jsonify({"success": True, "new_level": user.energy_level, "new_balance": user.balance_dct, "max_clicks": new_max_clicks})
    else:
        return jsonify({"success": False, "message": "Недостаточно средств на балансе"}), 400

@app.route('/update-task-state', methods=['POST'])
def update_task_state():
    data = request.get_json()
    user_id = data.get('user_id')
    task_id = data.get('task_id')
    completed = data.get('completed', False)

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Обновление состояния задачи на основе task_id
    if task_id == "TG":
        user.subscribed_telegram = completed
    elif task_id == "TWITTER":
        user.subscribed_xcom = completed
    # Обновите соответствующие поля для других задач

    db.session.commit()
    return jsonify({"success": True})


@app.route('/start-mining', methods=['POST'])
def start_mining():
    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.mining_active:
        return jsonify({"error": "Mining already active"}), 400

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=3)
    
    user.mining_active = True
    user.start_time = start_time
    user.mining_end_time = end_time
    user.last_update = start_time  # last_update устанавливается в момент старта майнинга
    
    db.session.commit()
    
    return jsonify({"message": "Mining started", "end_time": end_time.isoformat()})


@app.route('/check-mining-status', methods=['GET'])
def check_mining_status():
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Обновляем баланс и проверяем статус майнинга
    update_user_balance(user)

    return jsonify({
        "mining_active": user.mining_active,
        "balance_dct": user.balance_dct,
        "last_update": user.last_update.isoformat(),
        "can_start_mining": not user.mining_active
    })

@app.route('/exchange-tokens', methods=['POST'])
def exchange_tokens():
    data = request.get_json()
    user_id = data.get('user_id')
    dct_amount = float(data.get('dct_amount'))

    if dct_amount <= 0:
        return jsonify({'success': False, 'message': 'Некорректная сумма для обмена'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'}), 404

    # Формула обмена
    exchange_rate = 10000  # Пример курса: 10000 DCT = 1 USDT
    usdt_amount = dct_amount / exchange_rate

    if user.balance_dct < dct_amount:
        return jsonify({'success': False, 'message': 'Недостаточно DCT для обмена'}), 400

    # Обновляем баланс
    user.balance_dct -= dct_amount
    user.balance_usdt += usdt_amount
    db.session.commit()

    return jsonify({
        'success': True,
        'usdt_amount': usdt_amount,
        'new_dct_balance': user.balance_dct,
        'new_usdt_balance': user.balance_usdt
    })

@app.route('/start-mining-usdt', methods=['POST'])
def start_mining_usdt():
    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.mining_active_usdt:
        return jsonify({"error": "Mining already active"}), 400

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=3)

    user.mining_active_usdt = True
    user.start_time_usdt = start_time
    user.mining_end_time_usdt = end_time
    user.last_update_usdt = start_time

    db.session.commit()

    return jsonify({"message": "Mining started", "end_time": end_time.isoformat()})


@app.route('/check-mining-status-usdt', methods=['GET'])
def check_mining_status_usdt():
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    update_user_balance(user)

    return jsonify({
        "mining_active": user.mining_active_usdt,
        "balance_usdt": user.balance_usdt,
        "last_update": user.last_update_usdt.isoformat(),
        "can_start_mining": not user.mining_active_usdt
    })

@app.route('/upgrade-mining-usdt', methods=['POST'])
def upgrade_mining_usdt():
    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    upgrade_cost = user.get_upgrade_cost_usdt()

    if user.balance_usdt >= upgrade_cost:
        user.balance_usdt -= upgrade_cost
        user.mining_level_usdt += 1
        db.session.commit()
        return jsonify({"success": True, "new_level": user.mining_level_usdt, "new_income": user.get_hourly_income_usdt(), "next_upgrade_cost": user.get_upgrade_cost_usdt()})
    else:
        return jsonify({"success": False, "message": "Not enough USDT balance"}), 400

@app.route('/referral-info', methods=['GET'])
def referral_info():
    user_id = request.args.get('user_id')
    if user_id:
        try:
            user_id = int(user_id)
            referrals = db.session.query(Referral, User).join(User, User.id == Referral.referred_user_id).filter(Referral.referral_id == user_id).all()
            referral_data = [{"id": u.id, "telegram_username": u.telegram_username, "balance": u.balance, "earned": u.daily_earnings * 0.05} for r, u in referrals]
            total_users = User.query.count()

            print(f"Referrals for user_id {user_id}: {referral_data}")

            total_earned = sum([r["earned"] for r in referral_data])

            return jsonify({
                "referrals": referral_data,
                "total_users": total_users,
                "total_earned": total_earned
            })
        except ValueError:
            return "Invalid user ID", 400
    else:
        return "User ID missing", 400

@app.route('/referrals/<int:user_id>')
def show_referrals(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return "User not found", 404

    # Получение рефералов пользователя
    referrals = db.session.query(Referral, User).join(User, User.id == Referral.referred_user_id).filter(Referral.referral_id == user_id).all()

    referral_data = []
    total_earned = 0
    for referral, referred_user in referrals:
        earned = referred_user.daily_earnings * 0.05  # 5% от дневного заработка реферала
        total_earned += earned
        referral_data.append({
            'telegram_username': referred_user.telegram_username or referred_user.id,
            'balance': referred_user.balance,
            'earned': earned
        })

    return render_template('referrals.html', user_id=user.id, telegram_username=user.telegram_username, referrals=referral_data, total_earned=total_earned)

@app.route('/create_referral', methods=['POST'])
def create_referral():
    data = request.get_json()
    user_id = data.get('user_id')
    referral_id = data.get('referral_id')

    if not user_id or not referral_id:
        return jsonify({"message": "User ID or Referral ID missing"}), 400

    try:
        user_id = int(user_id)
        referral_id = int(referral_id)
        
        user = User.query.get(user_id)
        if not user:
            # Создаем нового пользователя, если он не существует
            user = User(id=user_id, daily_earnings=0)  # Инициализируем daily_earnings
            db.session.add(user)
            db.session.commit()

        referrer = User.query.get(referral_id)
        if not referrer:
            return jsonify({"message": "Referrer not found"}), 404

        # Проверка на существование записи реферала
        existing_referral = Referral.query.filter_by(user_id=user_id, referral_id=referral_id).first()
        if existing_referral:
            return jsonify({"message": "Referral already exists"}), 400

        # Создание новой записи реферала
        referral = Referral(user_id=user_id, referral_id=referral_id, referred_user_id=user.id)
        db.session.add(referral)
        db.session.commit()

        user.balance += 20000  # Добавляем баланс пользователю
        db.session.commit()
        print(f"Баланс пользователя с ID {referral_id} увеличен на 20000")

        return jsonify({"message": "Referral created successfully"}), 200

    except ValueError:
        return jsonify({"message": "Invalid User ID or Referral ID"}), 400
        
@app.route('/update_username/<int:user_id>')
def update_username(user_id):
    username = request.args.get('username')
    if not username:
        return "Username missing", 400
    
    user = User.query.get(user_id)
    if user:
        user.telegram_username = username
        db.session.commit()
        return f"Username updated for user {user_id}: {username}"
    else:
        return "User not found", 404

@app.route('/activate-key', methods=['POST'])
def activate_key():
    user_id = request.json.get('user_id')
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404
    
    user.sunduk_keys += 1
    db.session.commit()

    return jsonify({"success": True, "message": "Key activated successfully"})

@app.route('/boost-level', methods=['GET'])
def get_boost_level():
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)
    if user:
        return jsonify({
            "level": user.boost_level,
            "boost_name": user.get_boost_name()  # Добавляем название уровня
        })
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/check-eligibility', methods=['GET'])
def check_eligibility():
    user_id = request.args.get('user_id')
    action_type = request.args.get('action_type')
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    
    dubai_tz = pytz.timezone('Asia/Dubai')
    current_time = datetime.now(dubai_tz)
    
    if action_type == 'FORTUNA':
        if user.last_fortuna_spin:
            # Преобразование last_fortuna_spin в offset-aware, если оно не в нужной временной зоне
            user_last_fortuna_spin_aware = user.last_fortuna_spin.replace(tzinfo=dubai_tz) if user.last_fortuna_spin.tzinfo is None else user.last_fortuna_spin
            elapsed_time = current_time - user_last_fortuna_spin_aware
            if elapsed_time < timedelta(hours=3):
                remaining_time = timedelta(hours=3) - elapsed_time
                return jsonify({"eligible": False, "remaining_time": remaining_time.total_seconds()})
        user.last_fortuna_spin = current_time
        db.session.commit()
        return jsonify({"eligible": True})
    
    elif action_type == 'SUNDUK':
        if user.last_sunduk_open:
            # Преобразование last_sunduk_open в offset-aware
            user_last_sunduk_open_aware = user.last_sunduk_open.replace(tzinfo=dubai_tz) if user.last_sunduk_open.tzinfo is None else user.last_sunduk_open
            elapsed_time = current_time - user_last_sunduk_open_aware
            if elapsed_time < timedelta(hours=3):
                remaining_time = timedelta(hours=3) - elapsed_time
                return jsonify({"eligible": False, "remaining_time": remaining_time.total_seconds()})
        user.last_sunduk_open = current_time
        db.session.commit()
        return jsonify({"eligible": True})
    
    return jsonify({"status": "error", "message": "Invalid action type"}), 400
@app.route('/upgrade-mining', methods=['POST'])
def upgrade_mining():
    user_id = request.json.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    upgrade_cost = user.get_upgrade_cost()
    
    if user.balance_dct >= upgrade_cost:
        user.balance_dct -= upgrade_cost
        user.mining_level += 1
        db.session.commit()
        return jsonify({"success": True, "new_level": user.mining_level, "new_income": user.get_hourly_income(), "next_upgrade_cost": user.get_upgrade_cost()})
    else:
        return jsonify({"success": False, "message": "Not enough DCT balance"}), 400

@app.route('/spin-fortuna', methods=['POST'])
def spin_fortuna():
    user_id = request.json.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    # Проверка наличия спинов
    if user.fortuna_spins <= 0:
        return jsonify({"status": "error", "message": "No spins left"}), 400

    # Уменьшение количества спинов
    user.fortuna_spins -= 1

    # Награды и их вероятности
    rewards = [
        {"reward": "Ключ от сундука", "type": "key", "chance": 0.01},  # Очень редко
        {"reward": "10.000 монет DCT", "type": "dct", "amount": 10000, "chance": 0.2},  # Часто
        {"reward": "10 USDT", "type": "usdt", "amount": 10, "chance": 0.01},  # Очень редко
        {"reward": "5.000 монет DCT", "type": "dct", "amount": 5000, "chance": 0.2},  # Часто
        {"reward": "5 USDT", "type": "usdt", "amount": 5, "chance": 0.02},  # Очень редко
        {"reward": "3.000 монет DCT", "type": "dct", "amount": 3000, "chance": 0.25},  # Чаще
        {"reward": "3 USDT", "type": "usdt", "amount": 3, "chance": 0.05},  # Редко
        {"reward": "100.000 монет DCT", "type": "dct", "amount": 100000, "chance": 0.05},  # Редко
        {"reward": "1 USDT", "type": "usdt", "amount": 1, "chance": 0.1},  # Не очень часто
        {"reward": "50.000 монет DCT", "type": "dct", "amount": 50000, "chance": 0.1},  # Часто
        {"reward": "0,5 USDT", "type": "usdt", "amount": 0.5, "chance": 0.15},  # Часто, но не как 3000 или 5000 DCT
        {"reward": "Ключ от сундука", "type": "key", "chance": 0.01},  # Очень редко
    ]

    # Случайный выбор награды на основе вероятностей
    chosen_reward = random.choices(rewards, weights=[r["chance"] for r in rewards])[0]

    # Применение награды к пользователю
    if chosen_reward["type"] == "key":
        user.sunduk_keys += 1
    elif chosen_reward["type"] == "dct":
        user.balance_dct += chosen_reward["amount"]
    elif chosen_reward["type"] == "usdt":
        user.balance_usdt += chosen_reward["amount"]

    db.session.commit()

    return jsonify({"status": "success", "reward": chosen_reward["reward"]})

@app.route('/open-sunduk', methods=['POST'])
def open_sunduk():
    user_id = request.json.get('user_id')
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    
    if user.sunduk_keys > 0:
        user.sunduk_keys -= 1
        
        # Определяем награду с использованием случайных вероятностей
        rewards = [
            {"reward": "10 USDT", "type": "usdt", "amount": 10, "chance": 0.03},
            {"reward": "1000 DCT", "type": "dct", "amount": 1000, "chance": 0.05},
            {"reward": "50 USDT", "type": "usdt", "amount": 50, "chance": 0.01},
            {"reward": "10000 DCT", "type": "dct", "amount": 10000, "chance": 0.04},
            {"reward": "Tesla", "type": "item", "image": "static/Тесла.png", "chance": 0.02},
            {"reward": "iPhone", "type": "item", "image": "static/iphone.png", "chance": 0.04},
            {"reward": "Laptop", "type": "item", "image": "static/not.png", "chance": 0.05},
            {"reward": "Motorcycle", "type": "item", "image": "static/moto.png", "chance": 0.03},
            {"reward": "Gold Bar", "type": "item", "image": "static/slit.png", "chance": 0.07},
            {"reward": "Car", "type": "item", "image": "static/avto.png", "chance": 0.05}
        ]

        chosen_reward = random.choices(rewards, weights=[r["chance"] for r in rewards])[0]

        if chosen_reward["type"] == "usdt":
            user.balance_usdt += chosen_reward["amount"]
        elif chosen_reward["type"] == "dct":
            user.balance_dct += chosen_reward["amount"]
        
        db.session.commit()

        if chosen_reward["type"] in ["usdt", "dct"]:
            return jsonify({
                "status": "success",
                "reward": chosen_reward["reward"],
                "rewardType": chosen_reward["type"]
            })
        else:
            return jsonify({
                "status": "success",
                "reward": f"<img src='{chosen_reward['image']}' alt='{chosen_reward['reward']}'>",
                "rewardType": "item"
            })
    
    return jsonify({"status": "error", "message": "No keys left"}), 400

@app.route('/energy-level', methods=['GET'])
def get_energy_level():
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)
    if user:
        return jsonify({'level': user.energy_level})
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/upgrade-energy-level', methods=['POST'])
def upgrade_energy_level():
    data = request.get_json()
    user_id = data.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404

    upgrade_cost = user.energy_level * 2000  # Стоимость увеличивается с уровнем
    if user.balance_dct >= upgrade_cost:
        user.balance_dct -= upgrade_cost
        user.energy_level += 1
        
        # Пересчитываем максимальное количество кликов
        new_max_clicks = user.get_max_clicks()
        user.clicks_today = min(user.clicks_today, new_max_clicks)  # Ограничиваем текущее количество кликов новым значением

        db.session.commit()
        return jsonify({'level': user.energy_level, 'new_balance': user.balance_dct, 'max_clicks': new_max_clicks})
    else:
        return jsonify({'error': 'Not enough DCT balance'}), 400


@app.route('/energy-status', methods=['GET'])
def get_energy_status():
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)
    if user:
        max_energy = user.get_max_clicks()
        energy_left = max_energy - user.clicks_today
        return jsonify({
            'energy': energy_left,
            'max_energy': max_energy,
            'level': user.energy_level
        })
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/buy-boost', methods=['POST'])
def buy_boost():
    data = request.get_json()
    user_id = data['user_id']
    level = data['level']
    cost = data['cost']

    user = User.query.get(user_id)

    if user:
        if user.balance_dct >= cost:
            user.balance_dct -= cost
            user.boost_level = level
            db.session.commit()
            return jsonify({
                "success": True, 
                "message": f"Вы достигли уровня {user.get_boost_name()}!",
                "new_boost_level": user.boost_level
            })
        else:
            return jsonify({"success": False, "message": "Недостаточно средств на балансе"})
    else:
        return jsonify({"success": False, "message": "Пользователь не найден"})

@app.route('/airdrop.html')
def airdrop():
    user_id = request.args.get('user_id')
    return render_template('airdrop.html', user_id=user_id)

@app.route('/boost.html')
def boost():
    user_id = request.args.get('user_id')
    return render_template('boost.html', user_id=user_id)

@app.route('/energy.html')
def energy():
    user_id = request.args.get('user_id')
    return render_template('energy.html', user_id=user_id)

@app.route('/fortune.html')
def fortune():
    user_id = request.args.get('user_id')
    return render_template('fortune.html', user_id=user_id)

@app.route('/friends.html')
def friends():
    user_id = request.args.get('user_id')
    return render_template('friends.html', user_id=user_id)

@app.route('/mining.html')
def mining():
    user_id = request.args.get('user_id')
    return render_template('mining.html', user_id=user_id)

@app.route('/sunduk.html')
def sunduk():
    user_id = request.args.get('user_id')
    return render_template('sunduk.html', user_id=user_id)

@app.route('/task.html')
def task():
    user_id = request.args.get('user_id')
    return render_template('task.html', user_id=user_id)

@app.route('/usdt.html')
def usdt():
    user_id = request.args.get('user_id')
    return render_template('usdt.html', user_id=user_id)

@app.route('/index.html')
def redirect_to_home():
    user_id = request.args.get('user_id')
    return redirect(url_for('index', user_id=user_id))
    
if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)


