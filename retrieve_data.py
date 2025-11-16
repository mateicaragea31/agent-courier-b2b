from db_connector import db, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import logging

def get_pending_deliveries():
    """Retrieve pe rand la sarcinile din pending_deliveries"""

    logging.info("Interoghez baza de date pentru sarcini cu status 'recieved'.")

    if db is None:
        logging.error("Conexiunea la DB nu este activa. Lista goala va fi returnata.")
        return []
    
    try:
        pending_ref = db.collection('pending_deliveries') # referinta la coada de comenzi cu status 'recieved'
        tasks_query = pending_ref.where(filter = FieldFilter('status', '==', 'received')) # construieste interogarea

        tasks_stream = tasks_query.stream() # aplica interogarea si da rezultate piece by piece
        tasks_list = list(tasks_stream) # converteste raspunsul intr-o lista

        return tasks_list
    except Exception as e:
        logging.error(f"Eroare la preluarea valorilor din Firestore. {e}")
        return []

"""
## --- Testare ----
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("--- [MOD DE TESTARE SIMPLU PENTRU RETRIEVAL] ---")

    comenzi_gasite = get_pending_deliveries()
    if not comenzi_gasite:
        logging.warning("Nu exista comenzi gata de livare.")
    else:
        logging.info(f"SUCCES! Am gasit {len(comenzi_gasite)}")
        for i, task_doc in enumerate(comenzi_gasite):
            print(f"Sarcina {i + 1}: ID = {task_doc.id} (AWB)")

    logging.info("--- [MOD TESTARE INCHEIAT] ---")
"""