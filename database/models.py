from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import time
import json

# Enums
class UserRole(str, Enum):
    student = "student"
    doctor = "doctor"
    admin = "admin"

class DayOfWeek(str, Enum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"

class AttendanceStatus(str, Enum):
    present = "present"
    absent = "absent"

# Base models
class User(SQLModel, table=True):
    __tablename__: str = "users"
    
    user_id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password: str
    first_name: str
    last_name: str
    role: UserRole
    profile_image: Optional[str] = None
    
    # Relationships
    embedding: Optional["Embedding"] = Relationship(back_populates="user", sa_relationship_kwargs={"uselist": False})
    student_courses: List["StudentCourse"] = Relationship(back_populates="student")
    doctor_courses: List["Course"] = Relationship(back_populates="doctor")
    attendance_records: List["Attendance"] = Relationship(back_populates="student")

class Embedding(SQLModel, table=True):
    __tablename__ :str= "embeddings"
    
    embedding_id: int | None = Field(default=None, primary_key=True)
    face_vector: str  # JSON string of the embedding vector
    image_path: Optional[str] = None
    user_id: int = Field(foreign_key="users.user_id")
    
    # Relationships
    user: Optional["User"] = Relationship(back_populates="embedding")

class Course(SQLModel, table=True):
    __tablename__ :str= "courses"
    
    course_id: int | None = Field(default=None, primary_key=True)
    course_name: str
    description: Optional[str] = None
    doctor_id: int = Field(foreign_key="users.user_id")
    course_code: str = Field(unique=True, index=True)
    
    # Relationships
    doctor: Optional["User"] = Relationship(back_populates="doctor_courses")
    student_courses: List["StudentCourse"] = Relationship(back_populates="course")
    lectures: List["Lecture"] = Relationship(back_populates="course")

class StudentCourse(SQLModel, table=True):
    __tablename__ :str= "student_courses"
    
    student_id: int = Field(foreign_key="users.user_id", primary_key=True)
    course_id: int = Field(foreign_key="courses.course_id", primary_key=True)
    
    # Relationships
    student: Optional["User"] = Relationship(back_populates="student_courses")
    course: Optional["Course"] = Relationship(back_populates="student_courses")

class Lecture(SQLModel, table=True):
    __tablename__ :str= "lectures"
    
    lecture_id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.course_id")
    start_time: time
    end_time: time
    day_of_week: DayOfWeek
    room_num: Optional[int] = None
    
    # Relationships
    course: Optional["Course"] = Relationship(back_populates="lectures")
    attendance_records: List["Attendance"] = Relationship(back_populates="lecture")

class Attendance(SQLModel, table=True):
    __tablename__ :str= "attendance"
    
    lecture_id: int = Field(foreign_key="lectures.lecture_id", primary_key=True)
    student_id: int = Field(foreign_key="users.user_id", primary_key=True)
    is_present: AttendanceStatus
    
    # Relationships
    lecture: Optional["Lecture"] = Relationship(back_populates="attendance_records")
    student: Optional["User"] = Relationship(back_populates="attendance_records")
