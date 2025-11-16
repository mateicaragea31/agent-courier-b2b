import json

from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain_core.tools import *
from typing import Literal
from extragere_informatii import get_zi_saptamanii
import langchain
import langchain_openai
from langgraph.store.memory import InMemoryStore
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import datetime

system_prompt = """
Ești un asistent de suport clienți pentru un magazin online. 
Răspunde întotdeauna politicos și la obiect.
Data de astazi este: {current_date}, {day_of_week}.

Ai acces la două tool-uri:
1. `change_disponibility`
2. `change_disponibility_recurrent`

**REGULI STRICTE PENTRU FOLOSIREA TOOL-URILOR:**


1.  **Analizează intenția:** Mai întâi, stabilește dacă utilizatorul vrea să stabilească disponibilitatea pentru o data anume sau pentru o recurenta.

2.  **Alegerea Tool-ului:**
    * Daca utilizatorul specifică o dată anume (ex: "Vreau să fiu disponibil pe 2024-12-25"), folosește **exclusiv** `change_disponibility`.
    * Dacă utilizatorul specifică o un interval de date (ex: "Nu sunt acasa in urmatoarele 3 zile"), transforma acest interval intr-o lista de date si aplica **exclusiv** `change_disponibility' pentru fiecare element din lista.
    * Dacă utilizatorul specifică o recurență (ex: "Vreau să fiu disponibil în fiecare luni și miercuri"), folosește **exclusiv** `change_disponibility_recurrent`.
    
3.  **Informatii lipsa**: Dacă utilizatorul nu oferă toate informațiile necesare pentru a folosi un tool, cere clarificări suplimentare înainte de a continua.

4.  **Gândire:** Gândește-te întotdeauna pas cu pas ce tool să folosești și de ce.
"""

current_date = datetime.datetime.now().strftime("%Y-%m-%d")
day_of_week = get_zi_saptamanii(current_date)
system_prompt = system_prompt.format(current_date=current_date, day_of_week=day_of_week)

# Agentul are nevoie și de 'input' și 'agent_scratchpad'
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


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


@tool(args_schema=DisponibilityInput)
def change_disponibility(date, new_status):
    """Modifica starea de disponibilitate pentru o anumită dată"""
    with open('memorie_client.json', 'r') as f:
        data_client = json.load(f)
    data_client['exceptii_specifice'][date] = new_status
    with open('memorie_client.json', 'w') as f:
        json.dump(data_client, f, indent=4)
    return f'Starea de disponibilitate pentru data de {date} a fost actualizată la {new_status}.'


@tool(args_schema=DisponibilityRecurrentInput)
def change_disponibility_recurrent(reccurence_type, reccurence_interval, new_status, start_date, end_date=None):
    """Modifica starea de disponibilitate pentru o recurență specificată."""
    with open('memorie_client.json', 'r') as f:
        data_client = json.load(f)
    from datetime import datetime, timedelta
    data_client['recurrences'].update({
        'recurrence_type': reccurence_type,
        'recurrence_interval': reccurence_interval,
        'new_status': new_status,
        'start_date': start_date,
        'end_date': end_date if end_date else None
    })

    with open('memorie_client.json', 'w') as f:
        json.dump(data_client, f, indent=4)
    return f'Starea de disponibilitate a fost actualizată pentru perioada specificată.'


agent = create_agent(
    model=langchain_openai.ChatOpenAI(model="gpt-4o", temperature=0),
    tools=[change_disponibility, change_disponibility_recurrent],
    store=InMemoryStore()
)

input_data = {
    "messages": [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Vreau să fiu indisponibil in urmatoarele 3 zile.")
    ]
}

config_data = {
    "configurable": {
        "thread_id": "id-conversatie-123"
    }
}

# 3. Acum apelează invoke cu input-ul și config-ul
result = agent.invoke(input_data, config=config_data)

print(result['messages'][-1])