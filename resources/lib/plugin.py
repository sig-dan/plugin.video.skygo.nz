from matthuisman import plugin, gui, userdata, signals, inputstream
from matthuisman.exceptions import Error
from matthuisman.constants import ADDON_ID

from .api import API
from .constants import IMAGE_URL, PASSWORD_KEY, HEADERS
from .language import _

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
        folder.add_item(label=_(_.LIVE_TV, _bold=True),  path=plugin.url_for(live_tv))
        folder.add_item(label=_(_.TV_SHOWS, _bold=True), path=plugin.url_for(tv_shows))
        folder.add_item(label=_(_.MOVIES, _bold=True),   path=plugin.url_for(movies))
        folder.add_item(label=_(_.SPORTS, _bold=True),   path=plugin.url_for(sports))
        folder.add_item(label=_(_.BOX_SETS, _bold=True), path=plugin.url_for(box_sets))

        folder.add_item(label=_.LOGOUT, path=plugin.url_for(logout))

    folder.add_item(label=_.SETTINGS, path=plugin.url_for(plugin.ROUTE_SETTINGS))

    return folder

@plugin.route()
def live_tv():
    folder = plugin.Folder(title=_.LIVE_TV)

    hidden = userdata.get('hidden', [])

    for channel in api.channels().values():
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

@plugin.route()
def tv_shows():
    folder = plugin.Folder(title=_.TV_SHOWS)
    folder.add_items(_shows('tvshows'))
    return folder

@plugin.route()
def sports():
    folder = plugin.Folder(title=_.SPORTS)
    folder.add_items(_shows('sport'))
    return folder

@plugin.route()
def box_sets():
    folder = plugin.Folder(title=_.BOX_SETS)
    folder.add_items(_shows('boxsets'))
    return folder

def _shows(section):
    items = []

    for row in api.content().values():
        if row['section'] != section or row['suspended']:
            continue

        item = plugin.Item(
            label = row['title'],
            info  = {
                'tvshowtitle': row.get('seriesTitle', row['title']),
                'mediatype': 'tvshow',
            },
            art   = {'thumb': IMAGE_URL.format(row['images'].get('MP',''))},
            path  = plugin.url_for(show, show_id=row['id']),
        )

        items.append(item)

    return items

@plugin.route()
def movies():
    folder = plugin.Folder(title=_.MOVIES)
    
    for row in api.content().values():
        if row['section'] != 'movies' or row['suspended']:
            continue

        folder.add_item(
            label = row['title'],
            info = {
                'plot': row['synopsis'],
                'duration': int(row.get('duration', '0 mins').strip(' mins')) * 60,
                'mediatype': 'movie',
            },
            art  = {'thumb': IMAGE_URL.format(row['images'].get('MP',''))},
            path = plugin.url_for(play, media_id=row['mediaId']),
            playable = True,
        )

    return folder

@plugin.route()
def show(show_id):
    show = api.content()[show_id]
    folder = plugin.Folder(title=show['title'])
    
    for row in sorted(show.get('subContent', []), key=lambda x: x.get('episodeNumber', x['episodeTitle'])):
        if row['suspended']:
            continue

        folder.add_item(
            label = _(_.EPISODE_LABEL, title=row['episodeTitle'], episode=row.get('episodeNumber')),
            info  = {
                'tvshowtitle': show.get('seriesTitle', show['title']),
                'plot': row.get('episodeSynopsis'),
                'duration': int(row.get('duration', '0 mins').strip(' mins')) * 60,
                'season': int(row.get('seasonNumber', 0)),
                'episode': int(row.get('episodeNumber', 0)),
                'mediatype': 'episode',
            },
            art   = {'thumb': IMAGE_URL.format(show['images'].get('MP',''))},
            path  = plugin.url_for(play, media_id=row['mediaId']),
            playable = True,
        )

    return folder

@plugin.route()
def reset_hidden():
    userdata.delete('hidden')
    gui.notification(_.RESET_HIDDEN_OK)

@plugin.route()
def login():
    username = gui.input(_.ASK_USERNAME, default=userdata.get('username', '')).strip()
    if not username:
        return

    userdata.set('username', username)

    password = gui.input(_.ASK_PASSWORD, hide_input=True).strip()
    if not password:
        return

    api.login(username=username, password=password)

    if gui.yes_no(_.STORE_PASSWORD, heading=_.STORE_PASSWORD_HEADING):
        userdata.set(PASSWORD_KEY, password)

    gui.refresh()

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
    return api.play_channel(channel)