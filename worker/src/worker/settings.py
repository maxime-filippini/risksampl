from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from worker.constants import TZ_NAME


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = ""
    TESTING: bool = True

    def model_post_init(self, context: Any) -> None:
        self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)

        if self.TESTING:
            self._trigger = IntervalTrigger(seconds=10)
            return

        self._trigger = CronTrigger(hour=12, minute=0, timezone=TZ_NAME)


settings = Settings()
