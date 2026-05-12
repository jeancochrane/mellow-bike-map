from django.http import HttpRequest, HttpResponse

import logging
import time

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware():
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        start_time = time.time()

        response: HttpResponse = self.get_response(request)

        duration = time.time() - start_time
        extra = {"duration": duration, "method": request.method,
                 "path": request.path, "status": response.status_code}

        logged_query_params = ["source", "target", "bbox"]
        for key in logged_query_params:
            value = request.GET.get(key)
            if value:
                extra[key] = value

        logger.info("response sent", extra=extra)

        return response
