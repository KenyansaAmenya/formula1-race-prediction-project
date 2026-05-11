import logging
import sys
import traceback
from typing import Any, Dict, Optional
from datetime import datetime, timezone
import json

import structlog
from structlog.processors import JSONRenderer, TimeStamper
from structlog.stdlib import LoggerFactory, add_log_level

# Masking fields to prevent data leaks
class SensitiveDataMasker:
    SENSITIVE_KEYS = {
        'password', 'secret', 'token', 'api_key', 'db_password',
        'credentials', 'auth', 'private_key', 'connection_string'
    }
    
    @classmethod
    def mask_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return data
            
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in cls.SENSITIVE_KEYS):
                masked[key] = '***MASKED***'
            elif isinstance(value, dict):
                masked[key] = cls.mask_dict(value)
            elif isinstance(value, list):
                masked[key] = [
                    cls.mask_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value
        return masked


def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    service_name: str = "f1-data-platform"
) -> structlog.BoundLogger:

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    
    # Configure structlog processors
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        TimeStamper(fmt="iso", utc=True),
    ]
    
    if format_type == "json":
        processors = shared_processors + [JSONRenderer()]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    logger = structlog.get_logger(service_name)
    logger.info(
        "logging_initialized",
        level=level,
        format=format_type,
        service=service_name,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    return logger

#Get a module-specific logger instance
def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


class PipelineMetrics:
    
    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.start_time: Optional[datetime] = None
        self.records_processed = 0
        self.records_failed = 0
        self.errors: list = []
    
    def start(self) -> None:
        self.start_time = datetime.now(timezone.utc)
    
    def record_success(self, count: int = 1) -> None:
        self.records_processed += count
    
    def record_failure(self, error: Exception, context: Optional[Dict] = None) -> None:
        self.records_failed += 1
        self.errors.append({
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': SensitiveDataMasker.mask_dict(context or {}),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    def finalize(self) -> Dict[str, Any]:
        end_time = datetime.now(timezone.utc)
        duration = (
            (end_time - self.start_time).total_seconds()
            if self.start_time else 0
        )
        
        metrics = {
            'pipeline_name': self.pipeline_name,
            'status': 'completed' if not self.errors else 'failed',
            'duration_seconds': duration,
            'records_processed': self.records_processed,
            'records_failed': self.records_failed,
            'success_rate': (
                self.records_processed / (self.records_processed + self.records_failed)
                if (self.records_processed + self.records_failed) > 0 else 0
            ),
            'errors': self.errors[:10],  # Limit error detail
            'timestamp': end_time.isoformat()
        }
        
        logger = get_logger(__name__)
        logger.info("pipeline_metrics", **SensitiveDataMasker.mask_dict(metrics))
        
        return metrics