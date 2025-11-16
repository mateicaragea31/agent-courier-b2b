import json

from firebase_admin import firestore
from langchain.agents import create_agent
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableWithMessageHistory
from pydantic import BaseModel, Field
from langchain_core.tools import *
from typing import Literal
from extragere_informatii import get_zi_saptamanii
import langchain_openai
from langgraph.store.memory import InMemoryStore
import datetime
import filelock
from langsmith import uuid7


current_date = datetime.datetime.now().strftime("%Y-%m-%d")
day_of_week = get_zi_saptamanii(current_date)
system_prompt2 = f"""Ești un asistent virtual specializat în programarea livrărilor. Rolul tău principal este să afli de la client zilele în care acesta **NU** este disponibil (nu este acasă) pentru a primi un colet, din lista de date de livrare propuse. In momentul in care ai toate datele necesare (ai informatii de disponibilitate despre fiecare data), scopul tau e sa trimiti un raport final catre sistem cu zilele in care clientul NU este disponibil.

Ești politicos, profesionist și te concentrezi exclusiv pe obiectivul tău.

Astazi este {current_date}, {day_of_week}. Folosește această informație pentru a interpreta corect mesajele clientului legate de data.
Orindea zilelor săptămânii este: Luni, Marti, Miercuri, Joi, Vineri, Sâmbătă, Duminică.
Saptamana incepe luni și se termină duminică.
Toate datele pe care le folosesti trebuie sa fie în formatul YYYY-MM-DD.
Dupa duminica urmează luni.
### Context și Intrări

Vei primi două tipuri de mesaje:

1.  **Mesaj de la Sistem (JSON):** Acesta este semnalul de start. Conține toate detaliile necesare despre o livrare (client, AWB, și, cel mai important, `available_delivery_dates`). 
2.  **Mesaj de la Client (Text):** Acesta este răspunsul clientului la întrebările tale sau o solicitare din partea lui.

### Instrumente (Tools) Disponibile

Ai acces la următoarele instrumente. Folosește-le **doar** atunci când este necesar și cu argumentele corecte, conform descrierii.

1.  **`verify_disponibility`**:
    * **Scop:** Verifică starea curentă în sistem pentru o listă de date.
    * **Când se folosește:** Trebuie să folosești acest tool **o singură dată**, imediat după ce primești JSON-ul de sistem, pentru a afla starea inițială a datelor din `available_delivery_dates` înainte de a contacta clientul.
    * **Nu cere niciodata confirmarea datelor primi de la acest tool.

2.  **`change_disponibility`**:
    * **Scop:** Schimbă starea de disponibilitate pentru o dată specifică.
    * **Când se folosește:** Când clientul îți spune clar o dată anume (ex: "Nu sunt acasă pe 18") din lista propusă. Setează `available=False` dacă clientul spune că **NU** este acasă.
    * **Exemplu:** Clientul spune: "Marți pe 18 nu pot." -> Apelezi `change_disponibility(date="2025-11-18", available=False)`.
    * **Notă:** Dacă clientul menționează un interval (ex: "Nu sunt acasă în următoarele 3 zile" sau "nu sunt acasa toata saptamana"), trebuie să transformi acest interval într-o listă de date specifice și să apelezi `change_disponibility` pentru fiecare dată din acea listă.
    * **Nota:** Clientul poate mentiona si ca este disponibil. In acest caz, seteaza available=True si apeleaza tool-ul.

3.  **`change_disponibility_recurrent`**:
    * **Scop:** Setează o regulă de indisponibilitate recurentă.
    * **Când se folosește:** Când clientul menționează o *regulă* (ex: "în fiecare luni", "joia nu sunt niciodată", "lunea sunt mereu plecat").
    * **Daca clientul specifică o recurență, trebuie să calculezi care este cea mai apropiată dată în care este ziua specificată și să o setezi ca data de start.**
    * **Daca clientul specifica o recurență zilnică, săptămânală, lunară sau anuală, folosește tipul de recurență corespunzător.**
    * **Daca clientul specifica un interval de recurență (ex: "în fiecare 2 săptămâni"), setează intervalul corespunzător.**
    * **Daca clientul specifica un interval de date pentru recurenta (ex: 'in fiecare luna in primele 3 zile'), apeleaza acest tool pentru fiecare zi din interval, unde start_time este ziua**
    * **Daca clientul nu specifică o dată de sfârșit, setează recurența ca fiind nelimitată, adica end_date = None**
   
4.  **`send_response_to_system`**:
    * **Scop:** Trimite o lista cu zilele in care clientul nu este disponibil
    * Cand ai toate informatiile despre datele primite de la sistem, foloseste acest tool pentru a trimite o lista cu zilele in care clientul nu este disponibil
    * **Exemplu:** `send_response_to_system(['2025-11-19', '2025-11-21'])`

5. **`verify_hold_availability`**:
    * **Scop:** Verifica daca data pe care a dat-o clientul este in limita zilelor in care poate tine coletul in depozit.
    * **Când se folosește:** Când clientul dorește sa reprogrameze coletul.
    * **Argumente:**data curenta de livrare, noua data propusa de client, numarul maxim de zile in care poate tine coletul in depozit (din json-ul de la sistem, cheia days_of_hold).
    * Foloseste acest tool dupa ce clientul iti specifica o data pentru livrare. Daca returneaza True, reprogrameaza mereu livrarea folosind exclusiv tool-ul `send_new_schedule`. Daca returneaza False, intreaba clientul pentru o alta data.
    
6. **`send_new_schedule`**:
    * **Scop:** Trimite noua data de livrare către sistem.
    * **Argumente:** awb-ul din detaliile initiale si noua data propusa de client.
    * **Când se folosește:** Când clientul dorește să reprogrameze livrarea și ai verificat că noua dată este validă folosind `verify_hold_availability`.
    


## Scopul tau:
Atunci cand primesti un mesaj de la sistem, foloseste `verify_disponibility` pentru a verifica disponibilitatea pe datele primite. Daca nu toate datele sunt acoperite(au True sau False), intreba clientul despre disponibilitatea pe acele date necunoscute. Intreaba clientul despre o data doar daca aceasta este None.
Dupa ce toate datele primite de sistem au fost acoperite: Daca exista macar o data la care clientul este disponibil, foloseste `send_response_to_system` pentru a trimite raspunsul catre sistem. Daca toate datele sunt indisponibile, propune-i clientului reprogramarea livrarii, mentionandu-i mereu si numarul maxim de zile in care poate tine coletul in depozit (din json-ul de la sistem, cheia days_of_hold).
Cand ai toate datele necesare, nu mai intreba niciodata clientul pentru o confirmare.

Atunci cand clientul iti spune informatii legate de disponibilitate, foloseste **exclusiv** `change_disponibility` sau `change_disponibility_recurrent` pentru a actualiza starea de disponibilitate in sistem pentru TOATE datele mentionate de client.
### Reguli Stricte

* **Focusează-te pe INDISPONIBILITATE:** Obiectivul tău principal este să afli când clientul **NU** poate primi coletul.
* **Nu repeta întrebări:** Nu întreba clientul informații pe care le-ai primit deja în JSON (nume, AWB, adresă).
* **Încheie corect:** Nu folosi `send_response_to_system` până când conversația cu clientul nu este complet terminată și confirmată.
* **De fiecare data cand te gandesti la o zi, foloseste data curenta  ({current_date}, {day_of_week} pentru a calcula la ce data se refera clientul.**
* **Verifica mereu cand primesti json-ul de la sistem daca toate datele au fost acoperite, ruland 'verify_disponibility'. Daca nu, intreaba clientul pentru informatii suplimentare.**
* **De fiecare data cand primesti informatii legate de o zi, un interval de zile, o recurenta sau o recurenta de interval de zile, gandeste-te ce inseamna si calculeaza datele exacte pe care trebuie sa le modifici in sistem.**

"""

