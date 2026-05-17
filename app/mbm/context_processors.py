from mbm.settings import SENTRY_RELEASE, ENABLE_SENTRY


def sentry_config(request):
    return {
        "enable_sentry": ENABLE_SENTRY,
        "sentry_release": SENTRY_RELEASE
    }
