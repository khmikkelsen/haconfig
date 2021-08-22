import warnings
import appdaemon.plugins.hass.hassapi as hass


# noinspection PyAttributeOutsideInit
class Motion(hass.Hass):

    def initialize(self):
        self.log("initializing ...")
        warnings.filterwarnings("error")
        try:
            args = self.args
            self.log(f'args: {self.args}')
            # required args
            self.motion_sensor = args['motion_sensor']
            self.lx_sensor = args['lx_sensor']
            self.light_group = args['light_group']
            self.mode_input = args['mode_input']
            # optional args
            self._scene_morning = args.get('scene_morning')
            self._scene_day = args.get('scene_day')
            self._scene_evening = args.get('scene_evening')
            self._scene_night = args.get('scene_night')
            self.blocker = args.get('blocker', None)
            self._min_lx = args.get('min_lx', 55)
            self.wait_morning = args.get('wait_morning', 600)
            self.wait_day = args.get('wait_day', 2400)
            self.wait_evening = args.get('wait_evening', 1500)
            self.wait_night = args.get('wait_night', 60)
            self.off_transition = args.get('off_transition', 15.0)
            self.on_transition = args.get('on_transition', 0.7)
            # handler from last trigger
            self._handle = None
            self._last_trigger_time = None
            self._mode_changed_handler = self.listen_state(self.mode_changed_cb, self.mode_input)
            self._motion_handler = self.listen_state(self.motion, self.motion_sensor, new='on')

        except (TypeError, ValueError) as e:
            self.log('Incomplete configuration', level="ERROR")
            raise e

    async def motion(self, entity, attribute, old, new, kwargs):
        lx = await self.get_luminosity()
        if lx <= await self.min_lx():
            self.reset_handle()
            self._handle = await self.create_task(self.motion_run())

    async def motion_run(self, **kwargs):
        if await self.is_local_control():
            supported_colors = await self.get_state(self.light_group, attribute='supported_color_modes')
            mode = await self.get_mode()
            wait = kwargs.get('wait', getattr(self, f'wait_{mode}'))
            if supported_colors == ['onoff']:
                await self.turn_on(self.light_group)
            else:
                await self.turn_on(getattr(self, f'scene_{mode}'), transition=self.on_transition)
            self._last_trigger_time = await self.get_now_ts()
            await self.sleep(wait)
            if await self.is_local_control():
                await self.turn_off(self.light_group, transition=self.off_transition)

    async def get_mode(self):
        return await self.get_state(self.mode_input)

    async def get_luminosity(self):
        return float(await self.get_state(self.lx_sensor))

    async def min_lx(self) -> float:
        if isinstance(self._min_lx, int):
            return float(self._min_lx)
        elif isinstance(self._min_lx, str):
            return float(await self.get_state(self._min_lx))
        else:
            return self._min_lx

    async def is_local_control(self):
        return (self.blocker and await self.get_state(self.blocker) == 'off') or self.blocker is None

    async def mode_changed_cb(self, entity, attribute, old, new, kwargs):
        scene = getattr(self, f'scene_{new}')
        lights_state = await self.get_state(self.light_group)
        if lights_state == 'on':
            await self.turn_on(self.blocker)
            await self.turn_on(scene, transition=120)
            await self.sleep(121)
            await self.turn_off(self.blocker)
            await self.sleep(1)
            diff = getattr(self, f"wait_{new}") - await self.get_now_ts() - self._last_trigger_time 
            await self.motion_run(wait=diff)

    @property
    def scene_morning(self):
        if self._scene_morning:
            return self._scene_morning
        else:
            return self.light_group

    @property
    def scene_day(self):
        if self._scene_day:
            return self._scene_day
        else:
            return self.light_group

    @property
    def scene_evening(self):
        if self._scene_evening:
            return self._scene_evening
        else:
            return self.light_group

    @property
    def scene_night(self):
        if self._scene_night:
            return self._scene_night
        else:
            return self.light_group

    def reset_handle(self):
        if self._handle:
            if not self._handle.done():
                self._handle.cancel()

    def ad_api_all_apps(self):
        objs = self.get_ad_api().AD.app_management.objects
        self.log(objs)
