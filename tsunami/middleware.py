"""
Django middlewares for the tsunami app.
"""

from . import tracking


def user_tracking(get_response):
    """
    Middleware that enables user tracking for Tsunami events.
    """
    def middleware(request):
        # If there is an authenticated user, store it in the tracking state
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            tracking.state.user = user
        else:
            tracking.state.user = None
        # We can defer to the next middleware now
        return get_response(request)
    return middleware
