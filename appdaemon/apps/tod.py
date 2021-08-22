import datetime
import appdaemon.plugins.hass.hassapi as hass


# noinspection PyAttributeOutsideInit
class Tod(hass.Hass):

    def initialize(self):
        self.log("initializing ...")
        try:
            self.log(f'args: {self.args}')
            # required args
            self._night_input = self.args['night_input']
            self._tod_input = self.args['tod_input']
            self._mode = self.args['mode_input']
            # optional args
            self._morning_start = self.args.get('morning_start', self.rpltime(hour=4))
            self._day_start = self.args.get('day_start', self.rpltime(hour=8))
            self._evening_start = self.args.get('evening_start', self.rpltime(hour=20, minute=30))
            # handlers
            self._tod_handle = self.listen_state(self.mode_cb, self._tod_input, new='on', old='off')
            self._night_handle = self.listen_state(self.night_cb, self._night_input, new='on')
            self._morning_handle = None
            self._day_handle = None
            self._evening_handle = None
            # last registered goodnight
            self._night_trigger_time = None
            self.create_task(self.create_tasks())
        except (TypeError, ValueError) as e:
            self.log('Incomplete configuration', level="ERROR")
            raise e

    async def create_tasks(self, **kwargs):
        self.log(f'creating tasks')
        await self.create_task(self.mode_cb_run(tod=self._morning_start, mode='morning'))
        await self.create_task(self.mode_cb_run(tod=self._day_start, mode='day'))
        await self.create_task(self.mode_cb_run(tod=self._evening_start, mode='evening'))

    async def mode_cb(self, entity, attribute, old, new, kwargs):
        await self.create_tasks()
        # self._morning_handle = self.run_at(self.morning_cb, self.morning_start_time())
        # self._day_handle = self.run_at(self.day_cb, self.day_start_time())
        # self._evening_handle = self.run_at(self.evening_cb, self.evening_start_time())

    async def mode_cb_run(self, **kwargs):
        tod = kwargs['tod']
        mode = kwargs['mode']
        start_time = await self.start_tod(tod=tod, mode=mode)
        now = datetime.datetime.now()
        start_time = datetime.datetime.combine(now, start_time)
        if start_time < now:
            start_time = start_time.replace(day=start_time.day+1)
        diff = start_time.timestamp() - now.timestamp()
        log_str = f'dt: {str(start_time)}, mode: {mode}, diff: {str(diff)}'
        self.log(log_str, log='test_log')
        self.log(log_str)
        await self.sleep(diff)
        await self.tod_cb(mode=mode)
        self.log(f'MODE_CHANGED to {mode}', log='test_log')

    async def tod_cb(self, **kwargs):
        self.set_state(self._mode, state=kwargs['mode'])

    async def start_tod(self, **kwargs) -> datetime.time:
        res = None
        tod = kwargs['tod']
        mode = kwargs['mode']
        if mode == 'morning':
            res = await self.start_morning(tod)
        elif mode == 'day':
            res = await self.start_day(tod)
        elif mode == 'evening':
            res = await self.start_evening(tod)
        return res

    async def start_morning(self, tod) -> datetime.time:
        res = self.format_t(tod)
        return res

    async def start_day(self, tod):
        end_time = await self.sunrise(True)
        end_time = self.format_t(end_time.time())
        limit = self.format_t(tod)
        res = None
        if limit > end_time:
            res = end_time
        else:
            res = limit

        return res

    async def start_evening(self, tod):
        end_time = await self.sunset(True)
        end_time = self.format_t(end_time.time())
        limit = self.format_t(tod)
        res = None
        if limit < end_time:
            res = end_time
        else:
            res = limit
        return res

    def night_cb(self, kwargs):
        self.set_state(self._mode, state='night')
        self.log(f'MODE_CHANGED to night', log='test_log')
        self._night_trigger_time = datetime.datetime.now()

    def format_t(self, t) -> datetime.time:
        t = str(t).split('.')[0]
        res = datetime.datetime.strptime(t, '%H:%M:%S').time()
        return res

    def rpltime(self, **kwargs):
        t = datetime.time()
        hour = kwargs.get('hour')
        minute = kwargs.get('minute')
        if hour:
            t = t.replace(hour=hour)
        if minute:
            t = t.replace(minute=minute)
        return t
