"""Veritabani baglanti ayarlari."""
import mysql.connector

db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'dika_db',
    'charset': 'utf8mb4'
}


def get_db():
    return mysql.connector.connect(**db_config)
