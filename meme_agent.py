import os
import textwrap
import datetime
import requests
from PIL import Image, ImageDraw, ImageFont
from pytrends.request import TrendReq

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------------- SETTINGS ----------------

NUM_POSTS = 5
BG_COLOR = "#FFD400"
WATERMARK_TEXT = "@yourpage"
SAVE_FOLDER = "generated_memes"
DRIVE_FOLDER_ID = "1ePDgY57S11uV7Q5rd2gO9gnTeFR2eCLU"

HF_TOKEN = os.getenv("HF_TOKEN")
SCOPES = ['https://www.googleapis.com/auth/drive.file']

os.makedirs(SAVE_FOLDER, exist_ok=True)

# ---------------- GET TRENDS ----------------

try:
    pytrends = TrendReq(hl='en-IN', tz=330)
    trending = pytrends.trending_searches(pn='india')[0:10].tolist()
    trend_text = ", ".join(trending)
except:
    trend_text = "Indian job market, AI, dating culture, gym"

# ---------------- GENERATE MEMES ----------------

prompt = f"""
Generate exactly 5 Indian meme posts.
Slightly edgy but safe.
English + Hinglish mix.

Inspired by:
{trend_text}

Format strictly:

MEME: ...
CAPTION: ...
HASHTAGS: ...
"""

API_URL = "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-Instruct-v0.2"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

response = requests.post(
    API_URL,
    headers={
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    },
    json={
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 400,
            "temperature": 0.8,
            "return_full_text": False
        }
    }
)

data = response.json()

if isinstance(data, list):
    output = data[0].get("generated_text", "")
elif isinstance(data, dict) and "error" in data:
    print("HuggingFace Error:", data["error"])
    output = ""
else:
    print("Unexpected HF response:", data)
    output = ""

blocks = output.split("MEME:")
posts = []

for block in blocks[1:6]:
    meme_text = ""
    caption = ""
    hashtags = ""

    lines = block.strip().split("\n")

    for line in lines:
        if line.startswith("CAPTION:"):
            caption = line.replace("CAPTION:", "").strip()
        elif line.startswith("HASHTAGS:"):
            hashtags = line.replace("HASHTAGS:", "").strip()
        elif not meme_text:
            meme_text = line.strip()

    if meme_text:
        posts.append((meme_text, caption, hashtags))

# ---------------- IMAGE ----------------

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

# ---------------- DRIVE ----------------

def get_drive_service():
    creds = Credentials.from_authorized_user_info(eval(os.getenv("GOOGLE_TOKEN")), SCOPES)
    return build('drive', 'v3', credentials=creds)

service = get_drive_service()

folder_metadata = {
    'name': str(datetime.date.today()),
    'mimeType': 'application/vnd.google-apps.folder',
    'parents': [DRIVE_FOLDER_ID]
}

folder = service.files().create(body=folder_metadata, fields='id').execute()
folder_id = folder.get('id')

for i, (meme_text, caption, hashtags) in enumerate(posts, start=1):
    image_path = create_meme(meme_text, i)

    file_metadata = {
        'name': f"meme_{i}.png",
        'parents': [folder_id]
    }

    media = MediaFileUpload(image_path, mimetype='image/png')
    service.files().create(body=file_metadata, media_body=media).execute()
