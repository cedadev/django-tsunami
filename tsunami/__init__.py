from pkg_resources import get_distribution, DistributionNotFound
try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    pass

default_app_config = __name__ + '.apps.TsunamiAppConfig'
