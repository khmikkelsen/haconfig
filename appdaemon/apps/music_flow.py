from re import search
import appdaemon.plugins.hass.hassapi as hass
import json
from ytmusicapi import YTMusic


YTM_APPINFO = 'com.google.android.apps.youtube.music'
YTM_PLAYER = 'media_player.ytube_music_player'


# noinspection PyAttributeOutsideInit
class MusicFlow(hass.Hass):

    def initialize(self):
        self.log("initializing ...")
        try:
            self.last_song = None
            self.song_uri = None
            self.logger = self.get_user_log('test_log')
            self.notification_sensor = self.args['last_notification_sensor']
            self.tracker = self.args['device_tracker']
            self.trigger_play_sensor = self.args['contact_sensor']
            self.speakers = self.args['speakers']
            self.default_playlist = self.args['default_playlist_id']
            self.ytm = YTMusic()

            self.home_handle = self.listen_state(self.entered_home_zone_cb, self.tracker, new='home', old='not_home')
            self.noti_handle = self.listen_state(self.new_notification_cb, self.notification_sensor, attribute='all', immediate=True)
            self.content_id = None
            self.play_handle = None
            self.default_handle = None
            self.log('MusicFlow initiated', log='main_log')
            
        except (TypeError, ValueError) as e:
            self.log('Incomplete configuration', level="ERROR")
            raise e

    def new_notification_cb(self, entity, attribute, old, new, kwargs):
        attrs = self.get_state(entity, attribute=attribute).get('attributes')
        if appinfo := attrs.get('android.appInfo'):
            if search(YTM_APPINFO, appinfo):
                self.last_song = (
                    attrs['android.title'], 
                    attrs['android.text'],
                    attrs['post_time'])
                self.content_id = self.get_content_id()
                self.log(self.last_song, self.content_id)

    def entered_home_zone_cb(self, entity, attribute, old, new, kwargs):
        if self.is_alone():
            self.prepare_speakers()
            self.play_handle = self.listen_state(
                self.start_playing_cb,
                entity=self.trigger_play_sensor,
                new="on",
                old='off',
                oneshot=True)

    def start_playing_cb(self, entity, attribute, old, new, kwargs):
        self.call_service("media_player/play_media",
                          entity_id=YTM_PLAYER,
                          media_content_id=self.content_id,
                          media_content_type='track')
        diff = round(self.get_now_ts() - self.last_song[2] / 1000)
        self.log(f'diff: {diff}')
        self.call_service("media_player/media_seek",
                          entity_id=YTM_PLAYER,
                          seek_position=diff)
        self.cancel_listen_state(self.play_handle)
        self.default_handle = self.listen_state(
            self.to_default_playlist_cb,
            entity=self.speakers,
            to='idle',
            oneshot=True)

    def to_default_playlist_cb(self, entity, attribute, old, new, kwargs):
        self.call_service("media_player/play_media",
                          entity_id=YTM_PLAYER,
                          media_content_id=self.default_playlist,
                          media_content_type='playlist')
        self.cancel_listen_state(self.default_handle)

    def prepare_speakers(self):
        self.call_service("media_player/select_source",
                          source=self.speakers,
                          entity_id=YTM_PLAYER)

    def is_alone(self, **kwargs):
        alone = False
        trackers = self.get_trackers()
        for tracker in trackers:
            if tracker != self.tracker:
                state = self.get_state(tracker)
                self.log(f'external trackers: {str(tracker)}, state: {state}')
                alone = (state == 'home') or alone
        self.log(f'is alone: {(not alone)}')
        return (not alone)

    @property
    def song_query(self): 
        return f'{self.last_song[0]} - {self.last_song[1]}'

    def get_content_id(self):
        ans = self.ytm.search(self.song_query, filter='songs', limit=1)
        self.log(f'len: {len(ans)}, result: {str(ans[0]["title"])}')
        return ans[0]['videoId']
