"""Veritabani baglanti ayarlari."""
import os

import mysql.connector

# Production'da bu degerler DIKA_DB_* ortam degiskenleriyle override edilmeli;
# asagidaki varsayilanlar yalnizca yerel gelistirme icindir.
db_config = {
    'host': os.environ.get('DIKA_DB_HOST', '127.0.0.1'),
    'user': os.environ.get('DIKA_DB_USER', 'root'),
    'password': os.environ.get('DIKA_DB_PASSWORD', ''),
    'database': os.environ.get('DIKA_DB_NAME', 'dika_db'),
    'charset': 'utf8mb4'
}


def get_db():
    return mysql.connector.connect(**db_config)
