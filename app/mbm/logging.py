import json_log_formatter


def before_send(event, hint):
    """
    Log 400 Bad Request errors with the same custom fingerprint so that we can
    group them and ignore them all together. See:
    https://github.com/getsentry/sentry-python/issues/149#issuecomment-434448781
    """
    log_record = hint.get('log_record')
    if log_record and hasattr(log_record, 'name'):
        if log_record.name == 'django.security.DisallowedHost':
            event['fingerprint'] = ['disallowed-host']
    return event

# For future logging customizations


class JSONFormatter(json_log_formatter.JSONFormatter):
    def json_record(self, message, extra, record):
        return super().json_record(message, extra, record)
