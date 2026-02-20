"""Database models and initialization for the Telegram bot."""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to access logs
    access_logs = relationship('AccessLog', back_populates='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username}, is_admin={self.is_admin})>"


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
