from settings_object.appsettings import SettingsObject, Setting


class TsunamiSettings(SettingsObject):
    """
    Settings for the ``tsunami`` application.
    """
    #: Applications for which changes should never be recorded
    DEFAULT_BLACKLISTED_APPS = frozenset({
        'migrations',
        'contenttypes',
        'sessions',
        'admin',
        'tsunami',
    })
    #: Apps for which changes should not be recorded
    BLACKLISTED_APPS = Setting(default = lambda s: set())
    #: Specific apps for which changes should be recorded
    #: If not given, changes are recorded for all apps except those that are blacklisted
    #: If an app is in the whitelist and the blacklist, the blacklist takes precedence
    #: If a model is in a whitelisted app but the model is blacklisted, the blacklist takes precedence
    WHITELISTED_APPS = Setting(default = None)

    #: Models for which changes should never be recorded
    DEFAULT_BLACKLISTED_MODELS = frozenset({'auth.Permission'})
    #: Models for which changes should not be recorded
    BLACKLISTED_MODELS = Setting(default = lambda s: set())
    #: Specific models for which changes should be recorded
    #: If not given, changes are recorded for all models except those that are
    #: blacklisted or belong to a blacklisted app
    #: If a model is in the whitelist and the blacklist, the blacklist takes precedence
    #: If a model is in the whitelist but the app is blacklisted, the whitelist takes precedence
    WHITELISTED_MODELS = Setting(default = None)

    def default_is_tracked(self):
        def is_tracked(model):
            opts = model._meta
            # The default blacklists take precedence over everything else
            if opts.app_label in self.DEFAULT_BLACKLISTED_APPS:
                return False
            if opts.label in self.DEFAULT_BLACKLISTED_MODELS:
                return False
            # Model blacklisting overrides everything
            if opts.label in self.BLACKLISTED_MODELS:
                return False
            # If the model is whitelisted, track it
            if opts.label in (self.WHITELISTED_MODELS or []):
                return True
            # App blacklisting overrides app whitelisting
            if opts.app_label in self.BLACKLISTED_APPS:
                return False
            # If the app is whitelisted, track the model
            if opts.app_label in (self.WHITELISTED_APPS or []):
                return True
            # If we get this far, then the model will be tracked iff there are no whitelists
            return self.WHITELISTED_MODELS is None and self.WHITELISTED_APPS is None
        return is_tracked

    #: The predicate that determines if a model should be tracked
    #: The default uses the black/whitelists, but can be overridden
    IS_TRACKED_PREDICATE = Setting(default = default_is_tracked)

    # Attribute we are adding to instances to mute them
    MUTE_SIGNALS_ATTR = "_mute_signals"


app_settings = TsunamiSettings('TSUNAMI')
