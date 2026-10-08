import os
import re
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
    # Primary tab only: skips Promotions, Social, Updates and Forums. Spam and
    # Trash are never in INBOX, so they're excluded already.
    results = service.users().messages().list(
    userId='me',
    labelIds=['INBOX'],
    q='is:unread category:primary'
).execute()

    messages = results.get('messages', [])
    emails = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = msg_data['payload']['headers']
        sender = next((h['value'] for h in headers if h['name'] == 'From'), None)
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)
        message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)
        snippet = msg_data.get('snippet', '')
        thread_id = msg_data.get('threadId')
        emails.append({
            'id': msg['id'],
            'threadId': thread_id,
            'sender': sender,
            'subject': subject,
            'messageId': message_id,
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


def needs_no_reply(reply):
    return reply.lower().startswith("no reply needed")


def find_placeholders(reply):
    """Template slots the model sometimes leaves in, e.g. [Your Name]."""
    return re.findall(r"\[[^\[\]\n]{1,40}\]", reply)


def send_email(service, to, subject, message_text, thread_id=None, in_reply_to=None):
    subject = subject or ""
    message = MIMEText(message_text)
    message['to'] = to
    message['subject'] = subject if subject.lower().startswith("re:") else "Re: " + subject
    # Gmail only files a reply into the original conversation when these
    # headers point at the message being answered
    if in_reply_to:
        message['In-Reply-To'] = in_reply_to
        message['References'] = in_reply_to
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    body = {'raw': raw}
    if thread_id:
        body['threadId'] = thread_id

    return service.users().messages().send(userId='me', body=body).execute()


def mark_read(service, msg_id):
    """So an answered email isn't suggested again on the next run."""
    service.users().messages().modify(
        userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()

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
        if needs_no_reply(reply):
            print("\n🤖 No reply needed. Skipped.\n")
            continue
        print(f"\n🤖 Suggested Reply:\n{reply}\n")

        placeholders = find_placeholders(reply)
        if placeholders:
            print(f"⚠️ The reply still has placeholders ({', '.join(placeholders)}). "
                  "Choose 'edit' to fill them in before sending.")

        action = input("Send this reply? (y/n/edit): ").strip().lower()
        if action == 'y' and placeholders:
            print("❌ Not sent: fill in the placeholders with 'edit' first.\n")
        elif action == 'y':
            send_email(service, email['sender'], email['subject'], reply,
                       thread_id=email.get('threadId'), in_reply_to=email.get('messageId'))
            mark_read(service, email['id'])
            print("✅ Sent.\n")
        elif action == 'edit':
            print("✍️ Enter your edited reply below (press Enter when done):")
            edited = input(f"{reply}\n→ ").strip()
            if not edited:
                print("❌ Empty reply. Skipped.\n")
                continue
            send_email(service, email['sender'], email['subject'], edited,
                       thread_id=email.get('threadId'), in_reply_to=email.get('messageId'))
            mark_read(service, email['id'])
            print("✅ Custom reply sent.\n")
        else:
            print("❌ Skipped.\n")

if __name__ == "__main__":
    main()
