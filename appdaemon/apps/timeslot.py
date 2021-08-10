import datetime
import appdaemon.plugins.hass.hassapi as hass


# noinspection PyAttributeOutsideInit,PyTypeChecker,PyUnresolvedReferences
class Tod(hass.Hass):

    def initialize(self):
        self.log("initializing ...")
        try:
            self.log(f'args: {self.args}')
            # required args
            self._night_input = self.args['night_input']
            self._mode = self.args['mode_input']
            # optional args
            self._evening_start = self.args.get('evening_start', self.rpltime(hour=20, minute=30))
            self._morning_start = self.args.get('morning_start', self.rpltime(hour=4))
            self._morning_end = self.args.get('morning_end', self.rpltime(hour=8))
            # handlers
            h = self.run_in(self.mode_cb, 5)
            self._mode_handle = self.run_daily(self.mode_cb, "00:00:01")
            self._night_handle = self.listen_state(self.night_cb, self._night_input, new='on')
            self._morning_handle = None
            self._day_handle = None
            self._evening_handle = None
            # last registered goodnight
            self._night_trigger_time = None
            self.log(f'handle: {self.info_timer(h)}')
        except (TypeError, ValueError) as e:
            self.log('Incomplete configuration', level="ERROR")
            raise e

    def mode_cb(self, kwargs):
        self.log(f'entered')
        self._morning_handle = self.run_at(self.morning_cb, self.morning_start_time())
        self._day_handle = self.run_at(self.day_cb, self.day_start_time())
        self._evening_handle = self.run_at(self.evening_cb, self.evening_start_time())

    def morning_cb(self, kwargs):
        self.set_state(self._mode, state='morning')

    def day_cb(self, kwargs):
        self.set_state(self._mode, state='day')

    def evening_cb(self, kwargs):
        self.set_state(self._mode, state='evening')

    def night_cb(self, kwargs):
        self.set_state(self._mode, state='night')
        self._night_trigger_time = datetime.datetime.now()

    def morning_start_time(self):
        end_time = self.sunrise(True)
        end_time = end_time.time()
        limit = self.str2t(self._morning_start)
        res = None
        if limit < end_time:
            res = end_time
        else:
            res = limit
        self.log(f'morning: {res}')
        return res

    def day_start_time(self):
        end_time = self.sunrise(True)
        end_time = end_time.time()
        limit = self.str2t(self._morning_end)
        res = None
        if limit < end_time:
            res = end_time
        else:
            res = limit
        self.log(f'day: {res}')
        return res

    def evening_start_time(self):
        end_time = self.sunset(True) + datetime.timedelta(hours=1)
        end_time = end_time.time()
        limit = self.str2t(self._evening_start)
        res = None
        if limit < end_time:
            res = end_time
        else:
            res = limit
        self.log(f'evening: {res}')
        return res

    @staticmethod
    def str2t(string: str):
        return datetime.datetime.strptime(string, '%H:%M:%S.%f').time()

    @staticmethod
    def rpltime(**kwargs):
        t = datetime.time(microsecond=1)
        hour = kwargs.get('hour')
        minute = kwargs.get('minute')
        if hour:
            t = t.replace(hour=hour)
        if minute:
            t = t.replace(minute=minute)
        return str(t)
