from typing import List, Optional, Any
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import selectinload
import numpy as np
import logging
import json

from database.models import User, UserRole, Embedding, Course, Lecture, Attendance, AttendanceStatus, DayOfWeek
from ai_module.facerecognition_service import FaceRecognitionService

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.face_rec = FaceRecognitionService()

    async def create_user(self, email: str, first_name: str, last_name: str, user_type: UserRole, password_hash: str) -> int:
        new_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=user_type,
            password=password_hash
        )
        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)
        
        if new_user.user_id is None:
            raise ValueError("Failed to create user")
            
        return new_user.user_id

    async def get_user_by_email(self, email: str) -> Optional[User]:
        statement = select(User).where(User.email == email)
        result = await self.session.exec(statement)
        return result.first()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def store_embedding(self, user_id: int, embedding: np.ndarray, image_path: str):
        # Convert numpy to list then to json string
        emb_list = embedding.tolist()
        emb_json = json.dumps(emb_list)
        
        new_embedding = Embedding(
            user_id=user_id, 
            face_vector=emb_json, 
            image_path=image_path
        )
        self.session.add(new_embedding)
        await self.session.commit()

    async def create_course(self, course_name: str, course_code: str, doctor_id: int, description: Optional[str] = None) -> int:
        new_course = Course(
            course_name=course_name,
            course_code=course_code,
            doctor_id=doctor_id,
            description=description
        )
        self.session.add(new_course)
        await self.session.commit()
        await self.session.refresh(new_course)
        
        if new_course.course_id is None:
            raise ValueError("Failed to create course")
            
        return new_course.course_id

    async def create_lecture(self, course_id: int, start_time: str, end_time: str, day_of_week: DayOfWeek, room_num: Optional[int] = None) -> int:
        from datetime import time as dt_time
        # Handle string to time conversion if needed, assuming input is HH:MM:SS string
        # If it's already time object, direct assignment. 
        # But schemas usually pass string.
        if isinstance(start_time, str):
            start = dt_time.fromisoformat(start_time)
        else:
            start = start_time
            
        if isinstance(end_time, str):
            end = dt_time.fromisoformat(end_time)
        else:
            end = end_time
        
        new_lecture = Lecture(
            course_id=course_id,
            start_time=start,
            end_time=end,
            day_of_week=day_of_week,
            room_num=room_num
        )
        self.session.add(new_lecture)
        await self.session.commit()
        await self.session.refresh(new_lecture)
        
        if new_lecture.lecture_id is None:
            raise ValueError("Failed to create lecture")
            
        return new_lecture.lecture_id

    async def mark_attendance(self, lecture_id: int, student_id: int, is_present: AttendanceStatus) -> bool:
        statement = select(Attendance).where(Attendance.lecture_id == lecture_id, Attendance.student_id == student_id)
        result = await self.session.exec(statement)
        attendance = result.first()
        
        if attendance:
            attendance.is_present = is_present
            self.session.add(attendance)
        else:
            attendance = Attendance(
                lecture_id=lecture_id,
                student_id=student_id,
                is_present=is_present
            )
            self.session.add(attendance)
        
        await self.session.commit()
        return True

    async def get_present_students(self, course_id: Optional[int] = None, doctor_id: Optional[int] = None) -> List[dict]:
        query = select(Attendance, User, Lecture, Course).join(User, Attendance.student_id == User.user_id).join(Lecture, Attendance.lecture_id == Lecture.lecture_id).join(Course, Lecture.course_id == Course.course_id).where(Attendance.is_present == AttendanceStatus.present)
        
        if course_id:
            query = query.where(Course.course_id == course_id)
        if doctor_id:
            query = query.where(Course.doctor_id == doctor_id)
            
        result = await self.session.exec(query)
        rows = result.all()
        
        present_students = []
        for attendance, student, lecture, course in rows:
            present_students.append({
                "student_id": student.user_id,
                "full_name": f"{student.first_name} {student.last_name}",
                "email": student.email,
                "course_name": course.course_name,
                "lecture_date": str(lecture.day_of_week),
                "lecture_time": str(lecture.start_time),
                "attendance_status": attendance.is_present
            })
        return present_students

    async def find_similar_faces(self, target_embedding: np.ndarray, threshold: float = 0.6, limit: int = 1) -> List[dict]:
        # Fetch all embeddings
        # Ideally this should be optimized using pgvector extension in Postgres
        # But for now we do in-memory comparison of all embeddings
        statement = select(Embedding).options(selectinload(Embedding.user))
        result = await self.session.exec(statement)
        all_embeddings = result.all()
        
        matches = []
        for db_emb in all_embeddings:
            try:
                # Convert json string back to numpy
                stored_emb_list = json.loads(db_emb.face_vector)
                stored_emb = np.array(stored_emb_list, dtype=np.float32)
                
                similarity = self.face_rec.compute_similarity(target_embedding, stored_emb)
                
                if similarity >= threshold:
                    # Access user via relationship (async safe because of selectinload)
                    user = db_emb.user
                    if user:
                        matches.append({
                            "user_id": user.user_id,
                            "full_name": f"{user.first_name} {user.last_name}",
                            "email": user.email,
                            "similarity": float(similarity)
                        })
            except Exception as e:
                logger.error(f"Error processing embedding {db_emb.embedding_id}: {e}")
                continue
        
        # Sort by similarity desc
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Filter duplicates (same user might have multiple high sim embeddings)
        # We want best match per user? Or just best matches overall?
        # If multiple faces of same user match, we just want the user once with highest score.
        unique_matches = {}
        for m in matches:
            uid = m['user_id']
            if uid not in unique_matches:
                unique_matches[uid] = m
            # Since sorted, first one is best
        
        final_matches = list(unique_matches.values())
        
        return final_matches[:limit]
