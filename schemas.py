from pydantic import BaseModel, HttpUrl, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class VideoDownloadRequest(BaseModel):
    url: str

    @validator('url')
    def validate_url(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError('URL is required')

        # Basic YouTube URL validation
        youtube_domains = [
            'youtube.com', 'www.youtube.com', 'm.youtube.com',
            'youtu.be', 'www.youtu.be'
        ]

        if not any(domain in v.lower() for domain in youtube_domains):
            raise ValueError('Please provide a valid YouTube URL')

        return v


class VideoResponse(BaseModel):
    id: str
    title: str
    duration: float
    audio_path: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class VideoDetails(BaseModel):
    id: str
    title: str
    url: str
    duration: float
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_size: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: Optional[float] = None


class TranscriptResponse(BaseModel):
    video_id: str
    transcript: str
    segments: List[TranscriptSegment] = []
    language: str = "en"
    confidence: Optional[float] = None
    word_count: Optional[int] = None
    processing_time: Optional[float] = None
    status: str = "completed"

    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    video_id: str
    summary: str
    key_points: List[str] = []
    action_plan: List[str] = []
    tags: List[str] = []
    category: Optional[str] = None
    summary_length: Optional[int] = None
    processing_time: Optional[float] = None
    model_used: Optional[str] = None
    status: str = "completed"

    class Config:
        from_attributes = True


class ProcessingJobResponse(BaseModel):
    id: str
    video_id: str
    job_type: str
    status: str
    progress: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VideoListResponse(BaseModel):
    videos: List[VideoDetails]
    total: int
    page: int = 1
    per_page: int = 50


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = datetime.now()


class SuccessResponse(BaseModel):
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = datetime.now()