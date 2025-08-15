import os
import json
import logging
import openai
from sqlalchemy.orm import Session
from models import Video, Transcript
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

try:
    import whisper
    WHISPER_AVAILABLE = True
    logger.info("Local Whisper model available as fallback")
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("Local Whisper not available. Install with: pip install openai-whisper")


class TranscriptService:
    def __init__(self):
        # Initialize OpenAI client
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not found. Will use local Whisper only.")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

        # Initialize local Whisper model
        self.local_model = None
        if WHISPER_AVAILABLE:
            try:
                logger.info("Loading local Whisper model (base)...")
                self.local_model = whisper.load_model("base")
                logger.info("Local Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load local Whisper model: {e}")
                self.local_model = None

        # Base path for downloads
        self.download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

    async def generate_transcript(self, video_id: str, db: Session) -> dict:
        """Generate transcript using available transcription service"""
        try:
            # Get video record
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise Exception("Video not found")

            # Build full audio path
            audio_path = os.path.join(self.download_dir, video.audio_path)

            # Validate file exists
            if not video.audio_path or not os.path.exists(audio_path):
                raise Exception(f"Audio file not found at: {audio_path}")

            logger.info(f"Processing audio file: {audio_path}")

            # File size
            file_size = os.path.getsize(audio_path)
            logger.info(f"Audio file size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")

            # Decide transcription method
            if file_size > 25 * 1024 * 1024 or not self.client:
                if self.local_model:
                    logger.info("Using local Whisper (file too large for OpenAI or no API key)")
                    return await self._generate_local_transcript(video_id, audio_path, db)
                else:
                    raise Exception("File too large for OpenAI API and local Whisper not available")

            if self.client:
                try:
                    logger.info("Attempting transcript generation with OpenAI Whisper...")
                    return await self._generate_openai_transcript(video_id, audio_path, db)
                except Exception as openai_error:
                    logger.warning(f"OpenAI Whisper failed: {openai_error}")
                    if self.local_model:
                        logger.info("Falling back to local Whisper...")
                        return await self._generate_local_transcript(video_id, audio_path, db)
                    else:
                        raise openai_error

            raise Exception("No transcription method available. Please install local Whisper or configure OpenAI API key.")

        except Exception as e:
            logger.error(f"Error generating transcript: {str(e)}")
            raise e

    async def _generate_openai_transcript(self, video_id: str, audio_path: str, db: Session) -> dict:
        """Generate transcript using OpenAI Whisper API"""
        try:
            logger.info(f"Opening audio file: {audio_path}")
            with open(audio_path, "rb") as audio_file:
                logger.info("Sending request to OpenAI Whisper API...")
                transcript_response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )

            logger.info("Received response from OpenAI Whisper API")

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

            transcript_record = Transcript(
                video_id=video_id,
                transcript=transcript_text,
                language=language,
                segments=json.dumps(segments),
                word_count=len(transcript_text.split()),
                processing_time=0
            )
            db.add(transcript_record)
            db.commit()

            return {
                "transcript": transcript_text,
                "segments": segments,
                "language": language
            }

        except Exception as e:
            logger.error(f"OpenAI Whisper API error: {str(e)}")
            raise e

    async def _generate_local_transcript(self, video_id: str, audio_path: str, db: Session) -> dict:
        """Generate transcript using local Whisper model"""
        try:
            logger.info(f"Processing with local Whisper: {audio_path}")
            result = self.local_model.transcribe(audio_path, verbose=False, word_timestamps=True)

            transcript_text = result["text"]
            language = result.get("language", "en")

            segments = []
            if "segments" in result:
                segments = [
                    {
                        "start": segment["start"],
                        "end": segment["end"],
                        "text": segment["text"].strip()
                    }
                    for segment in result["segments"]
                ]

            word_count = len(transcript_text.split())

            transcript_record = Transcript(
                video_id=video_id,
                transcript=transcript_text,
                language=language,
                segments=json.dumps(segments),
                word_count=word_count,
                processing_time=0
            )
            db.add(transcript_record)
            db.commit()

            return {
                "transcript": transcript_text,
                "segments": segments,
                "language": language
            }

        except Exception as e:
            logger.error(f"Local Whisper error: {str(e)}")
            raise e
