import os
import textwrap
import datetime
import requests
import xml.etree.ElementTree as ET
import json
from PIL import Image, ImageDraw, ImageFont

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

# ---------------- GET TRENDS (GOOGLE NEWS RSS) ----------------

def get_trends_from_news():
    try:
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)

        titles = []
        for item in root.findall(".//item")[:10]:
            title = item.find("title").text
            titles.append(title)

        return ", ".join(titles)

    except Exception:
        print("News RSS failed, using fallback trends.")
        return "Indian job market, AI tools, dating culture, cricket, Bollywood, exams, startups"

trend_text = get_trends_from_news()

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
Generate exactly {NUM_POSTS} Indian meme posts.

Inspired by these news headlines:
{trend_text}

Return ONLY valid JSON.

Format:

[
  {{
    "meme": "text",
    "caption": "text",
    "hashtags": "text"
  }}
]

Return exactly {NUM_POSTS} objects inside the array.

No markdown.
No explanation.
Only JSON.
"""

output = generate_memes(prompt)

if not output:
    print("No output generated.")
    exit()

# ---------------- CLEAN & PARSE JSON ----------------

output = output.strip()

# Remove markdown wrapping if present
if output.startswith("```"):
    output = output.split("```")[1]

# Extract JSON array safely
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

if not isinstance(posts, list) or len(posts) < 1:
    print("Invalid JSON structure.")
    print(output)
    exit()

posts = posts[:NUM_POSTS]

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

    for i, post in enumerate(posts, start=1):

        meme_text = post.get("meme", "")
        caption = post.get("caption", "")
        hashtags = post.get("hashtags", "")

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