#    * **Scop:** Trimite un raport final înapoi la sistem.
class DisponibilityInput(BaseModel):
    date: str = Field(
        description="Data pentru care se dorește schimbarea stării de disponibilitate în format YYYY-MM-DD.")
    new_status: bool = Field(
        description="Noua stare de disponibilitate: True pentru disponibil, False pentru indisponibil.")


class DisponibilityRecurrentInput(BaseModel):
    reccurence_type: Literal["zilnic", "saptamanal", "lunar", "anual"] = Field(description="Tipul de recurență")
    reccurence_interval: int = Field(
        description="Intervalul de recurență: de exemplu, in fiecare saptamana, la fiecare 2 săptămâni.")
    new_status: bool = Field(
        description="Noua stare de disponibilitate pentru recurență: True pentru disponibil, False pentru indisponibil.")
    start_date: str = Field(description="Data de început a recurenței în format YYYY-MM-DD.")
    end_date: str = Field(
        description="Data de sfârșit a recurenței în format YYYY-MM-DD. Dacă nu este specificată, recurența este nelimitată.")


class DisponibilityToVerifyInput(BaseModel):
    date_list: list[str] = Field(
        description="O listă de date pentru care se dorește verificarea stării de disponibilitate în format YYYY-MM-DD.")


class SystemResponseInput(BaseModel):
    date_list: list = Field("Lista cu datele in care clientul nu este disponibil.")


class RescheduleInput(BaseModel):
    """ Input pentru query-uri de delivery"""
    awb: str = Field(description="awb-ul primit de la sistem")
    new_date: str = Field(description="Noua dată de livrare propusă în format YYYY-MM-DD.")

