# metrics.py
from prometheus_client import Counter, Gauge

blocks_mined_total = Counter('blocks_mined_total', 'Total number of blocks mined')
transactions_total = Counter('transactions_total', 'Total number of transactions processed')
pending_transactions_gauge = Gauge('pending_transactions', 'Number of pending transactions')
transactions_processed = Counter('transactions_processed_total', 'Total number of transactions processed')
# Определите и другие метрики, если нужно