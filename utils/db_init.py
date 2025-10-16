import sqlite3
from pathlib import Path

db_path = Path("database/result.db")
db_path.parent.mkdir(exist_ok=True)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Bảng nhật ký task
c.execute("""
CREATE TABLE IF NOT EXISTS tasks_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    task_id TEXT,
    status TEXT,
    start_time REAL,
    end_time REAL,
    duration REAL,
    worker_name TEXT,
    result_path TEXT,
    recognized_name TEXT,
    error TEXT
)
""")

# Bảng thống kê hiệu năng
c.execute("""
CREATE TABLE IF NOT EXISTS performance_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT,
    num_images INTEGER,
    total_time REAL,
    avg_time REAL,
    timestamp TEXT
)
""")

# (Tùy chọn) Bảng người đã biết
c.execute("""
CREATE TABLE IF NOT EXISTS known_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    image_path TEXT,
    encoding_vector BLOB
)
""")

conn.commit()
conn.close()

print("✅ Database initialized successfully!")
