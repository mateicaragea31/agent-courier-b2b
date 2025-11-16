from fastapi import FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from datetime import date
from typing import List
import logging

# Importă conexiunea la baza de date
from db_connector import db, firestore 

# --- 1. Definirea Modelului de Date (Contractul API) ---
class DeliveryRequest(BaseModel):
    client_name: str = Field(...,
                             description = "Numele clientului",
                             examples = ["Popescu Ion"])
    awb: str = Field(..., 
                     description="Numărul AWB al coletului.", 
                     examples=["AWB123456"])
    customer_phone: str = Field(..., 
                                description="Numărul de telefon al clientului (format național).", 
                                examples=["0722333444"])
    source_courier: str = Field(..., 
                                description="Numele curierului care trimite cererea.", 
                                examples=["FanCourier", "Sameday"])
    available_delivery_dates: List[date] = Field(...,
                                                  description="O listă cu datele în care curierul POATE livra.",
                                                  examples=[["2025-11-18", "2025-11-19"]])
    delivery_method: str = Field(...,
                                 description = "Delivery option chosed by client.",
                                 examples = ["locker", "home"])
    country: str = Field(...,
                         description = "Tara locuintei clientului.",
                         examples = ["Romania", "RO"])
    city: str = Field(...,
                      description="Orașul de reședință.",
                      examples=["București"])
    county: str = Field(...,
                      description="Județul sau sectorul.",
                      examples=["Sector 1"])
    street_name: str = Field(...,
                             description="Numele străzii.",
                             examples=["Calea Victoriei"])
    street_number: str = Field(...,
                               description="Numărul străzii.",
                               examples=["100"])
    postal_code: str = Field(...,
                                description="Codul poștal (opțional).",
                                examples=["010071"])
    details: str = Field(...,
                            description="Detalii suplimentare (bloc, scară, ap, interfon).",
                            examples=["Bloc D, Scara 2, Ap. 30, Interfon 30C"])


# --- 2. Inițializarea Aplicației FastAPI ---
app = FastAPI(
    title="Agent Dispecer API",
    description="Primește notificări de livrare de la curieri și le salvează în baza de date.",
    version="1.0.0"
)

# Configurare logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 3. Endpoint-ul NOU (Aici primești JSON-ul) ---
@app.post("/notify-delivery", 
          status_code=status.HTTP_202_ACCEPTED,
          summary="Primește o notificare de livrare de la un curier")
async def receive_delivery_notification(request: DeliveryRequest):
    """
    Acesta este endpoint-ul pe care îl apelează FanCourier.
    El primește JSON-ul și îl salvează în Firestore.
    """
    logger.info(f"Primit notificare pentru AWB: {request.awb} de la {request.source_courier}. Nume client: {request.client_name}.")

    if db is None:
        logger.error("Eroare critică: Conexiunea la DB nu este activă.")
        raise HTTPException(status_code=500, detail="Eroare internă: Conexiunea la baza de date a eșuat.")

    try:
        # 'request.model_dump(mode="json")' convertește JSON-ul primit 
        # (care e acum un obiect Pydantic) într-un dicționar
        # care poate fi salvat în Firebase (convertește 'date' în 'str').
        data_to_save = jsonable_encoder(request)
        
        # Adăugăm câmpuri extra pentru statusul intern
        data_to_save['status'] = 'received' # Statusul inițial
        data_to_save['received_at'] = firestore.SERVER_TIMESTAMP
        
        # Salvează în colecția 'pending_deliveries', folosind AWB-ul ca ID
        doc_ref = db.collection('pending_deliveries').document(request.awb)
        doc_ref.set(data_to_save)
        
        logger.info(f"AWB: {request.awb} a fost salvat în 'pending_deliveries'")
        
        return {
            "status": "success", 
            "message": f"Livrarea {request.awb} a fost primită și pusă în coadă."
        }
        
    except Exception as e:
        logger.error(f"Eroare la salvarea AWB {request.awb}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Nu s-a putut procesa cererea: {e}"
        )

# --- 4. Endpoint-urile de test existente ---
@app.get("/test-db", summary="Testează conexiunea la Firestore")
async def test_database_connection():
    if db is None:
        raise HTTPException(status_code=500, detail="Conexiunea la baza de date a eșuat.")
    try:
        doc_ref = db.collection('test_logs').document('api_ping')
        doc_ref.set({'timestamp': firestore.SERVER_TIMESTAMP})
        return {"status": "OK", "mesaj": "Conexiune DB reușită!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la scrierea în DB: {e}")

@app.get("/", summary="Verifică starea serverului")
def read_root():
    return {"status": "Agent Dispecer API is running"}