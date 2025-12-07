from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from sqlmodel import select

from ..api.schemas.course import CourseCreate
from ..database.models import Course


class CourseService:
    def __init__(self, session: AsyncSession):
        # Get database session to perform database operations
        self.session = session

    # Get a course by id
    async def get_by_id(self, course_id: int) -> Course:
        course = await self.session.get(Course, course_id)
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        return course

    # Search courses by teacher name
    async def get_by_teacher_name(self, teacher_name: str) -> list[Course]:
        statement = select(Course).where(Course.teacher == teacher_name)
        result = await self.session.exec(statement)
        courses = result.all()
        if not courses:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No courses found for teacher: {teacher_name}")
        return list(courses)

    # Add a new course
    async def add(self, course_create: CourseCreate) -> Course:
        # Create course from request data
        course_data = course_create.model_dump(exclude_none=False)
        new_course = Course(**course_data)
        
        self.session.add(new_course)
        await self.session.commit()
        await self.session.refresh(new_course)

        return new_course

