import logging
from pythonjsonlogger import jsonlogger
from opentelemetry import trace
from src.observability.context import request_id_ctx, user_id_ctx, workflow_id_ctx
import time

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Inject standard required fields
        if not log_record.get('timestamp'):
            log_record['timestamp'] = time.time()
        
        log_record['level'] = record.levelname
        
        # OpenTelemetry Trace Context
        span = trace.get_current_span()
        if span and span.is_recording():
            log_record["trace_id"] = trace.format_trace_id(span.get_span_context().trace_id)
            log_record["span_id"] = trace.format_span_id(span.get_span_context().span_id)
        else:
            log_record["trace_id"] = None
            log_record["span_id"] = None
            
        # Context Vars
        log_record["request_id"] = request_id_ctx.get()
        log_record["user_id"] = user_id_ctx.get()
        log_record["workflow_id"] = workflow_id_ctx.get()

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logHandler = logging.StreamHandler()
        formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
        logHandler.setFormatter(formatter)
        logger.addHandler(logHandler)
    return logger

structured_logger = get_logger("careeros")
