from pydantic import BaseModel
from enum import Enum
from typing import Union


class UserRole(str, Enum):
    student="student"
    teacher="teacher"

class BaseUser(BaseModel):
    name: str
    age: int
    email: str

class StudentGet(BaseUser):
    id: int
    role: UserRole = UserRole.student

class TeacherGet(BaseUser):
    id: int
    role: UserRole = UserRole.teacher

# Union type for response
UserGet = Union[StudentGet, TeacherGet]

# Separate create schemas for student and teacher
class StudentCreate(BaseUser):
    id: int | None = None
    project_id: int | None = None  # Foreign key to emb table

class TeacherCreate(BaseUser):
    id: int | None = None

# Keep UserCreate for backward compatibility (will be deprecated)
class UserCreate(BaseUser):
    role: UserRole
    id: int | None = None
    project_id: int | None = None  # Foreign key to emb table