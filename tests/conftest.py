
import json
import os
import sys
import pytest

# Вставляем корень проекта в sys.path, чтобы был доступен импорт app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, users as global_users

@pytest.fixture
def client():
    app.config['TESTING'] = True
    global_users.clear()
    with app.test_client() as c:
        yield c