class DepositHoldInput(BaseModel):
    first_date: str = Field(description="Prima dată de livrare programată în format YYYY-MM-DD.")
    new_date: str = Field(description="Noua dată de livrare propusă în format YYYY-MM-DD.")
    days_of_hold: int = Field(description="Numărul de zile pentru care clientul poate ține coletul în depozit.")

@tool(args_schema=RescheduleInput)
def send_new_schedule(awb: str, new_date: str):
    """
    Primeste noua data de livrare, updateaza noua data de livrare, marcheaza tot procesul in memorie si notifica curierul despre noua data
    """
    # Actulizez request-ul din coada
    detalii = {
        'awb': awb,
        'new_delivery_date': new_date
    }
    print ('Am trimis inapoi catre sistem noul request de livrare:', detalii)

@tool(args_schema= DepositHoldInput)
def verify_hold_availability(first_date: str, new_date: str, days_of_hold: int):
    """Verifica daca noua data propusa de client este in limita zilelor in care poate tine coletul in depozit."""
    first_date_object = datetime.strptime(first_date, "%Y-%m-%d")
    new_date_object = datetime.strptime(new_date, "%Y-%m-%d")
    delta_days = (new_date_object - first_date_object).days
    if delta_days <= days_of_hold:
        return True
    else:
        return False


@tool(args_schema=DisponibilityInput)
def change_disponibility(date, new_status):
    """Modifica starea de disponibilitate pentru o anumită dată"""
    FILE_PATH = "memorie_client.json"
    LOCK_PATH = "memorie_client.json.lock"
    lock = filelock.FileLock(LOCK_PATH)
    with lock:
        print(f"--- LOCK OBȚINUT: Procesez {date} ---")
        print("\n" + "=" * 30)
        print(f"--- TOOL APELAT: change_disponibility ---")
        print(f"--- ARGUMENTE PRIMITE: date = {date}")
        print(f"--- TIPUL ARGUMENTULUI: type(date) = {type(date)}")
        print("=" * 30 + "\n")
        with open('memorie_client.json', 'r') as f:
            data_client = json.load(f)
        data_client['exceptii_specifice'].update({date: new_status})
        print(data_client)
        with open('memorie_client.json', 'w') as f:
            json.dump(data_client, f, indent=4)
        print(f"--- LOCK ELIBERAT: Am terminat cu {date} ---")

    return f"Disponibilitatea pentru {date} a fost schimbată."


@tool(args_schema=SystemResponseInput)
def send_response_to_system(date_list: dict):
    """Trimite inapoi lista cu datele care nu sunt disponibile"""
    print("\n" + "=" * 30)
    print(f"--- TOOL APELAT: send_response_to_system ---")
    print(f"--- ARGUMENTE PRIMITE: date_list={date_list}")
    print(f"--- TIPURI: {type(date_list)}")
    print("=" * 30 + "\n")
    response_message = {
        'date_list': date_list
    }
    print(f'Răspuns trimis către sistem: {response_message}')
    return f'Răspuns trimis către sistem: {response_message}'


@tool(args_schema=DisponibilityRecurrentInput)
def change_disponibility_recurrent(reccurence_type, reccurence_interval, new_status, start_date, end_date=None):
    """Modifica starea de disponibilitate pentru o recurență specificată."""
    print("\n" + "=" * 30)
    print(f"--- TOOL APELAT: change_disponibility_recurrent ---")
    print("=" * 30 + "\n")
    FILE_PATH = "memorie_client.json"
    LOCK_PATH = "memorie_client.json.lock"
    lock = filelock.FileLock(LOCK_PATH)
    with lock:
        with open('memorie_client.json', 'r') as f:
            data_client = json.load(f)
        from datetime import datetime, timedelta
        data_client['recurrences'].append({
            'recurrence_type': reccurence_type,
            'recurrence_interval': reccurence_interval,
            'new_status': new_status,
            'start_date': start_date,
            'end_date': end_date if end_date else None
        })

        with open('memorie_client.json', 'w') as f:
            json.dump(data_client, f, indent=4)
        return f'Starea de disponibilitate a fost actualizată pentru perioada specificată.'


from datetime import datetime


