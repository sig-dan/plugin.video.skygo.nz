
class Error(Exception):
    def __init__(self, message, heading=None):
        super(Error, self).__init__(message)
        self.heading = heading

class InputStreamError(Error):
    pass

class PluginError(Error):
    pass

class GUIError(Error):
    pass

class RouterError(Error):
    pass