import datetime
import json
import sqlite3


def get_zi_saptamanii(date):
    ZILELE_SAPTAMANII = [
        "Luni",
        "Marti",
        "Miercuri",
        "Joi",
        "Vineri",
        "Sâmbătă",
        "Duminică"
    ]
    date_object = datetime.datetime.strptime(date, "%Y-%m-%d")
    indexul_zilei = date_object.weekday()
    numele_zilei = ZILELE_SAPTAMANII[indexul_zilei]
    return numele_zilei
#
# def check_disponibility(date):
#     with open('memorie_client.json', 'r') as f:
#         data_client = json.load(f)
#     nume_zi = get_zi_saptamanii(date)
#     disponibilitate = data_client['reguli_saptamanale'].get(nume_zi, None)
#     if disponibilitate is None:
#         disponibilitate = data_client['exceptii_specifice'].get(date, None)
#     return disponibilitate
#
# def return_pasi(date):
#     conn = sqlite3.connect("data.db")
#     cur = conn.cursor()
#     cur.execute(
#         "SELECT pasi FROM pasi_client WHERE data = ?",
#         (date,),
#     )
#     row = cur.fetchone()
#     conn.close()
#     if row:
#         return row[0]
#     return "Nu există pași înregistrați pentru această dată."
#
# def return_informatii_client(date):
#     disp = check_disponibility(date)
#     if disp is None:
#         return 'nu exista informatii despre disponibilitate'
#     elif disp is False:
#         pasi = return_pasi(date)
#         return f'clientul nu este disponibil pe data de {date}. Pașii înregistrați sunt: {pasi}'
#     else:
#         return f'clientul este disponibil pe data de {date}.'
#
# print(return_informatii_client('2025-11-17'))