def check_recurrence(rule, check_date_str):
    """
    Verifică dacă o dată (check_date_str) face parte dintr-o regulă de recurență.

    :param rule: Un dicționar (din JSON) ce conține:
                 - 'rule_type': 'daily', 'weekly', 'monthly', 'annually'
                 - 'interval': un număr întreg (ex: 1, 2, 3)
                 - 'start_date': data de început (string în format 'YYYY-MM-DD')
    :param check_date_str: Data pe care o verificăm (string în format 'YYYY-MM-DD')
    :return: True dacă data face parte din recurență, altfel False
    """

    # --- 1. Pregătirea datelor ---
    try:
        rule_type = rule['recurrence_type']
        interval = int(rule['recurrence_interval'])

        # Convertim string-urile în obiecte 'date' pentru a le putea compara
        start_date = datetime.strptime(rule['start_date'], '%Y-%m-%d').date()
        if rule['end_date']:
            end_date = datetime.strptime(rule['end_date'], '%Y-%m-%d').date()
        else:
            end_date = None
        check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()


    except (KeyError, ValueError) as e:
        # Gestionează erori dacă datele de intrare sunt invalide
        print(f"Eroare la parsarea datelor de intrare: {e}")
        return False

    # --- 2. Verificare de bază ---
    # Data de verificat nu poate fi înaintea datei de start
    if check_date < start_date:
        return False

    if end_date:
        if check_date > end_date:
            return False

    # --- 3. Logica de verificare pe tip de regulă ---

    if rule_type == 'zilnic':
        # Calculează diferența în zile
        delta_days = (check_date - start_date).days

        # Verifică dacă diferența de zile este un multiplu al intervalului
        # (Nota: 0 % interval == 0, deci start_date va returna True)
        return delta_days % interval == 0

    elif rule_type == 'saptamanal':
        # Pentru recurența săptămânală, trebuie să fie aceeași zi a săptămânii
        if check_date.weekday() != start_date.weekday():
            return False

        # Calculează diferența în săptămâni (bazându-ne pe zile)
        delta_days = (check_date - start_date).days
        delta_weeks = delta_days // 7  # Diviziune întreagă

        # Verifică dacă diferența de săptămâni este un multiplu al intervalului
        return delta_weeks % interval == 0

    elif rule_type == 'lunar':
        # Pentru recurența lunară, trebuie să fie aceeași zi a lunii
        if check_date.day != start_date.day:
            return False

        # Calculează diferența totală în luni
        delta_years = check_date.year - start_date.year
        delta_months = (delta_years * 12) + (check_date.month - start_date.month)

        # Verifică dacă diferența de luni este un multiplu al intervalului
        return delta_months % interval == 0

    elif rule_type == 'anual':
        # Pentru recurența anuală, trebuie să fie aceeași zi și aceeași lună
        if check_date.month != start_date.month or check_date.day != start_date.day:
            return False

        # Calculează diferența în ani
        delta_years = check_date.year - start_date.year

        # Verifică dacă diferența de ani este un multiplu al intervalului
        return delta_years % interval == 0

    # Dacă tipul regulii nu este recunoscut
    return False


@tool(args_schema=DisponibilityToVerifyInput)
def verify_disponibility(date_list):
    """Verifică starea de disponibilitate pentru o anumită dată."""
    with open('memorie_client.json', 'r') as f:
        data_client = json.load(f)
    date_disponibility_dict = {}
    for date in date_list:
        if date in data_client['exceptii_specifice']:
            date_disponibility_dict[date] = data_client['exceptii_specifice'][date]
        else:
            for rule in data_client['recurrences']:
                if check_recurrence(rule, date):
                    date_disponibility_dict[date] = rule['new_status']
                    break
        if date not in date_disponibility_dict:
            date_disponibility_dict[date] = None
    return date_disponibility_dict


# print(verify_disponibility(['2025-11-17', '2025-11-18', '2025-11-19']))

agent = create_agent(
    model=langchain_openai.ChatOpenAI(model="gpt-4o", temperature=0),
    tools=[change_disponibility, change_disponibility_recurrent, verify_disponibility, send_response_to_system, send_new_schedule, verify_hold_availability],
    store=InMemoryStore()
)

input_data = {
    "messages": [
        SystemMessage(content=system_prompt2),
        HumanMessage(content="Nu sunt acasa luni in fiecare saptamana")
    ]
}

system_input_content = '''{
  "client_name": "Popescu Maria",
  "awb": "AWB_FLAT_001",
  "customer_phone": "0722000000",
  "source_courier": "FanCourier",
  "available_delivery_dates": [
    "2025-11-21",
  ],
  "delivery_method": "home",
  "country": "Romania",
  "city": "București",
  "county": "Sector 3",
  "street_name": "Bulevardul Unirii",
  "street_number": "15",
  "postal_code": "030000",
  "details": "Bloc 2, Scara A, Ap 10",
  "days_of_hold": 5
}'''

input_data2 = {
    "messages": [
        SystemMessage(content=system_prompt2),
        SystemMessage(content=system_input_content),
    ]
}

config_data = {
    "configurable": {
        "session_id": uuid7()
    }
}

store = {}


def get_history(session_id: str):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]


agent_with_memory = RunnableWithMessageHistory(
    agent,
    get_history,
    input_messages_key="messages",
)