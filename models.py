from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
import uuid


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    duration = Column(Float, default=0)
    audio_path = Column(String)
    video_path = Column(String)
    thumbnail_path = Column(String)
    file_size = Column(Integer)  # in bytes
    status = Column(String, default="processing")  # processing, completed, error
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    transcripts = relationship("Transcript", back_populates="video")
    summaries = relationship("Summary", back_populates="video")

    def __repr__(self):
        return f"<Video(id={self.id}, title={self.title}, status={self.status})>"


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey('videos.id'), nullable=False)
    transcript = Column(Text, nullable=False)
    language = Column(String, default="en")
    confidence = Column(Float)  # Average confidence score
    segments = Column(Text)  # JSON string of segments with timestamps
    word_count = Column(Integer)
    processing_time = Column(Float)  # Time taken to generate transcript
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    video = relationship("Video", back_populates="transcripts")

    def __repr__(self):
        return f"<Transcript(id={self.id}, video_id={self.video_id}, language={self.language})>"


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey('videos.id'), nullable=False)
    summary = Column(Text, nullable=False)
    key_points = Column(Text)  # JSON string of key points
    action_plan = Column(Text)  # JSON string of action items
    tags = Column(Text)  # JSON string of generated tags
    category = Column(String)  # Auto-detected category
    summary_length = Column(Integer)  # Length of summary in words
    processing_time = Column(Float)  # Time taken to generate summary
    model_used = Column(String)  # AI model used for generation
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    video = relationship("Video", back_populates="summaries")

    def __repr__(self):
        return f"<Summary(id={self.id}, video_id={self.video_id}, category={self.category})>"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey('videos.id'), nullable=False)
    job_type = Column(String, nullable=False)  # download, transcript, summary
    status = Column(String, default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ProcessingJob(id={self.id}, job_type={self.job_type}, status={self.status})>"