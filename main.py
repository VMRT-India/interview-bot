import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import mongo
from db import redis as redis_db
from db import qdrant as qdrant_db

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(settings.log_level)
    ),
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", msg="connecting databases")
    await qdrant_db.init_collection()
    yield
    logger.info("shutdown", msg="closing connections")
    await mongo.close()
    await redis_db.close()
    await qdrant_db.close()


app = FastAPI(title="Interview Bot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routers import health  # noqa: E402
from api.routers import sessions  # noqa: E402
from api.routers import interview_ws  # noqa: E402
from api.routers import auth  # noqa: E402
from api.routers import stats  # noqa: E402

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(sessions.router, tags=["sessions"])
app.include_router(interview_ws.router, tags=["interview"])
app.include_router(stats.router, tags=["stats"])
