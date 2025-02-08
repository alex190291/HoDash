import sqlite3
import time
import threading
from datetime import datetime
from queue import Queue

MAX_HISTORY = 30

class DatabaseState:
    def __init__(self):
        self.cpu_history = {'time': [], 'usage': []}
        self.memory_history_basic = {'time': [], 'free': [], 'used': [], 'cached': []}
        self.disk_history_basic = {'time': [], 'total': [], 'used': [], 'free': []}
        self.cpu_history_24h = []
        self.memory_history_24h = []
        self.disk_history = []
        self.network_history = {}

        # Locks for granular locking
        self.cpu_history_lock = threading.Lock()
        self.memory_history_basic_lock = threading.Lock()
        self.disk_history_basic_lock = threading.Lock()
        self.cpu_history_24h_lock = threading.Lock()
        self.memory_history_24h_lock = threading.Lock()
        self.disk_history_lock = threading.Lock()
        self.network_history_lock = threading.Lock()

        self.db_queue = Queue()
        self.connection_pool = []  # To simulate a connection pool for SQLite

        self._init_connection_pool()

    def _init_connection_pool(self, pool_size=5):
        for _ in range(pool_size):
            conn = sqlite3.connect("stats.db", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self.connection_pool.append(conn)

    def get_db_connection(self):
        return self.connection_pool.pop(0)  # Get a connection from the pool

    def release_db_connection(self, conn):
        self.connection_pool.append(conn)  # Return the connection back to the pool

    def get_cpu_history(self):
        with self.cpu_history_lock:
            return self.cpu_history

    def get_memory_history_basic(self):
        with self.memory_history_basic_lock:
            return self.memory_history_basic

    def get_disk_history_basic(self):
        with self.disk_history_basic_lock:
            return self.disk_history_basic

    def get_cpu_history_24h(self):
        with self.cpu_history_24h_lock:
            return self.cpu_history_24h

    def get_memory_history_24h(self):
        with self.memory_history_24h_lock:
            return self.memory_history_24h

    def get_disk_history(self):
        with self.disk_history_lock:
            return self.disk_history

    def get_network_history(self):
        with self.network_history_lock:
            return self.network_history

    def set_cpu_history(self, data):
        with self.cpu_history_lock:
            self.cpu_history = data

    def set_memory_history_basic(self, data):
        with self.memory_history_basic_lock:
            self.memory_history_basic = data

    def set_disk_history_basic(self, data):
        with self.disk_history_basic_lock:
            self.disk_history_basic = data

    def set_cpu_history_24h(self, data):
        with self.cpu_history_24h_lock:
            self.cpu_history_24h = data

    def set_memory_history_24h(self, data):
        with self.memory_history_24h_lock:
            self.memory_history_24h = data

    def set_disk_history(self, data):
        with self.disk_history_lock:
            self.disk_history = data

    def set_network_history(self, data):
        with self.network_history_lock:
            self.network_history = data

    def add_task_to_queue(self, task):
        self.db_queue.put(task)

    def process_task_queue(self):
        while True:
            task = self.db_queue.get()
            if task is None:
                break
            task()

db_state = DatabaseState()

def initialize_database():
    conn = db_state.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS cpu_history (timestamp REAL, usage REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS cpu_history_24h (timestamp REAL, usage REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS memory_history (timestamp REAL, free REAL, used REAL, cached REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS memory_history_24h (timestamp REAL, usage REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS disk_history_basic (timestamp REAL, total REAL, used REAL, free REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS disk_history_details (timestamp REAL, used REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS net_history (interface TEXT, timestamp REAL, input REAL, output REAL)")
    conn.commit()
    db_state.release_db_connection(conn)

def batch_insert_data(data_list, table_name):
    """
    Helper function to batch insert data into the specified table.
    """
    conn = db_state.get_db_connection()
    cursor = conn.cursor()
    cursor.executemany(f"INSERT INTO {table_name} (timestamp, usage) VALUES (?, ?)", data_list)
    conn.commit()
    db_state.release_db_connection(conn)

def load_history():
    """
    Load previously stored history data from the SQLite database into the global in-memory arrays.
    """
    conn = db_state.get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT timestamp, usage FROM cpu_history ORDER BY timestamp DESC LIMIT ?", (MAX_HISTORY,))
    rows = cursor.fetchall()[::-1]
    db_state.set_cpu_history({
        'time': [datetime.fromtimestamp(r['timestamp']).strftime('%H:%M:%S') for r in rows],
        'usage': [r['usage'] for r in rows]
    })

    cursor.execute("SELECT timestamp, free, used, cached FROM memory_history ORDER BY timestamp DESC LIMIT ?", (MAX_HISTORY,))
    rows = cursor.fetchall()[::-1]
    db_state.set_memory_history_basic({
        'time': [datetime.fromtimestamp(r['timestamp']).strftime('%H:%M:%S') for r in rows],
        'free': [r['free'] for r in rows],
        'used': [r['used'] for r in rows],
        'cached': [r['cached'] for r in rows]
    })

    cursor.execute("SELECT timestamp, total, used, free FROM disk_history_basic ORDER BY timestamp DESC LIMIT ?", (MAX_HISTORY,))
    rows = cursor.fetchall()[::-1]
    db_state.set_disk_history_basic({
        'time': [datetime.fromtimestamp(r['timestamp']).strftime('%H:%M:%S') for r in rows],
        'total': [r['total'] for r in rows],
        'used': [r['used'] for r in rows],
        'free': [r['free'] for r in rows]
    })

    cursor.execute("SELECT timestamp, usage FROM cpu_history_24h ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    db_state.set_cpu_history_24h([{'time': r['timestamp'], 'usage': r['usage']} for r in rows])

    cursor.execute("SELECT timestamp, usage FROM memory_history_24h ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    db_state.set_memory_history_24h([{'time': r['timestamp'], 'usage': r['usage']} for r in rows])

    cursor.execute("SELECT timestamp, used FROM disk_history_details ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    db_state.set_disk_history([{'time': r['timestamp'], 'used': r['used']} for r in rows])

    cursor.execute("SELECT interface, timestamp, input, output FROM net_history ORDER BY timestamp ASC")
    rows = cursor.fetchall()
    network_history = {}
    for row in rows:
        iface = row['interface']
        if iface not in network_history:
            network_history[iface] = []
        network_history[iface].append({
            'time': datetime.fromtimestamp(row['timestamp']).strftime('%H:%M:%S'),
            'input': row['input'],
            'output': row['output']
        })
        if len(network_history[iface]) > MAX_HISTORY:
            network_history[iface] = network_history[iface][-MAX_HISTORY:]
    db_state.set_network_history(network_history)

    db_state.release_db_connection(conn)
