import re

from matthuisman import plugin, gui, cache, userdata, signals, inputstream

from .api import API
from .constants import CHANNELS_CACHE_KEY, CONTENT_CACHE_KEY, IMAGE_URL
from .language import _

def sorted_nicely(l):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key['title'])]
    return sorted(l, key = alphanum_key)

api = API()

@signals.on(signals.BEFORE_DISPATCH)
def before_dispatch():
    api.new_session()
    plugin.logged_in = api.logged_in

@plugin.route('')
def home():
    folder = plugin.Folder()

    if not api.logged_in:
        folder.add_item(label=_(_.LOGIN, _bold=True), path=plugin.url_for(login))
    else:
        folder.add_item(label=_(_.LIVE_TV, _bold=True),  path=plugin.url_for(live_tv), cache_key=CHANNELS_CACHE_KEY)
        # folder.add_item(label=_(_.TV_SHOWS, _bold=True), path=plugin.url_for(tv_shows), cache_key=CONTENT_CACHE_KEY)
        folder.add_item(label=_(_.MOVIES, _bold=True),   path=plugin.url_for(movies), cache_key=CONTENT_CACHE_KEY)
        # folder.add_item(label=_(_.SPORTS, _bold=True),   path=plugin.url_for(sports), cache_key=CONTENT_CACHE_KEY)
        # folder.add_item(label=_(_.BOX_SETS, _bold=True), path=plugin.url_for(box_sets), cache_key=CONTENT_CACHE_KEY)

        folder.add_item(label=_.LOGOUT, path=plugin.url_for(logout))

    folder.add_item(label=_.SETTINGS, path=plugin.url_for(plugin.ROUTE_SETTINGS))

    return folder

@plugin.route()
def live_tv():
    folder = plugin.Folder(title=_.LIVE_TV)

    hidden = userdata.get('hidden', [])

    channels = sorted_nicely(api.channels().values())
    for channel in channels:
        if channel['title'] in hidden:
            continue

        folder.add_item(
            label = channel['title'],
            art   = {'thumb': channel['image']},
            path  = plugin.url_for(play_channel, is_live=True, channel=channel['title']),
            info  = {'description': channel['description']},
            playable = True,
            context = ((_.HIDE_CHANNEL, 'XBMC.RunPlugin({})'.format(plugin.url_for(hide_channel, channel=channel['title']))),)
        )

    return folder

def _filter_content(section):
    return [x for x in api.content() if x['section'] == section]

@plugin.route()
def tv_shows():
    rows = _filter_content('tvshows')
    print(len(rows))

@plugin.route()
def movies():
    folder = plugin.Folder(title=_.MOVIES)
    
    rows = _filter_content('movies')
    for row in rows:
        #if row['suspended'] or row['expiryDate'] > now():

        folder.add_item(
            label = row['title'],
            info = {'plot': row['synopsis']},
            art  = {'thumb': IMAGE_URL.format(row['images'].get('MP','')), 'fanart': IMAGE_URL.format(row['images'].get('PS',''))},
            path = plugin.url_for(play, media_id=row['mediaId']),
            playable = True,
        )

    return folder

@plugin.route()
def sports():
    rows = _filter_content('sport')
    print(len(rows))

@plugin.route()
def box_sets():
    rows = _filter_content('boxsets')
    print(len(rows))

@plugin.route()
def reset_hidden():
    userdata.delete('hidden')
    gui.notification(_.RESET_HIDDEN_OK)

@plugin.route()
def login():
    while not api.logged_in:
        username = gui.input(_.ASK_USERNAME, default=userdata.get('username', '')).strip()
        if not username:
            break

        userdata.set('username', username)

        password = gui.input(_.ASK_PASSWORD, default=cache.get('password', '')).strip()
        if not password:
            break

        cache.set('password', password, expires=60)

        try:
            api.login(username=username, password=password)
            gui.refresh()
        except Exception as e:
            gui.ok(_(_.LOGIN_ERROR, error_msg=e))

    cache.delete('password')

@plugin.route()
def logout():
    if not gui.yes_no(_.LOGOUT_YES_NO):
        return

    api.logout()
    gui.refresh()

@plugin.route()
def hide_channel(channel):
    hidden = userdata.get('hidden', [])

    if channel not in hidden:
        hidden.append(channel)

    userdata.set('hidden', hidden)
    gui.refresh()

@plugin.route()
@plugin.login_required()
def play(media_id):
    return api.play_media(media_id)

@plugin.route()
@plugin.login_required()
def play_channel(channel):
    channels = api.channels()
    channel = channels.get(channel)
    if not channel:
        raise plugin.Error(_.NO_CHANNEL)

    url = api.play_url(channel['url'])

    if not url:
        if gui.yes_no(_.NO_STREAM):
            hide_channel(channel['title'])

    elif 'faxs' in url:
        if gui.yes_no(_.ADOBE_ERROR):
            hide_channel(channel['title'])
            
    else:
        return plugin.Item(
            label = channel['title'],
            art   = {'thumb': channel['image']},
            info  = {'description': channel['description']},
            path  = url,
        )