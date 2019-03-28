from resources.lib.api import API

api = API()
api.new_session()

def playlist():
    return 'test {}'.format(api.logged_in)

def epg():
    return 'test2'