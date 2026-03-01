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

NUM_POSTS = 5

BG_COLOR = "#080808"        # Background color
TEXT_COLOR = "#ebedeb"      # Main meme text color
STROKE_COLOR = "#ebedeb"    # Outline color

MAIN_TEXT_SIZE = 65
WATERMARK_SIZE = 20

WATERMARK_TEXT = "@soulsyncspacee"
SAVE_FOLDER = "generated_memes"
DRIVE_FOLDER_ID = "1ePDgY57S11uV7Q5rd2gO9gnTeFR2eCLU"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_TOKEN = os.getenv("GOOGLE_TOKEN")

SCOPES = ['https://www.googleapis.com/auth/drive.file']

os.makedirs(SAVE_FOLDER, exist_ok=True)

# ---------------- ROTATING THEMES ----------------

themes = [
    "Indian middle class struggles",
    "Overthinking and sadness",
    "Dating in India",
    "Gym motivation vs reality",
    "Corporate job life",
    "Salary problems",
    "Indian parents logic",
    "Gen Z existential crisis",
    "Being broke but acting rich",
    "Toxic relationships"
]

selected_theme = random.choice(themes)

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
                    "content": """
You are a viral Indian meme page admin.

You create savage, relatable, slightly dark Gen Z Indian humor.

Style:
- One-line punch
- Hinglish heavy
- Observational
- Slightly exaggerated
- Tag-worthy
- Not political
- Not religious
- No sensitive tragedy jokes
- No limits Dark humour

Make people say: "Bro this is too real."
"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 1.5,
            "max_tokens": 1200
        },
        timeout=60
    )

    if response.status_code != 200:
        print("Groq error:", response.text)
        exit()

    data = response.json()
    return data["choices"][0]["message"]["content"]

prompt = f"""
Generate exactly {NUM_POSTS} savage Indian one-line memes.

Theme: {selected_theme}

Example tone:

Pata nahi mujh jaise mastikhor mein itni sadness kaha se aa rahi hai.
Salary aati hai sirf account check karne ke liye.
Today's kids don't even get chicken pox anymore, they go straight to STD's.
Main toxic nahi hoon, bas overthinking ka premium version hoon.

Rules:
- One line only
- Max 18 words
- No explanation
- No image description
- Punchline format
- Be savage and sarcastic at the same time, It should be very funny and relatable. No Limits or restrictions to this.
- Natural Hinglish, no mistakes and words should be proper. This is important

Return ONLY JSON:

[
  {{
    "meme": "one savage line"
  }}
]

Generate exactly {NUM_POSTS} items.
Only JSON.
"""

output = generate_memes(prompt)

if not output:
    print("No output generated.")
    exit()

# ---------------- CLEAN & PARSE JSON ----------------

output = output.strip()

if output.startswith("```"):
    output = output.split("```")[1]

start = output.find("[")
end = output.rfind("]")

if start == -1 or end == -1:
    print("Could not find JSON array. Raw output below:\n")
    print(output)
    exit()

json_text = output[start:end+1]

try:
    posts = json.loads(json_text)
except Exception:
    print("JSON parsing failed. Raw output below:\n")
    print(output)
    exit()

posts = posts[:NUM_POSTS]

# ---------------- IMAGE CREATION ----------------

def create_meme(text, index):
    width, height = 1080, 1080
    image = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(image)

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
        fill=TEXT_COLOR,
        stroke_width=3,
        stroke_fill=STROKE_COLOR
    )

    # Watermark positioning (bottom right)
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
        fill="#ebedeb"
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

for i, post in enumerate(posts, start=1):

    meme_text = post.get("meme", "")

    image_path = create_meme(meme_text, i)

    file_metadata = {
        'name': f"meme_{i}.png",
        'parents': [folder_id]
    }

    media = MediaFileUpload(image_path, mimetype='image/png')
    service.files().create(body=file_metadata, media_body=media).execute()

print("Memes generated and uploaded successfully.")
