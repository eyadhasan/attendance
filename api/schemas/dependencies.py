from typing import Annotated
from fastapi import Depends

from database.session import SessionDep
from services.database_service import DatabaseService

def get_database_service(session: SessionDep):
    return DatabaseService(session)

DatabaseServiceDep = Annotated[DatabaseService, Depends(get_database_service)]