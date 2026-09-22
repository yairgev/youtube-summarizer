# YouTube Video Summarizer - Docker Container

FROM python:3.11-slim

# התקן FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# כדיר עבודה
WORKDIR /app

# העתק קבצים
COPY requirements.txt .
COPY app.py .
COPY index.html .

# התקן Python ספריות
RUN pip install --no-cache-dir -r requirements.txt

# יצור תיקיות
RUN mkdir -p summarized_videos

# PORT
EXPOSE 5000

# הרץ את השרת
CMD ["python", "app.py"]
