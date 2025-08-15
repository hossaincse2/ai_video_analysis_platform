import yt_dlp
import os
import logging
from pathlib import Path
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from models import Video
import re
import sys
import traceback

logger = logging.getLogger(__name__)


class YouTubeService:
    def __init__(self):
        # Use absolute paths to avoid Windows issues
        self.download_dir = Path.cwd() / "downloads"
        self.download_dir.mkdir(exist_ok=True)

        logger.info(f"Download directory: {self.download_dir.absolute()}")
        logger.info(f"Current working directory: {Path.cwd()}")
        logger.info(f"Python executable: {sys.executable}")

    def test_system(self) -> dict:
        """Test system capabilities and find potential issues"""
        results = {
            "python_executable": sys.executable,
            "working_directory": str(Path.cwd()),
            "download_directory": str(self.download_dir.absolute()),
            "download_dir_exists": self.download_dir.exists(),
            "download_dir_writable": False,
            "yt_dlp_import": False,
            "yt_dlp_version": None,
            "test_file_creation": False,
            "errors": []
        }

        try:
            # Test directory write permissions
            test_file = self.download_dir / "test_write.txt"
            test_file.write_text("test")
            test_file.unlink()
            results["download_dir_writable"] = True
        except Exception as e:
            results["errors"].append(f"Directory write test failed: {e}")

        try:
            # Test yt-dlp import and version
            import yt_dlp
            results["yt_dlp_import"] = True
            results["yt_dlp_version"] = yt_dlp.version.__version__
        except Exception as e:
            results["errors"].append(f"yt-dlp import failed: {e}")

        try:
            # Test yt-dlp basic functionality
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                # Test with a simple URL extraction (no download)
                info = ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
                results["yt_dlp_basic_test"] = True
        except Exception as e:
            results["errors"].append(f"yt-dlp basic test failed: {e}")

        return results

    async def download_video(self, url: str, db: Session) -> dict:
        """Download YouTube audio with enhanced error handling"""
        video_id = str(uuid.uuid4())

        try:
            logger.info(f"=== Starting download for URL: {url} ===")
            logger.info(f"Video ID: {video_id}")
            logger.info(f"Download directory: {self.download_dir.absolute()}")

            # Create initial video record
            video = Video(
                id=video_id,
                title="Processing...",
                url=url,
                status="processing"
            )
            db.add(video)
            db.commit()
            logger.info("Video record created in database")

            # Create output template with absolute path
            output_template = str(self.download_dir.absolute() / f'{video_id}_%(title)s.%(ext)s')
            logger.info(f"Output template: {output_template}")

            # Configure yt-dlp options with explicit paths
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[ext=webm]/bestaudio',
                'outtmpl': output_template,
                'noplaylist': True,
                'quiet': False,  # Enable verbose output for debugging
                'no_warnings': False,
                'extractaudio': False,  # Don't try to extract, just download
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ignoreerrors': False,
            }

            logger.info("Creating yt-dlp instance...")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info("yt-dlp instance created successfully")

                    # Get video info first
                    logger.info("Extracting video information...")
                    try:
                        info = ydl.extract_info(url, download=False)
                        logger.info("Video info extracted successfully")
                    except Exception as info_error:
                        logger.error(f"Failed to extract video info: {info_error}")
                        logger.error(f"Info error traceback: {traceback.format_exc()}")
                        raise Exception(f"Could not extract video information: {str(info_error)}")

                    title = info.get('title', 'Unknown Title')
                    duration = info.get('duration', 0)

                    # Clean title for logging
                    safe_title = self._sanitize_filename(title)
                    logger.info(f"Video Title: {title}")
                    logger.info(f"Safe Title: {safe_title}")
                    logger.info(f"Duration: {duration}s")

                    # Update video record with info
                    video.title = title
                    video.duration = duration
                    db.commit()
                    logger.info("Video record updated with metadata")

                    # Download audio
                    logger.info("Starting download...")
                    try:
                        # List files before download
                        files_before = list(self.download_dir.glob("*"))
                        logger.info(f"Files before download: {len(files_before)}")

                        ydl.download([url])
                        logger.info("Download completed successfully")

                        # List files after download
                        files_after = list(self.download_dir.glob("*"))
                        logger.info(f"Files after download: {len(files_after)}")

                        # Show new files
                        new_files = set(files_after) - set(files_before)
                        logger.info(f"New files created: {[str(f) for f in new_files]}")

                    except Exception as download_error:
                        logger.error(f"Download failed: {download_error}")
                        logger.error(f"Download error traceback: {traceback.format_exc()}")
                        raise Exception(f"Download failed: {str(download_error)}")

                    # Find the downloaded audio file
                    audio_path = self._find_audio_file(video_id)

                    if not audio_path:
                        # Enhanced file search debugging
                        logger.error("=== FILE SEARCH DEBUG ===")
                        all_files = list(self.download_dir.glob("*"))
                        logger.error(f"All files in directory: {[str(f) for f in all_files]}")

                        # Search by time
                        recent_files = []
                        current_time = datetime.now().timestamp()
                        for file in all_files:
                            if file.is_file():
                                mod_time = file.stat().st_mtime
                                if mod_time > (current_time - 600):  # 10 minutes
                                    recent_files.append((str(file), datetime.fromtimestamp(mod_time)))

                        logger.error(f"Recent files: {recent_files}")
                        raise Exception("Failed to find downloaded audio file")

                    # Verify file exists and is readable
                    audio_file_path = Path(audio_path)
                    if not audio_file_path.exists():
                        raise Exception(f"Audio file does not exist: {audio_path}")

                    file_size = audio_file_path.stat().st_size
                    logger.info(f"Audio file size: {file_size} bytes")

                    if file_size == 0:
                        raise Exception("Downloaded audio file is empty")

                    # Update video record with audio path
                    video.audio_path = str(audio_file_path.absolute())
                    video.status = "completed"
                    db.commit()

                    logger.info(f"=== Successfully processed video: {title} ===")
                    logger.info(f"Audio file: {video.audio_path}")

                    return {
                        "id": video_id,
                        "title": title,
                        "url": url,
                        "duration": duration,
                        "audio_path": video.audio_path,
                        "status": "completed"
                    }

            except Exception as ydl_error:
                logger.error(f"yt-dlp error: {ydl_error}")
                logger.error(f"yt-dlp traceback: {traceback.format_exc()}")
                raise ydl_error

        except Exception as e:
            logger.error(f"=== ERROR IN DOWNLOAD PROCESS ===")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

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

    def _find_audio_file(self, video_id: str) -> str:
        """Find the downloaded audio file with enhanced debugging"""
        # Audio formats that don't need conversion
        audio_extensions = ['.m4a', '.mp3', '.webm', '.ogg', '.opus', '.aac', '.wav']

        logger.info(f"=== SEARCHING FOR AUDIO FILE ===")
        logger.info(f"Video ID: {video_id}")
        logger.info(f"Search directory: {self.download_dir.absolute()}")

        # List all files in directory
        all_files = list(self.download_dir.glob("*"))
        logger.info(f"Total files in directory: {len(all_files)}")

        for file in all_files:
            logger.info(f"  File: {file.name} (size: {file.stat().st_size if file.is_file() else 'N/A'})")

        # Search for files with video ID prefix
        logger.info(f"Searching for files with prefix: {video_id}_")
        matching_files = list(self.download_dir.glob(f"{video_id}_*"))
        logger.info(f"Files with video ID prefix: {len(matching_files)}")

        for file in matching_files:
            logger.info(f"  Matching file: {file}")
            if any(file.name.lower().endswith(ext) for ext in audio_extensions):
                logger.info(f"Found audio file with video ID: {file}")
                return str(file.absolute())

        # Search for recent audio files (last 10 minutes)
        logger.info("Searching for recent audio files...")
        current_time = datetime.now().timestamp()

        for file in self.download_dir.glob("*"):
            if file.is_file() and any(file.name.lower().endswith(ext) for ext in audio_extensions):
                file_mod_time = file.stat().st_mtime
                age_minutes = (current_time - file_mod_time) / 60
                logger.info(f"  Audio file: {file.name} (age: {age_minutes:.1f} minutes)")

                if file_mod_time > (current_time - 600):  # 10 minutes
                    logger.info(f"Found recent audio file: {file}")
                    return str(file.absolute())

        logger.error("No suitable audio file found")
        return None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for Windows compatibility"""
        if not filename:
            return "unknown"

        # Remove invalid Windows filename characters
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')

        # Remove non-printable characters
        filename = ''.join(char for char in filename if ord(char) > 31)

        # Replace multiple spaces/dashes with single dash
        filename = re.sub(r'[\s\-]+', '-', filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')

        # Limit length
        return filename[:100] if filename else "unknown"

    def get_service_status(self) -> dict:
        """Get comprehensive service status"""
        return {
            "download_directory": str(self.download_dir.absolute()),
            "download_directory_exists": self.download_dir.exists(),
            "ffmpeg_required": False,
            "service_ready": True,
            "system_test": self.test_system()
        }