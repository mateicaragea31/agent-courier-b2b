from pydantic import BaseModel, Field
#from langchain_core.tools import *

from db_connector import db, firestore

import logging

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

class RescheduleInput(BaseModel):
    """ Input pentru query-uri de delivery"""
    awb: str = Field(description = "Awb-ul pachetului confirmat.")
    client_phone: str = Field(description = "NNumărul de telefon al clientului, necesar pentru a salva în istoric.")
    new_delivery_date: str = Field(description = "Data finală de livrare aleasă de client, în format YYYY-MM-DD.")

#@tool(args_schema=RescheduleInput)
def send_new_schedule(awb: str, client_phone: str, new_delivery_date: str):
    """
    Recieves a new schedule for delivery and sends it back to the delivery service.
    """
    logging.info(f"Rulez 'reschedule_and_notify_courier' pentru AWB: {awb} la data {new_delivery_date}")
    
    if db is None:
        return "Eroare: Conexiunea la DB a eșuat. Nu s-a putut confirma reprogramarea."

    try:
        # Actulizez request-ul din coada
        doc_ref = db.collection('pending_deliveries').document(awb)
        if not doc_ref.get().exists:
            return f"Eroare: Nu am găsit AWB-ul {awb} în 'pending_deliveries'. Imposibil de reprogramat."
        doc_ref.update({
            'status' : 'processed',
            'processed_at' : firestore.SERVER_TIMESTAMP,
            'final_delivery_date' : new_delivery_date
        })

        try:
            history_ref = db.collection('client_history').document()
            pasi_string = f"Livrarea coletului pentru clientul {client_phone} a fost reprogramata la data de {new_delivery_date}."

            history_ref.set({
                'client_phone' : client_phone,
                'awb_asociat' : awb,
                'pasi' : pasi_string,
                'Data' : firestore.SERVER_TIMESTAMP
            })

        except Exception as history_e:
            logging.error(f"Eroare la scrierea în 'client_history': {history_e}")
        
        logging.info(f"SIMULARE: Se trimite confirmarea API către curier pentru AWB {awb} cu noua dată {new_delivery_date}...")
        return f"Succes! Am confirmat reprogramarea pentru AWB {awb} în data de {new_delivery_date} și am notificat curierul."
    
    except Exception as e:
       logging.error(f"Eroare la actualizarea datei finale! {e}")

"""
# BLOC TESTARE     
if __name__ == "__main__":
    # --- Datele pe care le vom simula (ca și cum ar veni de la Agent) ---
    AWB_DE_TESTAT = "AWB_TEST_COMPLEX" # Asigură-te că există în 'pending_deliveries'
    DATA_ALEASA = "2025-11-25" # O dată nouă, aleasă de client
    CLIENT_TELEFON = "0722000123" # Telefonul asociat cu AWB-ul
    
    logging.info(f"Se testează 'reschedule_and_notify_courier' cu AWB: {AWB_DE_TESTAT}...")
    
    # Apelăm funcția .func() a tool-ului
    rezultat_string = send_new_schedule(
        client_phone=CLIENT_TELEFON,
        awb=AWB_DE_TESTAT, 
        new_delivery_date=DATA_ALEASA,
    )
    
    logging.info(f"\nREZULTATUL TOOL-ULUI:\n {rezultat_string}\n")
    logging.info("--- [TESTARE ÎNCHEIATĂ] ---")
    logging.info("Verifică acum în Firebase:")
    logging.info(f"1. 'pending_deliveries/{AWB_DE_TESTAT}' ar trebui să aibă status 'rescheduled_confirmed...' și data '{DATA_ALEASA}'.")
    logging.info(f"2. 'client_history' ar trebui să aibă o nouă intrare pentru AWB {AWB_DE_TESTAT}.")
"""