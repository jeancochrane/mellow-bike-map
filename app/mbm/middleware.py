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

        logged_query_params = ["source", "target", "showBbox", "sourceAddress",
                               "targetAddress", "sourceCoordinates", "targetCoordinates"]

        for key in logged_query_params:
            value = request.GET.get(key)
            if value:
                extra[key] = value

        logger.info("mbm.response_sent", extra=extra)

        return response


class MapEditorReferrerPolicyMiddleware:
    """
    Relax the Referrer-Policy header only on map editor pages, which need to
    send the Referer header in order to comply with the OSM tile server usage
    policy. For more info, see: https://osm.wiki/blocked
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response: HttpResponse = self.get_response(request)

        # Shared URL name prefix for pages that load OSM tiles via the Leaflet
        # widget. OSM requires a Referer on tile requests, but Django's default
        # Referrer-Policy ('same-origin') strips it for cross-origin requests,
        # so we need to make sure we send it
        map_editor_url_name_prefix = 'mellow-route-'
        map_editor_referer_policy = 'strict-origin-when-cross-origin'

        # resolver_match is populated once the request has been routed, so
        # it will be available here as long as this middleware continues to
        # take place after URL resolving
        match = request.resolver_match
        if match and (match.url_name or '').startswith(map_editor_url_name_prefix):
            response['Referrer-Policy'] = map_editor_referer_policy

        return response
