import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.monitoring.monitoring_worker import MonitoringWorker
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global instances
monitoring_worker = MonitoringWorker()
scheduler = AsyncIOScheduler()


async def start_scheduler():
    """Initialize and start the monitoring scheduler"""
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled in settings")
        return

    await monitoring_worker.initialize()

    # Run health checks at configured interval
    scheduler.add_job(
        monitoring_worker.monitor_all_services,
        trigger=IntervalTrigger(seconds=settings.MONITORING_INTERVAL_SECONDS),
        id="monitor_services",
        name="Monitor all active services",
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )

    scheduler.start()
    logger.info(
        f"Monitoring scheduler started - checking every {settings.MONITORING_INTERVAL_SECONDS}s"
    )


async def stop_scheduler():
    """Shutdown scheduler gracefully"""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Monitoring scheduler stopped")

    await monitoring_worker.shutdown()
