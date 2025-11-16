# db_connector.py
import firebase_admin
from firebase_admin import credentials, firestore
import logging

# Numele fișierului JSON pe care l-ai descărcat la Pasul 1
KEY_FILE = "serviceAccountKey.json"

# Inițializăm o variabilă globală pentru DB
db = None

try:
    # 1. Încarcă cheia de serviciu
    cred = credentials.Certificate(KEY_FILE)
    
    # 2. Inițializează aplicația Firebase
    firebase_admin.initialize_app(cred)
    
    # 3. Obține clientul pentru Firestore
    db = firestore.client()
    
    logging.warning("✅ Conectat cu succes la Firestore!")

except FileNotFoundError:
    logging.error(f"❌ EROARE CRITICĂ: Fișierul cheie '{KEY_FILE}' nu a fost găsit.")
    logging.error("   Asigură-te că l-ai descărcat de pe Firebase și l-ai pus în același folder.")
except ValueError:
    # Asta se întâmplă dacă 'uvicorn --reload' reîncarcă fișierul
    # și încearcă să inițializeze o aplicație deja inițializată.
    db = firestore.client() # Ne asigurăm că 'db' este asignat
    logging.info("ℹ️ Conexiunea Firestore era deja inițializată.")
except Exception as e:
    logging.error(f"❌ EROARE Necunoscută la conectarea cu Firebase: {e}")