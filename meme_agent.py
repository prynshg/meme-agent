import os
import textwrap
import datetime
import random
import requests
import json
from PIL import Image, ImageDraw, ImageFont

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------------- SETTINGS ----------------

NUM_FINAL_POSTS = 5
NUM_GENERATE = 15

BG_COLOR = "#0f0f0f"
TEXT_COLOR = "#f5f5f5"

MAIN_TEXT_SIZE = 62
WATERMARK_SIZE = 18

WATERMARK_TEXT = "@soulsyncspacee"
SAVE_FOLDER = "generated_memes"
DRIVE_FOLDER_ID = "1ePDgY57S11uV7Q5rd2gO9gnTeFR2eCLU"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_TOKEN = os.getenv("GOOGLE_TOKEN")

SCOPES = ['https://www.googleapis.com/auth/drive.file']

os.makedirs(SAVE_FOLDER, exist_ok=True)

# ---------------- ROTATING THEMES ----------------

themes = [
    "Overthinking and sadness",
    "Indian middle class struggles",
    "Dating in India",
    "Corporate burnout",
    "Gym vs motivation",
    "Salary problems",
    "Gen Z existential crisis"
]

selected_theme = random.choice(themes)

# ---------------- GROQ CALL FUNCTION ----------------

def groq_call(messages, temperature=0.9):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-oss-120b",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000
        },
        timeout=60
    )

    if response.status_code != 200:
        print("Groq error:", response.text)
        exit()

    return response.json()["choices"][0]["message"]["content"]

# ---------------- STEP 1: GENERATE 15 MEMES ----------------

generation_prompt = f"""
Generate {NUM_GENERATE} Indian meme one-liners.

Theme: {selected_theme}

Tone:
- Observational
- Relatable
- Slightly tragic but funny
- Either natural hinglish or proper English, not a combination of both
- Slangs such has chod(fuck) , gaand(ass) are ok but limited .
- No grammar mistakes
- No politics or religion

Bad examples:
"Life is sad."
"Main toxic nahi hoon, bas overthinking ka premium version hoon."
"Salary aati hai sirf account check karne ke liye."
"Gym join kiya tha body ke liye, ab sirf guilt mil raha hai."

Good examples:
"Todays kids dont even get chicken pox anymore, they go straight to AIDS."
"Living in your parents house is free because you pay with your mental health."
"being a son is crazy because the moment you are born, you are competing with modiji for the love of your father"
"10 suraj milke bhi itni aag nahi lagate jitni aapke dp ne laga rakhi hai"
"Nahi rehna to mat reh par mental health mat chod meri"

Rules:
- 10–16 words
- Clear punchline
- One line only

Return ONLY JSON:
[
  {{ "meme": "text" }}
]
"""

messages_generate = [
    {
        "role": "system",
        "content": "You are a clever Indian meme writer with strong Hinglish control."
    },
    {
        "role": "user",
        "content": generation_prompt
    }
]

raw_output = groq_call(messages_generate, temperature=0.9)

# Clean JSON
raw_output = raw_output.strip()
start = raw_output.find("[")
end = raw_output.rfind("]")
json_text = raw_output[start:end+1]

try:
    generated_memes = json.loads(json_text)
except:
    print("Generation JSON failed:")
    print(raw_output)
    exit()

# ---------------- STEP 2: SCORE MEMES ----------------

score_prompt = f"""
Rate these memes from 1 to 10 based on:
- Relatability
- Humor
- Clever twist
- Either natual hinglish or Enligsh, not a combination of both

Return ONLY JSON:
[
  {{ "meme": "text", "score": number }}
]

Memes:
{json.dumps(generated_memes, indent=2)}
"""

messages_score = [
    {
        "role": "system",
        "content": "You are a strict meme critic."
    },
    {
        "role": "user",
        "content": score_prompt
    }
]

scored_output = groq_call(messages_score, temperature=0.5)

scored_output = scored_output.strip()
start = scored_output.find("[")
end = scored_output.rfind("]")
json_text = scored_output[start:end+1]

try:
    scored_memes = json.loads(json_text)
except:
    print("Scoring JSON failed:")
    print(scored_output)
    exit()

# Sort & pick best
scored_memes.sort(key=lambda x: x["score"], reverse=True)
final_memes = scored_memes[:NUM_FINAL_POSTS]

# ---------------- IMAGE CREATION ----------------

def create_meme(text, index):
    width, height = 1080, 1080
    image = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(image)

    # Cleaner non-bold font
    font = ImageFont.truetype("DejaVuSans.ttf", MAIN_TEXT_SIZE)
    watermark_font = ImageFont.truetype("DejaVuSans.ttf", WATERMARK_SIZE)

    wrapped_text = textwrap.fill(text, width=22)

    bbox = draw.textbbox((0, 0), wrapped_text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (width - text_width) / 2
    y = (height - text_height) / 2

    draw.text(
        (x, y),
        wrapped_text,
        font=font,
        fill=TEXT_COLOR
    )

    # Center bottom watermark
    watermark_bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=watermark_font)
    wm_width = watermark_bbox[2] - watermark_bbox[0]
    wm_height = watermark_bbox[3] - watermark_bbox[1]

    margin = 40
    wm_x = (width - wm_width) / 2
    wm_y = height - wm_height - margin

    draw.text(
        (wm_x, wm_y),
        WATERMARK_TEXT,
        font=watermark_font,
        fill="#888888"
    )

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

for i, meme in enumerate(final_memes, start=1):

    meme_text = meme["meme"]

    image_path = create_meme(meme_text, i)

    file_metadata = {
        'name': f"meme_{i}.png",
        'parents': [folder_id]
    }

    media = MediaFileUpload(image_path, mimetype='image/png')
    service.files().create(body=file_metadata, media_body=media).execute()

print("Memes generated and uploaded successfully.")
