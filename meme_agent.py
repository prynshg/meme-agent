import os
import textwrap
import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
from pytrends.request import TrendReq

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------------- SETTINGS ----------------

NUM_POSTS = 5
BG_COLOR = "#FFD400"
WATERMARK_TEXT = "@yourpage"
SAVE_FOLDER = "generated_memes"
DRIVE_FOLDER_ID = "1ePDgY57S11uV7Q5rd2gO9gnTeFR2eCLU"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_TOKEN = os.getenv("GOOGLE_TOKEN")

SCOPES = ['https://www.googleapis.com/auth/drive.file']

os.makedirs(SAVE_FOLDER, exist_ok=True)

# ---------------- GET TRENDS ----------------

try:
    pytrends = TrendReq(hl='en-IN', tz=330)
    trending = pytrends.trending_searches(pn='india')[0:10].tolist()
    trend_text = ", ".join(trending)
except Exception:
    print("Trend fetch failed, using fallback.")
    trend_text = "Indian job market, AI, dating culture, gym, exams"

# ---------------- GENERATE MEMES (GROQ) ----------------

def generate_memes(prompt):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an Indian meme strategist. Slightly edgy but safe. English + Hinglish mix."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.8,
            "max_tokens": 900
        },
        timeout=60
    )

    if response.status_code != 200:
        print("Groq error:", response.text)
        exit()

    data = response.json()
    return data["choices"][0]["message"]["content"]

prompt = f"""
Generate exactly {NUM_POSTS} Indian meme posts.

Inspired by these trends:
{trend_text}

Format STRICTLY:

MEME: <1-2 lines>
CAPTION: <2 short punchy lines>
HASHTAGS: <8-12 hashtags>

Repeat exactly {NUM_POSTS} times.
Do not explain anything.
"""

output = generate_memes(prompt)

if not output:
    print("No output generated.")
    exit()

# ---------------- ROBUST PARSING ----------------

posts = []

sections = output.split("MEME:")

for section in sections[1:NUM_POSTS+1]:
    meme_text = ""
    caption = ""
    hashtags = ""

    lines = [l.strip() for l in section.strip().split("\n") if l.strip()]

    for line in lines:

        if line.upper().startswith("CAPTION"):
            caption = line.split(":", 1)[-1].strip()

        elif line.upper().startswith("HASHTAG"):
            hashtags = line.split(":", 1)[-1].strip()

        elif not meme_text:
            meme_text = line

    if meme_text:
        posts.append((meme_text, caption, hashtags))

if len(posts) < 1:
    print("Parser failed. Raw output below:\n")
    print(output)
    exit()

# ---------------- IMAGE CREATION ----------------

def create_meme(text, index):
    width, height = 1080, 1080
    image = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(image)

    font = ImageFont.load_default()

    wrapped_text = textwrap.fill(text, width=25)
    bbox = draw.textbbox((0, 0), wrapped_text, font=font)

    x = (width - (bbox[2] - bbox[0])) / 2
    y = (height - (bbox[3] - bbox[1])) / 2

    draw.text((x, y), wrapped_text, fill="black", font=font)
    draw.text((width - 200, height - 50), WATERMARK_TEXT, fill="black", font=font)

    filename = f"{SAVE_FOLDER}/meme_{index}.png"
    image.save(filename)
    return filename

# ---------------- GOOGLE DRIVE ----------------

def get_drive_service():
    creds = Credentials.from_authorized_user_info(eval(GOOGLE_TOKEN), SCOPES)
    return build('drive', 'v3', credentials=creds)

service = get_drive_service()

today = str(datetime.date.today())

folder_metadata = {
    'name': today,
    'mimeType': 'application/vnd.google-apps.folder',
    'parents': [DRIVE_FOLDER_ID]
}

folder = service.files().create(body=folder_metadata, fields='id').execute()
folder_id = folder.get('id')

caption_path = f"{SAVE_FOLDER}/captions_{today}.txt"

with open(caption_path, "w", encoding="utf-8") as caption_file:

    for i, (meme_text, caption, hashtags) in enumerate(posts, start=1):

        image_path = create_meme(meme_text, i)

        file_metadata = {
            'name': f"meme_{i}.png",
            'parents': [folder_id]
        }

        media = MediaFileUpload(image_path, mimetype='image/png')
        service.files().create(body=file_metadata, media_body=media).execute()

        caption_file.write(f"POST {i}\n")
        caption_file.write(meme_text + "\n\n")
        caption_file.write(caption + "\n")
        caption_file.write(hashtags + "\n\n")

print("Memes generated and uploaded successfully.")
