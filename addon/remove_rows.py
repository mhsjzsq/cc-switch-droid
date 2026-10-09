import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".cc-switch" / "cc-switch.db"
conn = sqlite3.connect(str(db), timeout=30)
try:
    with conn:
        n = conn.execute("DELETE FROM proxy_request_logs WHERE data_source = 'droid_session'").rowcount
finally:
    conn.close()
print(f"已删除 {n} 条")
