import openai
import json
import logging
from sqlalchemy.orm import Session
from models import Video, Transcript, Summary
from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self):
        if not OPENAI_API_KEY:
            logger.warning("OpenAI API key not found. AI service will not work.")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    async def generate_summary_and_action_plan(self, video_id: str, db: Session) -> dict:
        """Generate summary and action plan using GPT-4"""
        try:
            if not self.client:
                raise Exception("OpenAI client not initialized. Check API key.")

            # Get transcript from database
            transcript = db.query(Transcript).filter(Transcript.video_id == video_id).first()
            if not transcript:
                raise Exception("Transcript not found")

            video = db.query(Video).filter(Video.id == video_id).first()
            video_title = video.title if video else "Unknown Video"

            # Create prompt for GPT-4
            prompt = f"""
            Please analyze the following video transcript and provide:
            1. A comprehensive summary (2-3 paragraphs)
            2. Key points (5-7 bullet points)
            3. Action plan (5-7 actionable steps)

            Video Title: {video_title}

            Transcript:
            {transcript.transcript}

            Please format your response as JSON with the following structure:
            {{
                "summary": "comprehensive summary here",
                "key_points": ["point 1", "point 2", ...],
                "action_plan": ["action 1", "action 2", ...]
            }}
            """

            # Call GPT-4
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system",
                     "content": "You are an expert at analyzing video content and creating actionable insights. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            # Parse the response
            try:
                content = response.choices[0].message.content
                # Clean up the response if it has markdown formatting
                if content.startswith("```json"):
                    content = content.replace("```json", "").replace("```", "").strip()

                result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {e}")
                # Fallback if JSON parsing fails
                content = response.choices[0].message.content
                result = {
                    "summary": content[:500] + "..." if len(content) > 500 else content,
                    "key_points": ["Analysis completed - see summary for details"],
                    "action_plan": ["Review the summary and create personalized action items"]
                }

            # Save to database
            summary_record = Summary(
                video_id=video_id,
                summary=result["summary"],
                key_points=json.dumps(result["key_points"]),
                action_plan=json.dumps(result["action_plan"])
            )
            db.add(summary_record)
            db.commit()

            return result

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise e