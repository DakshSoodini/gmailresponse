import os
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from model_loader import load_local_model  # Make sure this exists

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def authenticate_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def fetch_unread_emails(service):
    results = service.users().messages().list(
    userId='me',
    labelIds=['INBOX'],
    q='is:unread -category:spam -in:trash'
).execute()

    messages = results.get('messages', [])
    emails = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_data['payload']['headers']
        sender = next((h['value'] for h in headers if h['name'] == 'From'), None)
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)
        snippet = msg_data.get('snippet', '')
        thread_id = msg_data.get('threadId')
        emails.append({
            'id': msg['id'],
            'threadId': thread_id,
            'sender': sender,
            'subject': subject,
            'snippet': snippet
        })
    return emails

def generate_reply(generator, email_text):
    prompt = f"""
### Instruction:
You are a professional email assistant helping someone **respond to emails they've received**. 
Do **not** act as the sender. Do **not** respond on behalf of companies like Spotify or NVIDIA.
You are the **recipient**, and you're writing a **short, clear, and polite response** if a response makes sense. 
If it's a newsletter or irrelevant marketing message, you may respond: "No reply needed."

### Email received:
{email_text}

### Reply:
"""
    result = generator(prompt, max_new_tokens=200, do_sample=True, temperature=0.7)[0]["generated_text"]
    return result.split("### Reply:")[-1].strip()


def send_email(service, to, subject, message_text, thread_id=None):
    message = MIMEText(message_text)
    message['to'] = to
    message['subject'] = "Re: " + subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    body = {'raw': raw}
    if thread_id:
        body['threadId'] = thread_id

    return service.users().messages().send(userId='me', body=body).execute()

def main():
    service = authenticate_gmail()
    generator = load_local_model()
    emails = fetch_unread_emails(service)
    if not emails:
        print("📭 No unread emails.")
        return

    for email in emails:
        print(f"\n📧 From: {email['sender']}\nSubject: {email['subject']}\n\nSnippet: {email['snippet']}")
        reply = generate_reply(generator, email['snippet'])
        print(f"\n🤖 Suggested Reply:\n{reply}\n")

        action = input("Send this reply? (y/n/edit): ").strip().lower()
        if action == 'y':
            send_email(service, email['sender'], email['subject'], reply, thread_id=email.get('threadId'))
            print("✅ Sent.\n")
        elif action == 'edit':
            print("✍️ Enter your edited reply below (press Enter when done):")
            edited = input(f"{reply}\n→ ").strip()
            send_email(service, email['sender'], email['subject'], edited, thread_id=email.get('threadId'))
            print("✅ Custom reply sent.\n")
        else:
            print("❌ Skipped.\n")

if __name__ == "__main__":
    main()
