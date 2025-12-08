from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference
from contextlib import asynccontextmanager

# Handle imports for both package and standalone execution
import sys
import os

# Add the current directory to sys.path to ensure modules can be imported
# irrespective of how the script is run or if __init__.py exists
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.router import router
from database.session import create_db_tables


@asynccontextmanager
async def lifespan_handler(_app: FastAPI):
    await create_db_tables()
    yield


app = FastAPI(
    # Server start/stop listener
    lifespan=lifespan_handler,
)

app.include_router(router)

# Entry point for Railway deployment
if __name__ == "__main__":
    # Read PORT from environment variable, default 8000 for local testing
    port = int(os.getenv("PORT", 8000))
    # Run Uvicorn server
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
@app.get("/", include_in_schema=False)
def health_check():
    return {"status": "ok", "message": "Service is running"}

#scalar api documentation
@app.get("/scalar",include_in_schema=False)
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API"
    )
