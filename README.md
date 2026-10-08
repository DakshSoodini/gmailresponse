# Gmail Auto-Responder (Local LLM)

An assistant that drafts replies to your unread Gmail with a language model running on your own computer. Nothing is sent until you approve, edit or reject each draft.

## How it works

1. **Read:** `gmail2.py` signs in to Gmail with Google OAuth and fetches unread emails from the Primary inbox tab. Promotions, Social, Updates, Forums and spam are skipped.
2. **Draft:** each email's preview text goes to **Falcon-7B-Instruct**, which runs locally through Hugging Face Transformers. It is prompted to write a short, polite reply as the recipient, or to say that no reply is needed.
3. **Review:** you see the email and the draft and choose `y` (send), `edit` (rewrite, then send) or `n` (skip).
4. **Send:** approved replies are sent in the original conversation thread, and the email is marked as read so it isn't suggested again.

### Safeguards
- **A person approves every email.** Nothing is sent automatically.
- **Unfilled placeholders block sending.** If a draft still contains text like `[Your Name]` or `[Recipient]`, you have to edit it before it can go out.
- **No-reply emails are skipped.** When the model decides an email doesn't need a reply, it's skipped without asking.
- **Email content stays on your machine.** It goes only to the local model, never to an outside AI service.

## Why a local model

I first tried OpenAI's API, but the cost added up for every email. Running a 7-billion-parameter open model locally is slower, but it's free and keeps email content private.

## Setup

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. In the [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Gmail API**. Then create an **OAuth client ID** of type *Desktop app* and download it as `credentials.json` into this folder.
3. Run:
   ```bash
   python gmail2.py
   ```
   The first run opens a browser to grant access and saves `token.json`.

**Keep `credentials.json` and `token.json` private.** They're listed in `.gitignore` so they can't be committed by accident.

Falcon-7B is a large model and runs best on a GPU with plenty of memory. With less, Transformers moves part of the model to the CPU, which works but is slow.

## Limitations

- **Drafts only see the preview.** The model reads Gmail's short preview of each email, not the full message, so replies to long emails can miss context.
- **Drafts need checking.** A 7B model sometimes misreads who is writing to whom. That's why every reply needs approval.

## What I learned

This was my first fully independent AI project. ChatGPT wrote the first version, and I improved it over a second iteration. I learned how OAuth works, the trade-off between paid APIs and running models locally, and why an automated system that acts for you needs a person in the loop.
