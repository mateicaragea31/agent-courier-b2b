import sqlite3
from typing import List, Tuple

DB_PATH = "data.db"

def create_table(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pasi_client (
            id_client INTEGER PRIMARY KEY NOT NULL,
            data TEXT NOT NULL,
            pasi TEXT NOT NULL 
        )
        """
    )
    conn.commit()
    conn.close()

def insert_record(id_client: int, date_str: str, pasi: int, db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pasi_client (id_client, data, pasi) VALUES (?, ?, ?)",
        (id_client, date_str, pasi),
    )
    conn.commit()
    conn.close()

def fetch_all(db_path: str = DB_PATH) -> List[Tuple]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, id_client, data, pasi FROM pasi_client")
    rows = cur.fetchall()
    conn.close()
    return rows

create_table()