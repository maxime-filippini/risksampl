import logging
from contextlib import asynccontextmanager

from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.events import EVENT_JOB_EXECUTED
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from worker.constants import JOB_ID
from worker.constants import LOCK_KEY
from worker.constants import TZ_NAME
from worker.database import connect
from worker.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("worker")

database_url = settings.DATABASE_URL


scheduler = AsyncIOScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(url=settings.DATABASE_URL),
    },
    job_defaults={
        "coalesce": True,  # if multiple runs were missed, run only once
        "max_instances": 1,  # never overlap this job
        "misfire_grace_time": 60 * 15,  # 15 minutes grace around restarts
    },
    timezone=TZ_NAME,
)


def acquire_leader_lock(session: Session):
    result = session.execute(text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": LOCK_KEY})
    return result.scalar()


def release_leader_lock(session: Session):
    session.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": LOCK_KEY})


def _job_listener(event):
    if event.exception:
        log.error("Job %s failed", event.job_id, exc_info=True)
    else:
        log.info("Job %s executed successfully", event.job_id)


async def test_job():
    session = connect()
    try:
        log.info("hi, this is a test!")
    finally:
        session.close()


async def do_daily_run():
    # Runs once per day; idempotent
    session = connect()
    try:
        log.info("hi, this is the daily run")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    session = connect()

    if not acquire_leader_lock(session):
        log.warning("Leader lock not acquired; this instance will be passive.")
        session.close()
        return

    log.info("Leader lock acquired; initializing scheduler.")

    # Add a listener for completed/failed jobs
    scheduler.add_listener(_job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    trigger = settings._trigger

    if scheduler.get_job(JOB_ID):
        scheduler.reschedule_job(JOB_ID, trigger=trigger)
    else:
        scheduler.add_job(do_daily_run, trigger=trigger, id=JOB_ID)

    scheduler.start()

    # keep the session open to hold the leader lock for the life of the process
    app.state.leader_session = session

    yield

    # Clean up on shutdown
    if hasattr(app.state, "leader_session"):
        release_leader_lock(app.state.leader_session)
        app.state.leader_session.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "ok": True,
        "scheduler_running": scheduler.running,
        "jobs": [j.id for j in scheduler.get_jobs()] if scheduler.running else [],
        "tz": TZ_NAME,
    }
