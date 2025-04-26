# models.py
from sqlalchemy import create_engine, Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Создаем базовый класс для моделей
Base = declarative_base()

class Block(Base):
    __tablename__ = 'blocks'
    id = Column(Integer, primary_key=True)  # Автоинкрементное значение
    index = Column(Integer, unique=True)
    timestamp = Column(Float)
    proof = Column(Integer)
    difficulty = Column(Integer)
    previous_hash = Column(String(256))
    merkle_root = Column(String(256))
    transactions = Column(Text)  # Сохраним транзакции в виде JSON-строки

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    email = Column(String(120), nullable=True)
    name = Column(String(120), nullable=True)

# Создаем движок и сессию для SQLite
engine = create_engine('sqlite:///blockchain.db')
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
