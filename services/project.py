from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from ..api.schemas.project import EmbCreate
from ..database.models import Emb, Student


class ProjectService:
    def __init__(self, session: AsyncSession):
        # Get database session to perform database operations
        self.session = session

    # Get project by student id
    async def get_by_student_id(self, student_id: int) -> Emb:
        # First get the student
        student = await self.session.get(Student, student_id)
        if student is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        
        # Check if student has a project
        if student.project_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student is not assigned to any project")
        
        # Get the project
        project = await self.session.get(Emb, student.project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        
        return project

    # Add a new project
    async def add(self, project_create: EmbCreate) -> Emb:
        # Check if project with the same ID already exists
        if project_create.id is not None:
            existing_project = await self.session.get(Emb, project_create.id)
            if existing_project is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Project with id {project_create.id} already exists. Please use a different id or update the existing project."
                )
        
        # Create project from request data
        project_data = project_create.model_dump(exclude_none=False)
        new_project = Emb(**project_data)
        
        try:
            self.session.add(new_project)
            await self.session.commit()
            await self.session.refresh(new_project)
        except Exception as e:
            await self.session.rollback()
            # Check if it's a unique constraint violation (in case ID is set as unique)
            error_str = str(e).lower()
            if 'unique' in error_str or 'duplicate' in error_str:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Project with id {project_create.id} already exists. Please use a different id."
                )
            # Re-raise other exceptions
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating project: {e}"
            )

        return new_project

    # Get a project by id
    async def get_by_id(self, project_id: int) -> Emb:
        project = await self.session.get(Emb, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

