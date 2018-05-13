import logging
import requests
import time

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, PreferencesEvent, PreferencesUpdateEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction
from ulauncher.api.shared.action.OpenUrlAction import OpenUrlAction
logging.basicConfig()
logger = logging.getLogger(__name__)

class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        items = extension.get_items(event.get_argument())
        return RenderResultListAction(items)

class PreferencesEventListener(EventListener):
    def on_event(self, event, extension):
        extension.set_pref(event.preferences)

class PreferencesUpdateEventListener(EventListener):
    def on_event(self, event, extension):
        extension.set_pref({ event.id: event.new_value })

class Cacher(Extension):
    matches_len = 0

    def __init__(self):
        self.headers = {}
        super(Cacher, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(PreferencesEvent, PreferencesEventListener())
        self.subscribe(PreferencesUpdateEvent, PreferencesUpdateEventListener())

    def set_pref(self, pref):
        self.cache_max = 3600
        self.cache_start = time.time()
        self.data = None
        self.preferences = pref
        self.headers['X-Api-Key'] = self.preferences['api_key'] if 'api_key' in self.preferences else self.headers['X-Api-Key']
        self.headers['X-Api-Token'] = self.preferences['api_token'] if 'api_token' in self.preferences else self.headers['X-Api-Token']

        if not self.headers['X-Api-Key'] or not self.headers['X-Api-Token']:
            logger.error('Credentials not found!')

    @staticmethod
    def get_labels(label, guid):
        lbs = []
        for i in range(0, len(label)):
            for j in range(0, len(label[i]['snippets'])):
                if label[i]['snippets'][j]['guid'] == guid:
                    lbs.append('(' + label[i]['title'] + ') ')
                    break
        return lbs

    def find_rec(self, data, query, matches):

        for i in range(0, len(data)):

            if len(data[i]['files']) > 0:

                if self.matches_len >= 10:
                    return matches

                res_tit = data[i]['title'].lower().find(query, 0, len(data[i]['title']))
                res_desc = data[i]['description'].lower().find(query, 0, len(data[i]['description']))

                if res_tit != -1 or res_desc != -1:
                    matches.append({'guid': data[i]['guid'],
                                    'title': data[i]['title'].encode('utf8'),
                                    'data': data[i]['files'][0]['content'].encode('utf8'),
                                    'file': data[i]['files'][0]['filename'].encode('utf8')})
                    self.matches_len += 1
                    continue

                for j in range(0, len(data[i]['files'])):

                    res_cont = data[i]['files'][j]['content'].lower().find(query, 0,
                                                                           len(data[i]['files'][j]['content']))
                    res_file = data[i]['files'][j]['filename'].lower().find(query, 0,
                                                                            len(data[i]['files'][j]['filename']))

                    if res_cont != -1 or res_file != -1:
                        matches.append({'guid': data[i]['guid'],
                                        'title': data[i]['title'].encode('utf8'),
                                        'data': data[i]['files'][j]['content'].encode('utf8'),
                                        'file': data[i]['files'][j]['filename'].encode('utf8')})
                        self.matches_len += 1

        return matches

    def get_items(self, query):

        items = []

        # Handle credentials error
        if not self.headers['X-Api-Key'] or not self.headers['X-Api-Token']:
            items.append(ExtensionResultItem(icon='images/cacher.png',
                                 name='Credentials not found!',
                                 description='Press Enter to go straight to cacher.io',
                                 on_enter=OpenUrlAction('https://app.cacher.io')))
            return items

        if self.data is None or (time.time() - self.cache_start) > self.cache_max:
            response = requests.get('https://api.cacher.io/integrations/show_all', headers=self.headers)
            self.data = response.json()

            # Handle API error
            if 'status' in self.data and self.data['status'] == 'error':
                logger.error(self.data['message'])
                items.append(ExtensionResultItem(icon='images/cacher.png',
                                     name='An error just occured!',
                                     description='Error content: ' + self.data['message']))
                return items

        matches = []
        self.matches_len = 0

        if query is None:
            query = ''

        matches = self.find_rec(self.data['personalLibrary']['snippets'], query, matches)

        for i in range(0, self.matches_len):
            labels = self.get_labels(self.data['personalLibrary']['labels'], matches[i]['guid'])
            items.append(ExtensionResultItem(icon='images/cacher.png',
                                             name='%s' % matches[i]['title'],
                                             description='%s' % matches[i]['file'] + ' ' + ''.join(labels),
                                             on_enter=CopyToClipboardAction(matches[i]['data'])))

        return items
