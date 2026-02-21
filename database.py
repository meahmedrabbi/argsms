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


class Range(Base):
    """Model for storing SMS ranges uploaded via CSV."""
    __tablename__ = 'ranges'
    
    id = Column(Integer, primary_key=True)
    unique_id = Column(String(255), unique=True, nullable=False, index=True)  # Generated hash
    name = Column(String(255), nullable=False, index=True)  # e.g., "Russia Lion Whatsapp 24 Oct"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    phone_numbers = relationship('PhoneNumber', back_populates='range', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Range(unique_id={self.unique_id}, name={self.name})>"


class PhoneNumber(Base):
    """Model for storing individual phone numbers from CSV upload."""
    __tablename__ = 'phone_numbers'
    
    id = Column(Integer, primary_key=True)
    range_id = Column(Integer, ForeignKey('ranges.id'), nullable=False, index=True)
    number = Column(String(50), nullable=False, index=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    range = relationship('Range', back_populates='phone_numbers')
    number_holds = relationship('NumberHold', back_populates='phone_number', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<PhoneNumber(number={self.number}, range_id={self.range_id})>"


class NumberHold(Base):
    """Model for tracking temporary and permanent number holds."""
    __tablename__ = 'number_holds'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    phone_number_id = Column(Integer, ForeignKey('phone_numbers.id'), nullable=True, index=True)  # NULL for legacy holds
    phone_number_str = Column(String(50), nullable=False, index=True)  # Keep for backward compatibility
    range_id = Column(String(50), nullable=False)  # Range unique_id
    hold_start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    first_retry_time = Column(DateTime, nullable=True)
    is_permanent = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    user = relationship('User', back_populates='number_holds')
    phone_number = relationship('PhoneNumber', back_populates='number_holds')
    
    def __repr__(self):
        return f"<NumberHold(user_id={self.user_id}, phone_number={self.phone_number_str}, is_permanent={self.is_permanent})>"


class PriceRange(Base):
    """Model for storing SMS price ranges by unique range ID."""
    __tablename__ = 'price_ranges'
    
    id = Column(Integer, primary_key=True)
    range_unique_id = Column(String(255), nullable=False, unique=True, index=True)  # Links to Range.unique_id
    range_name = Column(String(255), nullable=False)  # For display purposes
    price = Column(Float, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<PriceRange(range_unique_id={self.range_unique_id}, range_name={self.range_name}, price={self.price})>"


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


def migrate_database(engine):
    """Migrate existing database to add new columns and tables."""
    import sqlite3
    
    db_path = engine.url.database
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check and add missing columns to users table
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'is_banned' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0 NOT NULL")
        
        if 'balance' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0 NOT NULL")
        
        if 'total_spent' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN total_spent REAL DEFAULT 0.0 NOT NULL")
        
        if 'total_sms_received' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN total_sms_received INTEGER DEFAULT 0 NOT NULL")
        
        # Check and add new columns to number_holds table if it exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='number_holds'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(number_holds)")
            hold_columns = [row[1] for row in cursor.fetchall()]
            
            if 'phone_number_id' not in hold_columns:
                cursor.execute("ALTER TABLE number_holds ADD COLUMN phone_number_id INTEGER")
            
            if 'phone_number_str' not in hold_columns:
                # Rename phone_number to phone_number_str if needed
                if 'phone_number' in hold_columns:
                    # SQLite doesn't support column rename directly, so we copy data
                    cursor.execute("ALTER TABLE number_holds RENAME TO number_holds_old")
                    cursor.execute("""
                        CREATE TABLE number_holds (
                            id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            phone_number_id INTEGER,
                            phone_number_str VARCHAR(50) NOT NULL,
                            range_id VARCHAR(50) NOT NULL,
                            hold_start_time DATETIME NOT NULL,
                            first_retry_time DATETIME,
                            is_permanent BOOLEAN NOT NULL
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO number_holds 
                        (id, user_id, phone_number_id, phone_number_str, range_id, hold_start_time, first_retry_time, is_permanent)
                        SELECT id, user_id, NULL, phone_number, range_id, hold_start_time, first_retry_time, is_permanent
                        FROM number_holds_old
                    """)
                    cursor.execute("DROP TABLE number_holds_old")
        
        # Check and update price_ranges table if it exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='price_ranges'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(price_ranges)")
            price_columns = [row[1] for row in cursor.fetchall()]
            
            if 'range_pattern' in price_columns and 'range_unique_id' not in price_columns:
                # Migrate from pattern-based to unique_id-based
                cursor.execute("ALTER TABLE price_ranges RENAME TO price_ranges_old")
                cursor.execute("""
                    CREATE TABLE price_ranges (
                        id INTEGER PRIMARY KEY,
                        range_unique_id VARCHAR(255) NOT NULL UNIQUE,
                        range_name VARCHAR(255) NOT NULL,
                        price REAL NOT NULL,
                        created_by INTEGER NOT NULL,
                        created_at DATETIME NOT NULL
                    )
                """)
                # Note: Old data can't be migrated automatically as we don't have unique_id mapping
                # Admin will need to re-set prices after CSV upload
                cursor.execute("DROP TABLE price_ranges_old")
        
        conn.commit()
        conn.close()
    except Exception:
        pass


def init_db(db_path='bot.db'):
    """Initialize the database and create tables. Returns a session factory."""
    db_url = f'sqlite:///{db_path}'
    engine = create_engine(db_url, echo=False)
    
    # Migrate existing database
    migrate_database(engine)
    
    # Create new tables
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


def get_price_for_range(db_session, range_unique_id):
    """Get price for a specific range by unique ID."""
    price_range = db_session.query(PriceRange).filter_by(range_unique_id=str(range_unique_id)).first()
    
    if price_range:
        return price_range.price
    
    # Default price if no price set for this range
    return 1.0


def create_number_holds(db_session, user, phone_number_ids, range_unique_id):
    """Create temporary holds for phone numbers."""
    from datetime import datetime
    
    # Release all non-permanent holds for this user
    db_session.query(NumberHold).filter_by(
        user_id=user.id,
    ).filter(NumberHold.is_permanent.is_(False)).delete()
    
    # Create new holds
    holds = []
    for phone_number_id in phone_number_ids:
        # Get the phone number object
        phone_number = db_session.query(PhoneNumber).get(phone_number_id)
        if phone_number:
            hold = NumberHold(
                user_id=user.id,
                phone_number_id=phone_number.id,
                phone_number_str=phone_number.number,
                range_id=str(range_unique_id),
                hold_start_time=datetime.utcnow()
            )
            holds.append(hold)
            db_session.add(hold)
    
    db_session.commit()
    return holds


def mark_number_permanent(db_session, user, phone_number_str):
    """Mark a number hold as permanent when SMS is received."""
    hold = db_session.query(NumberHold).filter_by(
        user_id=user.id,
        phone_number_str=str(phone_number_str)
    ).filter(NumberHold.is_permanent.is_(False)).first()
    
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


def is_number_held(db_session, phone_number_str):
    """Check if a phone number is currently held by any user."""
    hold = db_session.query(NumberHold).filter_by(phone_number_str=str(phone_number_str)).first()
    return hold is not None


def cleanup_expired_holds(db_session):
    """Remove holds that have expired (5 minutes after first retry)."""
    from datetime import datetime, timedelta
    
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    
    # Delete non-permanent holds where first_retry_time is set and more than 5 minutes ago
    db_session.query(NumberHold).filter(
        NumberHold.is_permanent.is_(False),
        NumberHold.first_retry_time.isnot(None),
        NumberHold.first_retry_time < five_minutes_ago
    ).delete()
    
    db_session.commit()


def update_first_retry_time(db_session, user, phone_number_str):
    """Update first retry time for a number hold."""
    hold = db_session.query(NumberHold).filter_by(
        user_id=user.id,
        phone_number_str=str(phone_number_str)
    ).first()
    
    if hold and not hold.first_retry_time:
        hold.first_retry_time = datetime.utcnow()
        db_session.commit()
        return True
    return False


# CSV Upload and Range Management Functions

def generate_range_unique_id(range_name):
    """Generate a unique ID for a range based on its name."""
    import hashlib
    # Create a hash of the range name for unique ID
    return hashlib.md5(range_name.encode()).hexdigest()[:16]


def import_csv_data(db_session, csv_file_path):
    """
    Import ranges and phone numbers from CSV file.
    Expected CSV columns: Range, Number (other columns ignored)
    Returns: (success_count, error_count, errors_list)
    """
    import csv
    
    success_count = 0
    error_count = 0
    errors = []
    range_cache = {}  # Cache to avoid repeated DB queries
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
            # Try to detect the delimiter
            sample = csvfile.read(1024)
            csvfile.seek(0)
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
                reader = csv.DictReader(csvfile, dialect=dialect)
            except:
                reader = csv.DictReader(csvfile)
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
                try:
                    # Get range and number (case-insensitive)
                    range_name = None
                    number = None
                    
                    for key in row.keys():
                        if key and key.strip().lower() == 'range':
                            range_name = row[key].strip()
                        elif key and key.strip().lower() == 'number':
                            number = row[key].strip()
                    
                    if not range_name or not number:
                        errors.append(f"Row {row_num}: Missing Range or Number")
                        error_count += 1
                        continue
                    
                    # Get or create range
                    if range_name not in range_cache:
                        unique_id = generate_range_unique_id(range_name)
                        range_obj = db_session.query(Range).filter_by(unique_id=unique_id).first()
                        if not range_obj:
                            range_obj = Range(unique_id=unique_id, name=range_name)
                            db_session.add(range_obj)
                            db_session.flush()  # Get the ID
                        range_cache[range_name] = range_obj
                    else:
                        range_obj = range_cache[range_name]
                    
                    # Check if number already exists
                    existing = db_session.query(PhoneNumber).filter_by(number=number).first()
                    if existing:
                        # Update range if different
                        if existing.range_id != range_obj.id:
                            existing.range_id = range_obj.id
                            success_count += 1
                    else:
                        # Create new phone number
                        phone_number = PhoneNumber(
                            range_id=range_obj.id,
                            number=number
                        )
                        db_session.add(phone_number)
                        success_count += 1
                
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
            
            db_session.commit()
            
    except Exception as e:
        db_session.rollback()
        errors.append(f"File error: {str(e)}")
        error_count += 1
    
    return success_count, error_count, errors


def get_all_ranges(db_session):
    """Get all ranges with count of phone numbers."""
    from sqlalchemy import func
    
    ranges = db_session.query(
        Range,
        func.count(PhoneNumber.id).label('number_count')
    ).outerjoin(PhoneNumber).group_by(Range.id).order_by(Range.name).all()
    
    return [(r, count) for r, count in ranges]


def get_range_by_unique_id(db_session, unique_id):
    """Get a range by its unique ID."""
    return db_session.query(Range).filter_by(unique_id=unique_id).first()


def get_available_numbers_for_range(db_session, range_unique_id, limit=100):
    """
    Get available phone numbers for a range (not currently held).
    Returns list of PhoneNumber objects.
    """
    range_obj = db_session.query(Range).filter_by(unique_id=range_unique_id).first()
    if not range_obj:
        return []
    
    # Get phone numbers that are not currently held (temporary or permanent)
    held_number_ids = db_session.query(NumberHold.phone_number_id).filter(
        NumberHold.phone_number_id.isnot(None)
    ).distinct().subquery()
    
    available_numbers = db_session.query(PhoneNumber).filter(
        PhoneNumber.range_id == range_obj.id,
        ~PhoneNumber.id.in_(held_number_ids)
    ).limit(limit).all()
    
    return available_numbers


def delete_range_and_numbers(db_session, range_unique_id):
    """Delete a range and all its associated phone numbers."""
    range_obj = db_session.query(Range).filter_by(unique_id=range_unique_id).first()
    if range_obj:
        db_session.delete(range_obj)
        db_session.commit()
        return True
    return False


def set_range_price(db_session, range_unique_id, range_name, price, admin_user):
    """Set or update price for a range."""
    price_range = db_session.query(PriceRange).filter_by(range_unique_id=range_unique_id).first()
    
    if price_range:
        price_range.price = price
        price_range.range_name = range_name
    else:
        price_range = PriceRange(
            range_unique_id=range_unique_id,
            range_name=range_name,
            price=price,
            created_by=admin_user.id
        )
        db_session.add(price_range)
    
    db_session.commit()
    return price_range
