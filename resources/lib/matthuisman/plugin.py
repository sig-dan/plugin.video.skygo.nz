import sys
import re
import shutil

from functools import wraps

import xbmc, xbmcplugin

from . import router, gui, settings, userdata, inputstream, signals
from .constants import ROUTE_SETTINGS, ROUTE_RESET, ROUTE_SERVICE, ROUTE_CLEAR_CACHE, ROUTE_IA_SETTINGS, ROUTE_IA_INSTALL, ROUTE_IA_QUALITY, ADDON_ICON, ADDON_FANART, ADDON_ID, ADDON_NAME, ROUTE_AUTOPLAY_TAG, ADDON_PROFILE
from .log import log
from .language import _
from .exceptions import PluginError

## SHORTCUTS
url_for         = router.url_for
dispatch        = router.dispatch
############

def exception(msg=''):
    raise PluginError(msg)

logged_in   = False

# @plugin.login_required()
def login_required():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not logged_in:
                raise PluginError(_.PLUGIN_LOGIN_REQUIRED)

            return f(*args, **kwargs)
        return decorated_function
    return lambda f: decorator(f)

# @plugin.route()
def route(url=None):
    def decorator(f, url):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            item = f(*args, **kwargs)

            pattern = kwargs.get(ROUTE_AUTOPLAY_TAG, '')

            if pattern and isinstance(item, Folder):
                _autoplay(item, pattern)
            elif isinstance(item, Folder):
                item.display()
            elif isinstance(item, Item):                    
                item.play()
            else:
                resolve()

        router.add(url, decorated_function)
        return decorated_function
    return lambda f: decorator(f, url)

# @plugin.merge()
def merge():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            xbmc.executebuiltin('Skin.SetString(merge,started)')

            try:
                result = f(*args, **kwargs)
            except Exception as e:
                xbmc.executebuiltin('Skin.SetString(merge,error)')
                log.exception(e)
            else:
                xbmc.executebuiltin('Skin.SetString(merge,ok)')
                return result
                
        return decorated_function
    return lambda f: decorator(f)

def resolve():
    if _handle() > 0:
        xbmcplugin.endOfDirectory(_handle(), succeeded=False, updateListing=False, cacheToDisc=False)
    
@signals.on(signals.ON_ERROR)
def _error(e):
    try:
        error = str(e)
    except:
        error = e.message.encode('utf-8')

    if not hasattr(e, 'heading') or not e.heading:
        e.heading = _(_.PLUGIN_ERROR, addon=ADDON_NAME)

    log.error(error)
    _close()

    gui.ok(error, heading=e.heading)
    resolve()

@signals.on(signals.ON_EXCEPTION)
def _exception(e):
    log.exception(e)
    _close()
    gui.exception()
    resolve()

@route('')
def _home(**kwargs):
    raise PluginError(_.PLUGIN_NO_DEFAULT_ROUTE)

@route(ROUTE_IA_QUALITY)
def _ia_quality(**kwargs):
    inputstream.set_quality()

@route(ROUTE_IA_SETTINGS)
def _ia_settings(**kwargs):
    _close()
    inputstream.open_settings()

@route(ROUTE_IA_INSTALL)
def _ia_install(**kwargs):
    _close()
    inputstream.install_widevine(reinstall=True)

def reboot():
    _close()
    xbmc.executebuiltin('Reboot')

@signals.on(signals.AFTER_DISPATCH)
def _close():
    signals.emit(signals.ON_CLOSE)

@route(ROUTE_SETTINGS)
def _settings(**kwargs):
    _close()
    settings.open()
    gui.refresh()

@route(ROUTE_RESET)
def _reset(**kwargs):
    if not gui.yes_no(_.PLUGIN_RESET_YES_NO):
        return

    xbmc.executeJSONRPC('{{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{{"addonid":"{}","enabled":false}}}}'.format(ADDON_ID))

    _close()
    userdata.clear()
    shutil.rmtree(ADDON_PROFILE)

    xbmc.executeJSONRPC('{{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{{"addonid":"{}","enabled":true}}}}'.format(ADDON_ID))

    gui.notification(_.PLUGIN_RESET_OK)
    signals.emit(signals.AFTER_RESET)
    gui.refresh()

@route(ROUTE_SERVICE)
def _service(**kwargs):
    try:
        signals.emit(signals.ON_SERVICE)
    except Exception as e:
        #catch all errors so dispatch doesn't show error
        log.exception(e)

def _handle():
    try:
        return int(sys.argv[1])
    except:
        return -1

def _autoplay(folder, pattern):
    if '#' in pattern:
        pattern, count = pattern.split('#')
        num = int(count)
    else:
        num = 1

    log.debug('Auto playing #{} list item that matches: {}'.format(num, pattern))

    count = 0
    for item in folder.items:
        if not item or not item.label or not item.playable:
            continue

        if re.search(pattern, item.label, re.IGNORECASE):
            count += 1
            log.debug('#{} Match: {}'.format(count, item.label))
            if count == num:
                router.redirect(item.path)

    raise PluginError(_(_.NO_AUTOPLAY_FOUND, pattern=pattern))

#Plugin.Item()
class Item(gui.Item):
    def __init__(self, cache_key=None, *args, **kwargs):
        super(Item, self).__init__(self, *args, **kwargs)
        self.cache_key = cache_key

    def get_li(self):
        if settings.getBool('use_cache', True) and self.cache_key:
            url = url_for(ROUTE_CLEAR_CACHE, key=self.cache_key)
            self.context.append((_.PLUGIN_CONTEXT_CLEAR_CACHE, 'XBMC.RunPlugin({})'.format(url)))

        return super(Item, self).get_li()

    def play(self):
        li = self.get_li()
        handle = _handle()

        if handle > 0:
            xbmcplugin.setResolvedUrl(handle, True, li)
        else:
            xbmc.Player().play(li.getPath(), li)

#Plugin.Folder()
class Folder(object):
    def __init__(self, items=None, title=None, content='videos', updateListing=False, cacheToDisc=True, sort_methods=None, thunb=None, fanart=None, no_items_label=_.NO_ITEMS):
        self.items = items or []
        self.title = title
        self.content = content
        self.updateListing = updateListing
        self.cacheToDisc = cacheToDisc
        self.sort_methods = sort_methods or [xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_LABEL, xbmcplugin.SORT_METHOD_DATEADDED]
        self.thunb = thunb or ADDON_ICON
        self.fanart = fanart or ADDON_FANART
        self.no_items_label = no_items_label

    def display(self):
        handle = _handle()
        items  = [i for i in self.items if i]

        if not items and self.no_items_label:
            items.append(Item(
                label = _(self.no_items_label, _label=True), 
                is_folder = False,
            ))

        for item in items:
            item.art['thumb'] = item.art.get('thumb') or self.thunb
            item.art['fanart'] = item.art.get('fanart') or self.fanart

            li = item.get_li()
            xbmcplugin.addDirectoryItem(handle, li.getPath(), li, item.is_folder)

        if self.content: xbmcplugin.setContent(handle, self.content)
        if self.title: xbmcplugin.setPluginCategory(handle, self.title)

        for sort_method in self.sort_methods:
            xbmcplugin.addSortMethod(handle, sort_method)

        xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=self.updateListing, cacheToDisc=self.cacheToDisc)

    def add_item(self, *args, **kwargs):
        position = kwargs.pop('_position', None)
        
        item = Item(*args, **kwargs)
        
        if position == None:
            self.items.append(item)
        else:
            self.items.insert(int(position), item)

        return item

    def add_items(self, items):
        self.items.extend(items)