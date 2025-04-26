from sqlalchemy import inspect
from models import engine  # Убедитесь, что engine импортирован из вашего модуля моделей

inspector = inspect(engine)
columns = inspector.get_columns('blocks')
for column in columns:
    print(column['name'], column['type'])