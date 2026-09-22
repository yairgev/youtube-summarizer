from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import yt_dlp
import whisper
from anthropic import Anthropic
import os
import threading
import json

app = Flask(__name__)
CORS(app)

# Global progress tracking
progress_data = {
    'status': 'idle',
    'message': '',
    'progress': 0,
    'result': None,
    'error': None
}

# Lazy-load Whisper model
whisper_model = None

def get_whisper_model():
    """Load Whisper model lazily"""
    global whisper_model
    if whisper_model is None:
        try:
            whisper_model = whisper.load_model("base")
        except Exception as e:
            raise Exception(f"שגיאה בטעינת Whisper: {str(e)}")
    return whisper_model

def download_video(url):
    """Download video from YouTube with enhanced options"""
    try:
        progress_data['message'] = 'מוריד סרטון...'
        progress_data['progress'] = 10

        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': 'summarized_videos/%(id)s.%(ext)s',
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'tv'],
                    'skip': ['hls', 'dash'],
                }
            },
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_file = ydl.prepare_filename(info)
            progress_data['progress'] = 40
            return video_file
    except Exception as e:
        raise Exception(f"שגיאה בהורדה: {str(e)}")

def transcribe_audio(video_file):
    """Transcribe audio from video using Whisper"""
    try:
        progress_data['message'] = 'טוען מודל Whisper...'
        progress_data['progress'] = 45

        model = get_whisper_model()

        progress_data['message'] = 'תומלל אודיו...'
        progress_data['progress'] = 50
        result = model.transcribe(video_file, language="he")

        progress_data['progress'] = 70
        return result['text']
    except Exception as e:
        raise Exception(f"שגיאה בתמלול: {str(e)}")

def analyze_with_claude(transcript):
    """Analyze transcript with Claude AI"""
    try:
        progress_data['message'] = 'מנתח תוכן...'
        progress_data['progress'] = 80

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise Exception("API key not found. Please add ANTHROPIC_API_KEY to environment variables.")

        client = Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"""נתח את התמלול הזה של סרטון YouTube והחזר:
1. סיכום קצר (2-3 משפטים)
2. נושאים עיקריים (רשימה)
3. רגעים חשובים (עד 5)

התמלול:
{transcript}

תשובה בפורמט JSON עם שדות: summary, key_points, key_moments, suggested_title"""
                }
            ]
        )

        response_text = message.content[0].text

        # Try to parse as JSON
        try:
            result = json.loads(response_text)
        except:
            # If not JSON, structure it
            result = {
                "summary": response_text,
                "key_points": [],
                "key_moments": [],
                "suggested_title": "סיכום הסרטון"
            }

        progress_data['progress'] = 95
        return result
    except Exception as e:
        raise Exception(f"שגיאה בניתוח: {str(e)}")

def process_video(url):
    """Main processing function running in background"""
    try:
        progress_data['status'] = 'processing'
        progress_data['error'] = None

        # Download
        video_file = download_video(url)

        # Transcribe
        transcript = transcribe_audio(video_file)

        # Analyze
        result = analyze_with_claude(transcript)

        progress_data['status'] = 'complete'
        progress_data['progress'] = 100
        progress_data['message'] = 'סיכום מוכן!'
        progress_data['result'] = result

        # Cleanup
        try:
            os.remove(video_file)
        except:
            pass

    except Exception as e:
        progress_data['status'] = 'error'
        progress_data['error'] = str(e)
        progress_data['message'] = f"שגיאה: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'App is running'}), 200

@app.route('/api/progress')
def get_progress():
    return jsonify(progress_data)

@app.route('/api/summarize', methods=['POST'])
def summarize():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    # Reset progress
    progress_data['status'] = 'idle'
    progress_data['message'] = ''
    progress_data['progress'] = 0
    progress_data['result'] = None
    progress_data['error'] = None

    # Start processing in background thread
    thread = threading.Thread(target=process_video, args=(url,))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'processing'})

if __name__ == '__main__':
    os.makedirs('summarized_videos', exist_ok=True)
    app.run(debug=False, host='0.0.0.0', port=5000)
