try:
    import prometheus_client
except ImportError:
    raise RuntimeError('prometheus_client is not installed')

from src.utils import get_logger, MemoryUsageLogger

logger = get_logger(__name__)

MEMORY_USAGE = prometheus_client.Gauge(
    name='memory_usage',
    documentation='Overall memory usage of API'
)
MEMORY_MONITORING_DAEMON = MemoryUsageLogger(memory_gauge=MEMORY_USAGE)
MEMORY_MONITORING_DAEMON.start()
logger.info("Started memory_usage monitoring daemon")

monitor_router = prometheus_client.make_asgi_app()

