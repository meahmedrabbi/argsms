"""Database models and initialization for the Telegram bot."""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()


def get_admin_telegram_ids():
    """Get list of admin Telegram IDs from environment."""
    admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
    if not admin_ids_str:
        return []
    
    admin_ids = []
    for id_str in admin_ids_str.split(","):
        id_str = id_str.strip()
        if id_str:
            try:
                admin_ids.append(int(id_str))
            except ValueError:
                pass
    return admin_ids


class User(Base):
    """User model for storing Telegram user information."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    total_spent = Column(Float, default=0.0, nullable=False)
    total_sms_received = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    access_logs = relationship('AccessLog', back_populates='user', cascade='all, delete-orphan')
    number_holds = relationship('NumberHold', back_populates='user', cascade='all, delete-orphan')
    transactions = relationship('Transaction', back_populates='user', cascade='all, delete-orphan')
    recharge_requests = relationship('RechargeRequest', back_populates='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username}, is_admin={self.is_admin}, is_banned={self.is_banned}, balance={self.balance})>"


class AccessLog(Base):
    """Access log model for tracking user actions."""
    __tablename__ = 'access_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    action = Column(String(255), nullable=False)
    
    # Relationship to user
    user = relationship('User', back_populates='access_logs')
    
    def __repr__(self):
        return f"<AccessLog(user_id={self.user_id}, action={self.action}, timestamp={self.timestamp})>"


class NumberHold(Base):
    """Model for tracking temporary and permanent number holds."""
    __tablename__ = 'number_holds'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    phone_number = Column(String(50), nullable=False, index=True)
    range_id = Column(String(50), nullable=False)
    hold_start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    first_retry_time = Column(DateTime, nullable=True)
    is_permanent = Column(Boolean, default=False, nullable=False)
    
    # Relationship to user
    user = relationship('User', back_populates='number_holds')
    
    def __repr__(self):
        return f"<NumberHold(user_id={self.user_id}, phone_number={self.phone_number}, is_permanent={self.is_permanent})>"


class PriceRange(Base):
    """Model for storing SMS price ranges."""
    __tablename__ = 'price_ranges'
    
    id = Column(Integer, primary_key=True)
    range_pattern = Column(String(255), nullable=False, unique=True)
    price = Column(Float, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<PriceRange(range_pattern={self.range_pattern}, price={self.price})>"


class Transaction(Base):
    """Model for tracking user balance transactions."""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    amount = Column(Float, nullable=False)  # Positive for credit, negative for debit
    transaction_type = Column(String(50), nullable=False)  # 'recharge', 'sms_charge', 'admin_add', 'admin_deduct'
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to user
    user = relationship('User', back_populates='transactions')
    
    def __repr__(self):
        return f"<Transaction(user_id={self.user_id}, amount={self.amount}, type={self.transaction_type})>"


class RechargeRequest(Base):
    """Model for user recharge requests."""
    __tablename__ = 'recharge_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(20), default='pending', nullable=False)  # 'pending', 'approved', 'rejected'
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, nullable=True)  # Store admin user ID directly, no FK
    
    # Relationships
    user = relationship('User', back_populates='recharge_requests')
    
    def __repr__(self):
        return f"<RechargeRequest(user_id={self.user_id}, amount={self.amount}, status={self.status})>"


def init_db(db_path='bot.db'):
    """Initialize the database and create tables. Returns a session factory."""
    db_url = f'sqlite:///{db_path}'
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory


def get_or_create_user(db_session, telegram_id, username=None):
    """Get existing user or create a new one."""
    user = db_session.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        db_session.add(user)
        db_session.commit()
    return user


def log_access(db_session, user, action):
    """Log user access action."""
    log = AccessLog(user_id=user.id, action=action)
    db_session.add(log)
    db_session.commit()


def is_user_admin(db_session, telegram_id):
    """Check if user is an admin (checks both environment and database)."""
    # Check if user is in ADMIN_TELEGRAM_IDS from environment
    admin_ids = get_admin_telegram_ids()
    if telegram_id in admin_ids:
        return True
    
    # Also check database for dynamically granted admin status
    user = db_session.query(User).filter_by(telegram_id=telegram_id).first()
    return user and user.is_admin


def is_user_banned(db_session, telegram_id):
    """Check if user is banned."""
    user = db_session.query(User).filter_by(telegram_id=telegram_id).first()
    return user and user.is_banned


def get_user_balance(db_session, user):
    """Get user balance."""
    return user.balance


def add_user_balance(db_session, user, amount, transaction_type='admin_add', description=None):
    """Add balance to user account."""
    user.balance += amount
    transaction = Transaction(
        user_id=user.id,
        amount=amount,
        transaction_type=transaction_type,
        description=description
    )
    db_session.add(transaction)
    db_session.commit()
    return user.balance


def deduct_user_balance(db_session, user, amount, transaction_type='sms_charge', description=None):
    """Deduct balance from user account."""
    if user.balance < amount:
        return None  # Insufficient balance
    user.balance -= amount
    user.total_spent += amount
    transaction = Transaction(
        user_id=user.id,
        amount=-amount,
        transaction_type=transaction_type,
        description=description
    )
    db_session.add(transaction)
    db_session.commit()
    return user.balance


def get_price_for_range(db_session, range_id):
    """Get price for a specific range based on pattern matching."""
    # Get all price ranges ordered by creation date (most recent first)
    price_ranges = db_session.query(PriceRange).order_by(PriceRange.created_at.desc()).all()
    
    for price_range in price_ranges:
        # Simple pattern matching - check if pattern is in range_id
        if price_range.range_pattern.lower() in str(range_id).lower():
            return price_range.price
    
    # Default price if no pattern matches
    return 1.0


def create_number_holds(db_session, user, phone_numbers, range_id):
    """Create temporary holds for phone numbers."""
    from datetime import datetime
    
    # Release all non-permanent holds for this user
    db_session.query(NumberHold).filter_by(
        user_id=user.id,
        is_permanent=False
    ).delete()
    
    # Create new holds
    holds = []
    for phone in phone_numbers:
        hold = NumberHold(
            user_id=user.id,
            phone_number=str(phone),
            range_id=str(range_id),
            hold_start_time=datetime.utcnow()
        )
        holds.append(hold)
        db_session.add(hold)
    
    db_session.commit()
    return holds


def mark_number_permanent(db_session, user, phone_number):
    """Mark a number hold as permanent when SMS is received."""
    hold = db_session.query(NumberHold).filter_by(
        user_id=user.id,
        phone_number=str(phone_number),
        is_permanent=False
    ).first()
    
    if hold:
        hold.is_permanent = True
        user.total_sms_received += 1
        db_session.commit()
        return True
    return False


def get_held_numbers(db_session, user_id=None):
    """Get all held numbers, optionally filtered by user."""
    query = db_session.query(NumberHold)
    if user_id:
        query = query.filter_by(user_id=user_id)
    return query.all()


def is_number_held(db_session, phone_number):
    """Check if a phone number is currently held by any user."""
    hold = db_session.query(NumberHold).filter_by(phone_number=str(phone_number)).first()
    return hold is not None


def cleanup_expired_holds(db_session):
    """Remove holds that have expired (5 minutes after first retry)."""
    from datetime import datetime, timedelta
    
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    
    # Delete non-permanent holds where first_retry_time is set and more than 5 minutes ago
    db_session.query(NumberHold).filter(
        NumberHold.is_permanent == False,
        NumberHold.first_retry_time.isnot(None),
        NumberHold.first_retry_time < five_minutes_ago
    ).delete()
    
    db_session.commit()


def update_first_retry_time(db_session, user, phone_number):
    """Update first retry time for a number hold."""
    hold = db_session.query(NumberHold).filter_by(
        user_id=user.id,
        phone_number=str(phone_number)
    ).first()
    
    if hold and not hold.first_retry_time:
        hold.first_retry_time = datetime.utcnow()
        db_session.commit()
        return True
    return False
