#!/usr/bin/env python3
"""
YouTube Video Summarizer - Web Interface with Flask
יוטיוב סמולטור - ממשק אתר עם Flask
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import json
import threading
from pathlib import Path
import yt_dlp
import whisper
from anthropic import Anthropic
import traceback

app = Flask(__name__, template_folder='.', static_folder='.')
CORS(app)

# הגדרות
OUTPUT_DIR = Path("./summarized_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

# משתנים גלובליים לעדכון התקדמות
progress_data = {
    "status": "idle",
    "message": "",
    "progress": 0,
    "result": None,
    "error": None
}

def update_progress(status, message, progress=None):
    """עדכון התקדמות"""
    global progress_data
    progress_data["status"] = status
    progress_data["message"] = message
    if progress is not None:
        progress_data["progress"] = progress
    print(f"[{status}] {message}")

@app.route('/')
def index():
    """דף הבית"""
    return render_template('index.html')

@app.route('/api/progress')
def get_progress():
    """קבל עדכון התקדמות"""
    return jsonify(progress_data)

@app.route('/api/summarize', methods=['POST'])
def summarize():
    """סיכום סרטון YouTube"""
    global progress_data

    data = request.json
    video_url = data.get('url', '').strip()

    if not video_url:
        return jsonify({"error": "נא הזן URL תקין"}), 400

    # בדוק API Key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY לא הוגדר"}), 400

    # הרץ בthread נפרד כדי לא לחסום את הבקשה
    thread = threading.Thread(target=process_video, args=(video_url, api_key))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started"})

def process_video(video_url, api_key):
    """עיבוד הסרטון"""
    global progress_data

    try:
        progress_data["error"] = None
        progress_data["result"] = None

        # שלב 1: הורדה
        update_progress("downloading", "⏳ מוריד סרטון מ-YouTube...", 10)
        video_path = download_video(video_url)
        if not video_path:
            raise Exception("לא הצלחנו להוריד את הסרטון")

        # שלב 2: תמלול
        update_progress("transcribing", "🎵 מתמללת את הדיבור...", 30)
        transcript = transcribe_audio(video_path)

        # שלב 3: ניתוח עם Claude
        update_progress("analyzing", "🤖 מנתחת עם Claude AI...", 60)
        summary_data = analyze_with_claude(transcript, api_key)

        # סיום
        update_progress("completed", "✅ הושלם בהצלחה!", 100)
        progress_data["result"] = {
            "summary": summary_data.get("summary", ""),
            "title": summary_data.get("suggested_title", ""),
            "moments": summary_data.get("key_moments", [])
        }

    except Exception as e:
        update_progress("error", f"❌ שגיאה: {str(e)}", 0)
        progress_data["error"] = str(e)
        print(traceback.format_exc())

def download_video(url):
    """הורדת סרטון מ-YouTube"""
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': str(OUTPUT_DIR / '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
            return video_path

    except Exception as e:
        print(f"שגיאה בהורדה: {e}")
        return None

def transcribe_audio(video_path):
    """תמלול אודיו"""
    try:
        print("📥 טוען מודל Whisper...")
        model = whisper.load_model("base")

        print("🎵 מתמללת...")
        result = model.transcribe(video_path, language="he")

        return result["text"]

    except Exception as e:
        print(f"שגיאה בתמלול: {e}")
        raise

def analyze_with_claude(transcript, api_key):
    """ניתוח עם Claude"""
    try:
        client = Anthropic(api_key=api_key)

        prompt = f"""אתה עורך וידאו מקצועי שמתמחה בסיכום סרטונים.

התמלול של הסרטון:
{transcript[:3000]}

עשה את הדברים הבאים:

1. **סיכום קצר**: כתוב סיכום של 2-3 משפטים של הנושא הראשי

2. **רגעים חשובים**: זהה בדיוק 3-4 רגעים מפתח שצריך להשאר בסרטון המקוצר
   עבור כל רגע, תן:
   - הזמן המשוער בדקות (0-5)
   - תיאור קצר
   - מדוע זה חשוב

3. **שם למקוצר**: הצע שם טוב לסרטון מקוצר

תן תשובה בפורמט JSON בדיוק:

{{
  "summary": "...",
  "key_moments": [
    {{
      "start_time": 0.5,
      "end_time": 1.2,
      "description": "...",
      "importance": "..."
    }}
  ],
  "suggested_title": "..."
}}"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text

        # חלץ JSON
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            json_str = response_text[start:end]
            return json.loads(json_str)

        return {
            "summary": "סיכום בעברית",
            "key_moments": [],
            "suggested_title": "סרטון מקוצר"
        }

    except Exception as e:
        print(f"שגיאה בניתוח: {e}")
        raise

if __name__ == '__main__':
    print("🚀 YouTube Video Summarizer - Web Interface")
    print("=" * 50)
    print("🌐 פתח את: http://localhost:5000")
    print("=" * 50)

    # קרא PORT מהמשתנה הסביבה (עבור שרתים)
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'

    app.run(debug=debug, host='0.0.0.0', port=port)
