from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import Union, cast

from ..api.schemas.user import UserCreate, UserRole
from ..database.models import Student, Teacher, Emb


class UserService:
    def __init__(self, session: AsyncSession):
        # Get database session to perform database operations
        self.session = session

    # Get a user by id (checks both tables)
    async def get(self, user_id: int, role: UserRole) -> Union[Student, Teacher]:
        if role == UserRole.student:
            user = await self.session.get(Student, user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            return cast(Student, user)
        else:
            user = await self.session.get(Teacher, user_id)
            if user is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            return cast(Teacher, user)

    # Add a new user based on role
    async def add(self, user_create: UserCreate) -> Union[Student, Teacher]:
        # Extract data, exclude role (tables don't have role field), but include id if provided
        user_data = user_create.model_dump(exclude={'role'}, exclude_none=False)
        
        # Check if user with the same ID already exists
        if user_data.get('id') is not None:
            user_id = user_data['id']
            if user_create.role == UserRole.student:
                existing_user = await self.session.get(Student, user_id)
            else:
                existing_user = await self.session.get(Teacher, user_id)
            
            if existing_user is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User with id {user_id} and role '{user_create.role.value}' already exists. Please use a different id."
                )
        
        # If creating a student with a project_id, validate that the project exists
        if user_create.role == UserRole.student and user_data.get('project_id') is not None:
            project_id = user_data['project_id']
            project = await self.session.get(Emb, project_id)
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Project with id {project_id} does not exist. Please create the project first using POST /project"
                )
        
        # Check role and insert into appropriate table
        if user_create.role == UserRole.student:
            new_user = Student(**user_data)
        else:  # teacher
            # Remove project_id if it's a teacher (teachers don't have projects)
            user_data.pop('project_id', None)
            new_user = Teacher(**user_data)
        
        try:
            self.session.add(new_user)
            await self.session.commit()
            await self.session.refresh(new_user)
        except Exception as e:
            await self.session.rollback()
            error_str = str(e).lower()
            
            # Check if it's a duplicate key/unique constraint violation
            if 'unique' in error_str or 'duplicate' in error_str or 'already exists' in error_str:
                user_id = user_data.get('id')
                if user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"User with id {user_id} already exists. Please use a different id."
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="A user with these details already exists."
                    )
            
            # Check if it's a foreign key constraint violation
            if 'foreign key' in error_str or 'constraint' in error_str or 'referenced' in error_str:
                project_id = user_data.get('project_id')
                if project_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Project with id {project_id} does not exist. Please create the project first using POST /project"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid foreign key reference. Please ensure the referenced record exists."
                    )
            
            # For other errors, provide detailed error message
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating user: {str(e)}"
            )

        return new_user  # type: ignore[return-value]