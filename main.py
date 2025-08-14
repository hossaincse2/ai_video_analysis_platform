from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import uvicorn
import os
from pathlib import Path
import logging

# Import after ensuring config is loaded
try:
    from database import get_db, engine
    from models import Base, Video, Transcript, Summary
    from services.youtube_service import YouTubeService
    from services.transcript_service import TranscriptService
    from services.ai_service import AIService
    from schemas import VideoDownloadRequest, VideoResponse, TranscriptResponse, SummaryResponse
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all dependencies are installed and environment is configured")
    exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Error creating database tables: {e}")

app = FastAPI(
    title="AI Video Analysis Platform",
    description="Backend API for video processing and AI analysis",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs("downloads", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

# Initialize services
youtube_service = YouTubeService()
transcript_service = TranscriptService()
ai_service = AIService()


@app.get("/")
async def root():
    return {"message": "AI Video Analysis Platform API", "version": "1.0.0"}


@app.post("/api/videos/downloads", response_model=VideoResponse)
async def download_video(
        request: VideoDownloadRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """Download YouTube video and extract audio"""
    try:
        logger.info(f"Processing video URL: {request.url}")

        # Download video and extract audio using the real service
        result = await youtube_service.download_video(request.url, db)

        return VideoResponse(
            id=result["id"],
            title=result["title"],
            duration=result["duration"],
            audio_path=result["audio_path"],
            status="completed"
        )
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/videos/transcript", response_model=TranscriptResponse)
async def generate_transcript(
        video_id: str,
        db: Session = Depends(get_db)
):
    """Generate transcript from audio using OpenAI Whisper"""
    try:
        logger.info(f"Generating transcript for video ID: {video_id}")

        result = await transcript_service.generate_transcript(video_id, db)

        return TranscriptResponse(
            video_id=video_id,
            transcript=result["transcript"],
            segments=result["segments"],
            language=result["language"],
            status="completed"
        )
    except Exception as e:
        logger.error(f"Error generating transcript: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/videos/summarize", response_model=SummaryResponse)
async def generate_summary(
        video_id: str,
        db: Session = Depends(get_db)
):
    """Generate summary and action plan using GPT-4"""
    try:
        logger.info(f"Generating summary for video ID: {video_id}")

        result = await ai_service.generate_summary_and_action_plan(video_id, db)

        return SummaryResponse(
            video_id=video_id,
            summary=result["summary"],
            key_points=result["key_points"],
            action_plan=result["action_plan"],
            status="completed"
        )
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/videos/{video_id}")
async def get_video_details(video_id: str, db: Session = Depends(get_db)):
    """Get video processing details"""
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        return {
            "id": video.id,
            "title": video.title,
            "url": video.url,
            "duration": video.duration,
            "audio_path": video.audio_path,
            "status": video.status,
            "created_at": video.created_at.isoformat() if video.created_at else None
        }
    except Exception as e:
        logger.error(f"Error getting video details: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/videos/{video_id}/download")
async def download_audio_file(video_id: str, db: Session = Depends(get_db)):
    """Download the processed audio file"""
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.audio_path:
            raise HTTPException(status_code=404, detail="Audio file not found")

        if not os.path.exists(video.audio_path):
            raise HTTPException(status_code=404, detail="Audio file not found on disk")

        # Clean the filename for download
        safe_filename = "".join(c for c in video.title if c.isalnum() or c in (' ', '-', '_')).rstrip()

        return FileResponse(
            video.audio_path,
            media_type='audio/mpeg',
            filename=f"{safe_filename}.mp3"
        )
    except Exception as e:
        logger.error(f"Error downloading audio file: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/videos")
async def list_videos(db: Session = Depends(get_db)):
    """List all processed videos"""
    try:
        videos = db.query(Video).order_by(Video.created_at.desc()).all()
        return [{
            "id": video.id,
            "title": video.title,
            "url": video.url,
            "duration": video.duration,
            "status": video.status,
            "created_at": video.created_at.isoformat() if video.created_at else None
        } for video in videos]
    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)