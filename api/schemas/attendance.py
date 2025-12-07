from pydantic import BaseModel
from typing import Optional
from datetime import time
from database.models import UserRole, DayOfWeek, AttendanceStatus

# User schemas
class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    role: UserRole
    profile_image: Optional[str] = None

class UserGet(BaseModel):
    user_id: int
    email: str
    first_name: str
    last_name: str
    role: UserRole
    profile_image: Optional[str] = None

# Enrollment schemas
class EnrollmentRequest(BaseModel):
    student_email: str
    image_paths: list[str]

class EnrollmentResponse(BaseModel):
    user_id: int
    email: str
    full_name: str
    embeddings_stored: int

# Course schemas
class CourseCreate(BaseModel):
    course_name: str
    course_code: str
    doctor_id: int
    description: Optional[str] = None

class CourseGet(BaseModel):
    course_id: int
    course_name: str
    course_code: str
    doctor_id: int
    description: Optional[str] = None

# Lecture schemas
class LectureCreate(BaseModel):
    course_id: int
    start_time: str  # Format: "HH:MM:SS"
    end_time: str    # Format: "HH:MM:SS"
    day_of_week: DayOfWeek
    room_num: Optional[int] = None

class LectureGet(BaseModel):
    lecture_id: int
    course_id: int
    start_time: time
    end_time: time
    day_of_week: DayOfWeek
    room_num: Optional[int] = None

# Attendance schemas
class AttendanceMark(BaseModel):
    lecture_id: int
    student_id: int
    is_present: AttendanceStatus

class AttendanceGet(BaseModel):
    lecture_id: int
    student_id: int
    is_present: AttendanceStatus

# Student-Course enrollment
class StudentCourseEnroll(BaseModel):
    student_id: int
    course_id: int

# Attendance taking from image
class AttendanceImageRequest(BaseModel):
    lecture_id: int
    image_path: str
    threshold: float = 0.6

class RecognizedStudent(BaseModel):
    user_id: int
    name: str
    email: str
    confidence: float

class AttendanceImageResponse(BaseModel):
    lecture_id: int
    recognized_students: list[RecognizedStudent]
    total_faces_detected: int

