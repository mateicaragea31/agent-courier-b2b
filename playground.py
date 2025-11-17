from flask import Flask, request
from langchain_core.messages import HumanMessage, SystemMessage
from twilio.twiml.messaging_response import MessagingResponse
import os
from tools import agent_with_memory, config_data, system_prompt2
from send_message import send_whatsapp_message
app = Flask(__name__)

system_input_content = '''{
  "client_name": "Popescu Maria",
  "awb": "AWB_FLAT_001",
  "customer_phone": "0722000000",
  "source_courier": "FanCourier",
  "available_delivery_dates": [
    "2025-11-21",
    "2025-11-22"
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
result = agent_with_memory.invoke(input_data2, config=config_data)
send_whatsapp_message('whatsapp:+40746348023', result['messages'][-1].content)

@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_reply():
    incoming_message = request.values.get('Body', '').lower()
    input_data = {
        "messages": [
            HumanMessage(content=incoming_message)
        ]
    }
    response = agent_with_memory.invoke(input_data, config=config_data)
    send_whatsapp_message('whatsapp:+40746348023', response['messages'][-1].content)
    return str(incoming_message)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True, use_reloader = False)
