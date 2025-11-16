from twilio.rest import Client
import os

# Account SID și Auth Token din consola Twilio
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')  # Înlocuiește cu Account SID
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')  # Înlocuiește cu Auth Token

client = Client(account_sid, auth_token)

def send_whatsapp_message(to_number, message_body):
    message = client.messages.create(
        from_='whatsapp:+14155238886',
        body=message_body,
        to=to_number
    )
    return message.sid
