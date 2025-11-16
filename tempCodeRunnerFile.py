# tools_reschedule.py
import logging
from datetime import datetime
# --- TEMPORAR COMENTAT (cauzează 'hang') ---
# from pydantic import BaseModel, Field
# from langchain_core.tools import *
# ---

from db_connector import db, firestore

# --- Logică Internă (Helper) ---

def _get_client_rules(client_phone):
    """(Helper) Prelucrează profilul unui client din 'client_profile'."""
    if db is None: return None
    try:
        client_ref = db.collection('client_profile').document(client_phone)
        client_data = client_ref.get()
        return client_data.to_dict() if client_data.exists else None
    except Exception as e:
        logging.error(f"Eroare la citirea profilului clientului {client_phone}: {e}")
        return None

def _get_delivery_task(awb):
    """(Helper) Prelucrează sarcina de livrare din 'pending_deliveries'."""
    if db is None: return None
    try:
        task_ref = db.collection('pending_deliveries').document(awb)
        task_data = task_ref.get()
        return task_data.to_dict() if task_data.exists else None
    except Exception as e:
        logging.error(f"Eroare la citirea sarcinii {awb}: {e}")
        return None

# --- TOOL 1: Obținerea Opțiunilor ---

# --- TEMPORAR COMENTAT (clasa Pydantic) ---
# class DeliveryOptionsInput(BaseModel):
#     awb: str = Field(description="AWB-ul pachetului care trebuie reprogramat.")

# --- TEMPORAR COMENTAT (decoratorul @tool) ---
# @tool(args_schema=DeliveryOptionsInput)
def get_delivery_options(awb: str) -> str:
    """
    (Versiune de test, fără @tool)
    Folosește acest tool pentru a afla ce opțiuni VALIDE de reprogramare 
    sunt disponibile pentru un AWB specific.
    """
    logging.info(f"Rulez 'get_delivery_options' pentru AWB: {awb}")
    
    task_data = _get_delivery_task(awb)
    if not task_data:
        return f"Eroare: Nu am găsit nicio livrare în așteptare cu AWB-ul {awb}."
    
    courier_dates = task_data.get('available_delivery_dates', [])
    client_phone = task_data.get('customer_phone')
    
    if not courier_dates or not client_phone:
        return f"Eroare: Datele pentru AWB {awb} sunt incomplete."

    profile = _get_client_rules(client_phone)
    valid_dates_final = []

    if profile is None:
        logging.info(f"Clientul {client_phone} nu are profil. Toate datele curierului sunt valide.")
        return str(courier_dates)

    recurrence_rules = profile.get('recurrences', [])
    exception_rules = profile.get('exceptii_specifice', {})

    for date_str in courier_dates:
        try:
            courier_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            logging.warning(f"Data de la curier '{date_str}' are un format invalid. Ignor...")
            continue

        is_valid = True 
        if date_str in exception_rules:
            is_valid = exception_rules[date_str]
            logging.info(f"Data {date_str} a fost găsită în EXCEPȚII: Permis = {is_valid}")
            if is_valid:
                valid_dates_final.append(date_str)
            continue
        
        found_matching_rule = False
        for rule in recurrence_rules:
            if rule.get('type') != 'weekly':
                continue 

            try:
                rule_start_date = datetime.strptime(rule['start_date'], "%Y-%m-%d").date()
                rule_interval = int(rule['interval'])
                rule_availability = bool(rule['available'])
                
                rule_end_date = None
                if 'end_date' in rule and rule['end_date']:
                    rule_end_date = datetime.strptime(rule['end_date'], "%Y-%m-%d").date()

                if courier_date.weekday() == rule_start_date.weekday():
                    if courier_date >= rule_start_date:
                        
                        if rule_end_date and courier_date > rule_end_date:
                            logging.info(f"Regula {rule} a expirat pentru {date_str}. Se ignoră.")
                            continue 
                        
                        delta_days = (courier_date - rule_start_date).days
                        delta_weeks = delta_days / 7
                        
                        if delta_weeks % rule_interval == 0:
                            is_valid = rule_availability
                            logging.info(f"Data {date_str} a activat o regulă recurentă: Permis = {is_valid}")
                            found_matching_rule = True
                            break 
            
            except Exception as e:
                logging.error(f"Eroare la parsarea unei reguli recurente: {e}")

        if is_valid and not found_matching_rule:
            is_valid = True
            
        if is_valid:
            valid_dates_final.append(date_str)

    if not valid_dates_final:
        return f"Din păcate, conform regulilor setate, niciuna din datele curierului ({courier_dates}) nu este validă."
    
    return str(valid_dates_final)

