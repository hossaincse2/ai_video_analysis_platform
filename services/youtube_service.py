import yt_dlp
import os
import logging
from pathlib import Path
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from models import Video
import re

logger = logging.getLogger(__name__)


class YouTubeService:
    def __init__(self):
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)

    async def download_video(self, url: str, db: Session) -> dict:
        """Download YouTube video and extract audio"""
        video_id = str(uuid.uuid4())

        try:
            logger.info(f"Starting download for URL: {url}")

            # Create initial video record
            video = Video(
                id=video_id,
                title="Processing...",
                url=url,
                status="processing"
            )
            db.add(video)
            db.commit()

            # Configure yt-dlp options for audio extraction
            # ydl_opts = {
            #     'format': 'bestaudio/best',
            #     'outtmpl': str(self.download_dir / f'{video_id}_%(title)s.%(ext)s'),
            #     'postprocessors': [{
            #         'key': 'FFmpegExtractAudio',
            #         'preferredcodec': 'mp3',
            #         'preferredquality': '192',
            #     }],
            #     'noplaylist': True,
            #     'quiet': True,
            #     'no_warnings': True,
            #     'extractaudio': True,
            #     'audioformat': 'mp3',
            #     # Add FFmpeg path if not in system PATH
            #     'ffmpeg_location': '/path/to/ffmpeg',  # Update with actual path
            # }
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
                'outtmpl': str(self.download_dir / f'{video_id}_%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                # Remove postprocessors to avoid FFmpeg requirement
                # 'postprocessors': [{
                #     'key': 'FFmpegExtractAudio',
                #     'preferredcodec': 'mp3',
                #     'preferredquality': '192',
                # }],
                # 'extractaudio': True,
                # 'audioformat': 'mp3',
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info first
                logger.info("Extracting video information...")
                info = ydl.extract_info(url, download=False)

                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)

                # Clean title for safe filename
                safe_title = self._sanitize_filename(title)

                logger.info(f"Video info - Title: {title}, Duration: {duration}s")

                # Update video record with info
                video.title = title
                video.duration = duration
                db.commit()

                # Download and convert to audio
                logger.info("Downloading and converting to audio...")
                ydl.download([url])

                # Find the downloaded audio file
                audio_path = self._find_audio_file(video_id, safe_title)

                if not audio_path:
                    raise Exception("Failed to find downloaded audio file")

                # Update video record with audio path
                video.audio_path = audio_path
                video.status = "completed"
                db.commit()

                logger.info(f"Successfully processed video: {title}")

                return {
                    "id": video_id,
                    "title": title,
                    "url": url,
                    "duration": duration,
                    "audio_path": audio_path,
                    "status": "completed"
                }

        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")

            # Update video record with error status
            try:
                video = db.query(Video).filter(Video.id == video_id).first()
                if video:
                    video.status = "error"
                    video.title = f"Error: {str(e)[:100]}"
                    db.commit()
            except Exception as db_error:
                logger.error(f"Error updating video status: {db_error}")

            raise e

    def _find_audio_file(self, video_id: str, safe_title: str) -> str:
        """Find the downloaded audio file"""
        possible_extensions = ['.mp3', '.m4a', '.wav', '.aac']

        # Search for the audio file with video ID prefix
        for file in self.download_dir.glob(f"{video_id}_*"):
            if any(file.name.endswith(ext) for ext in possible_extensions):
                logger.info(f"Found audio file: {file}")
                return str(file)

        # Alternative search for recent files
        current_time = datetime.now().timestamp()
        for file in self.download_dir.glob("*.mp3"):
            if file.stat().st_mtime > (current_time - 300):  # Modified in last 5 minutes
                logger.info(f"Found recent audio file: {file}")
                return str(file)

        # Last resort: find any recent audio file
        for ext in possible_extensions:
            for file in self.download_dir.glob(f"*{ext}"):
                if file.stat().st_mtime > (current_time - 300):
                    logger.info(f"Found recent audio file: {file}")
                    return str(file)

        return None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system usage"""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'[^\w\s-]', '', filename).strip()
        filename = re.sub(r'[-\s]+', '-', filename)
        return filename[:100]  # Limit length

    def get_video_by_id(self, video_id: str, db: Session) -> Video:
        """Get video by ID from database"""
        try:
            return db.query(Video).filter(Video.id == video_id).first()
        except Exception as e:
            logger.error(f"Error getting video from database: {e}")
            raise

    def list_videos(self, db: Session, limit: int = 50) -> list:
        """List videos from database"""
        try:
            return db.query(Video).order_by(Video.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error listing videos from database: {e}")
            raise

    def delete_video(self, video_id: str, db: Session) -> bool:
        """Delete video and associated files"""
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                return False

            # Delete audio file if exists
            if video.audio_path and os.path.exists(video.audio_path):
                os.remove(video.audio_path)
                logger.info(f"Deleted audio file: {video.audio_path}")

            # Delete video file if exists
            if video.video_path and os.path.exists(video.video_path):
                os.remove(video.video_path)
                logger.info(f"Deleted video file: {video.video_path}")

            # Delete from database
            db.delete(video)
            db.commit()

            return True
        except Exception as e:
            logger.error(f"Error deleting video: {e}")
            db.rollback()
            raise