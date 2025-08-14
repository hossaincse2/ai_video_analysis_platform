import openai
import json
import logging
import os
from sqlalchemy.orm import Session
from models import Video, Transcript
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


class TranscriptService:
    def __init__(self):
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not found. Transcript service will not work.")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    async def generate_transcript(self, video_id: str, db: Session) -> dict:
        """Generate transcript using OpenAI Whisper"""
        try:
            if not self.client:
                raise Exception("OpenAI client not initialized. Check API key.")

            # Get video from database
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise Exception("Video not found")

            if not video.audio_path or not os.path.exists(video.audio_path):
                raise Exception("Audio file not found")

            # Generate transcript using Whisper
            with open(video.audio_path, "rb") as audio_file:
                transcript_response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            # Extract transcript and segments
            transcript_text = transcript_response.text
            segments = []

            if hasattr(transcript_response, 'segments'):
                segments = [
                    {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text
                    }
                    for segment in transcript_response.segments
                ]

            language = getattr(transcript_response, 'language', 'en')

            # Save to database
            transcript_record = Transcript(
                video_id=video_id,
                transcript=transcript_text,
                language=language,
                segments=json.dumps(segments)
            )
            db.add(transcript_record)
            db.commit()

            return {
                "transcript": transcript_text,
                "segments": segments,
                "language": language
            }

        except Exception as e:
            logger.error(f"Error generating transcript: {str(e)}")
            raise e