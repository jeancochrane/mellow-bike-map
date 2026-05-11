from mbm.settings import SENTRY_RELEASE


def sentry_release(request):
    return {
        sentry_release: SENTRY_RELEASE
    }