# --- TOOL 2: Confirmarea Deciziei ---
# (Am comentat și aici Pydantic și @tool)

# class ConfirmRescheduleInput(BaseModel):
#     awb: str = Field(description="AWB-ul pachetului care este confirmat.")
#     chosen_date: str = Field(description="Data finală aleasă de client, în format YYYY-MM-DD.")
#     client_phone: str = Field(description="Numărul de telefon al clientului, necesar pentru a salva în istoric.")

# @tool(args_schema=ConfirmRescheduleInput)
def confirm_rescheduled_delivery(awb: str, chosen_date: str, client_phone: str) -> str:
    """(Versiune de test, fără @tool)"""
    logging.info(f"Rulez 'confirm_rescheduled_delivery' pentru AWB: {awb} la data {chosen_date}")
    
    if db is None: return "Eroare: Conexiunea la DB a eșuat."
        
    try:
        doc_ref = db.collection('pending_deliveries').document(awb)
        doc_ref.update({
            'status': 'rescheduled_confirmed_by_chat',
            'processed_at': firestore.SERVER_TIMESTAMP,
            'final_delivery_date': chosen_date
        })
        
        try:
            history_ref = db.collection('client_history').document()
            pasi_string = f"Reprogramat AWB {awb} la cererea clientului pentru data de {chosen_date}."
            history_ref.set({
                'client_phone': client_phone,
                'data_eveniment': firestore.SERVER_TIMESTAMP,
                'pasi': pasi_string,
                'awb_asociat': awb
            })
            logging.info(f"Eveniment adăugat în 'client_history' pentru {client_phone}.")
        except Exception as history_e:
            logging.error(f"Eroare la scrierea în 'client_history': {history_e}")

        logging.info(f"Simulare: Se trimite confirmarea API către curier pentru AWB {awb}...")
        
        return f"Succes! Am confirmat reprogramarea pentru AWB {awb} în data de {chosen_date} și am salvat acest eveniment."
    
    except Exception as e:
        return f"Eroare la înregistrarea deciziei finale pentru {awb}: {e}"
    
if __name__ == "__main__":
    """
    Bloc de testare simplificat, fără LangChain.
    """
    
    logging.basicConfig(level=logging.INFO)
    logging.info("--- [MOD DE TESTARE SIMPLU (fără LangChain)] ---")
    
    AWB_DE_TESTAT = "AWB_TEST_COMPLEX" # Asigură-te că există!
    
    logging.info(f"Se testează 'get_delivery_options' cu AWB: {AWB_DE_TESTAT}...")
    
    # --- MODIFICARE: Apelăm funcția normal, fără .func ---
    rezultat_string = get_delivery_options(awb=AWB_DE_TESTAT)
    
    logging.info(f"\nREZULTATUL TOOL-ULUI:\n {rezultat_string}\n")

    logging.info("--- Analiza Rezultatului Așteptat ---")
    logging.info("2025-11-16 (Duminică): RESPINS (Excepție 'false')")
    logging.info("2025-11-17 (Luni): RESPINS (Excepție 'false')")
    logging.info("2025-11-18 (Marți): VALID (Nicio excepție, nicio recurență)")
    logging.info("2025-11-19 (Miercuri): VALID (Nicio excepție, nicio recurență)")
    logging.info("2025-11-20 (Joi): VALID (Excepție 'true')")
    logging.info("2025-11-24 (Luni): VALID (Regulile recurente au expirat înainte de această dată)")
    
    rezultat_asteptat = "['2025-11-18', '2025-11-19', '2025-11-20', '2025-11-24']"
    
    if rezultat_string == rezultat_asteptat:
        logging.info("✅ SUCCES: Logica de recurență și excepții funcționează corect!")
    else:
        logging.error(f"❌ EȘEC: Rezultatul a fost diferit de cel așteptat.")
        logging.error(f"   AȘTEPTAT: {rezultat_asteptat}")
        logging.error(f"   PRIMIT:   {rezultat_string}")