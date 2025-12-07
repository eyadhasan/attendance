from pydantic import BaseModel

class CourseCreate(BaseModel):
    id: int | None = None
    name: str
    code: str
    teacher: str  # Teacher name
    teacher_id: int

class CourseGet(BaseModel):
    id: int
    name: str
    code: str
    teacher: str  # Teacher name
    teacher_id: int

