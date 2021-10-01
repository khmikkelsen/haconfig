import datetime
import warnings
import appdaemon.plugins.hass.hassapi as hass
from typing import List


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
            if self.args.get('logger'):
                self.logger = self.get_user_log(self.args['logger'])
            self._scene_morning = args.get('scene_morning')
            self._scene_day = args.get('scene_day')
            self._scene_evening = args.get('scene_evening')
            self._scene_night = args.get('scene_night')
            self.blocker = args.get('blocker', None)
            self._min_lx = args.get('min_lx', 55)
            self._wait_morning = args.get('wait_morning', 600)
            self._wait_day = args.get('wait_day', 2400)
            self._wait_evening = args.get('wait_evening', 1500)
            self._wait_night = args.get('wait_night', 60)
            self.off_transition = args.get('off_transition', 15.0)
            self.on_transition = args.get('on_transition', 0.7)
            self._offset_evening = args.get('offset_evening', '15:00')
            self._offset_morning = args.get('offset_morning', '0')
            # handlers
            self._motion_run_handle = None
            self._motion_off_run_handle = None
            self._mode_changed_handle = None
            self._motion_off_listener = None
            self._motion_listener = self.motion_listener
            self._mode_changed_listener = self.mode_changed_listener
            # vars
            self._last_trigger_ts = None

        except (TypeError, ValueError) as e:
            self.log('Incomplete configuration', level="ERROR")
            raise e

    async def motion(self, entity, attribute, old, new, kwargs):
        lx = await self.get_luminosity()
        self._last_trigger_ts = await self.get_now_ts()
        if lx <= await self.min_lx():
            self.reset_motion_handle()
            self._motion_run_handle = await self.create_task(self.motion_run())

    async def motion_run(self, **kwargs):
        if await self.is_local_control():
            supported_colors = await self.get_state(self.light_group, attribute='supported_color_modes')
            mode = await self.get_mode()
            state = await self.get_state(self.light_group)
            if state == 'off':
                if supported_colors == ['onoff']:
                    await self.turn_on(self.light_group)
                else:
                    await self.turn_on(getattr(self, f'scene_{mode}'), transition=self.on_transition)
            self._motion_off_listener = self.motion_listener_off
            
    async def motion_off(self, entity, attribute, old, new, kwargs):
        self._motion_off_run_handle = await self.create_task(self.motion_off_run())

    async def motion_off_run(self, **kwargs):
        mode = await self.get_mode()
        wait = kwargs.get('wait', getattr(self, f'wait_{mode}'))
        await self.sleep(wait)
        self.log(f'finished waiting {wait} in {mode}')
        if await self.is_local_control():
            await self.turn_off(self.light_group, transition=self.off_transition)
        await self.cancel_listen_state(self._motion_off_listener)

    async def get_luminosity(self):
        return float(await self.get_state(self.lx_sensor))

    async def min_lx(self) -> float:
        if isinstance(self._min_lx, int):
            return float(self._min_lx)
        elif isinstance(self._min_lx, str):
            return float(await self.get_state(self._min_lx))
        else:
            return self._min_lx

    async def mode_changed_cb(self, entity, attribute, old, new, kwargs):
        self._mode_changed_handle = await self.create_task(self.mode_changed_task())

    async def mode_changed_task(self, **kwargs):
        mode = await self.get_mode()
        scene = getattr(self, f'scene_{mode}')
        lights_state = await self.get_state(self.light_group)
        if lights_state == 'on' and mode != 'night':
            try:
                self.log(f'mode_changed to scene: {scene}')
                await self.turn_on(self.blocker)
                limit = getattr(self, f'wait_{mode}')
                await self.turn_on(scene, transition=1200 if 1200 < limit else limit)
                # test env
                # await self.turn_on(scene, transition=15)
                await self.sleep(1201)
                await self.turn_off(self.blocker)
                self._motion_run_handle = await self.create_task(self.motion_run(wait=await self.remainder()))
            except (Exception, BaseException) as e:
                raise e

    async def remainder(self):
        try:
            wait = getattr(self, f"wait_{await self.get_state(self.mode_input)}")
            diff = await self.get_now_ts() - self._last_trigger_ts
            remainder = wait - diff if wait - diff < wait else 0
            self.log(f'wait:{wait} - diff:{diff} = {remainder}')
        except (Exception, BaseException) as e:
            remainder = 0
            self.log(e)
        return remainder

    async def is_local_control(self):
        return (self.blocker and await self.get_state(self.blocker) == 'off') or self.blocker is None

    async def get_mode(self):
        return await self.get_state(self.mode_input)

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

    @property
    def wait_morning(self):
        return int(self._wait_morning)

    @property
    def wait_day(self):
        return int(self._wait_day)

    @property
    def wait_evening(self):
        return int(self._wait_evening)

    @property
    def wait_night(self):
        return int(self._wait_night)
        

    @property
    def motion_listener(self):
        return self.listen_state(self.motion, self.motion_sensor, new='on', old='off')

    @property
    def motion_listener_off(self):
        return self.listen_state(self.motion_off, self.motion_sensor, new='off', old='on', oneshot=True)

    @property
    def mode_changed_listener(self):
        return self.listen_state(self.mode_changed_cb, self.mode_input)

    @property
    def external_control_on_listener(self):
        return self.listen_event(
            self.external_control_on_event, 
            'call_service', 
            domain='light', 
            service='turn_on')

    @property
    def external_control_off_listener(self):
        return self.listen_event(
            self.external_control_off_event,
            'call_service',
            domain='light',
            service='turn_off')
        
    def event_contains_lights(self, data):
        try:
            entity_id = data['service_data']['entity_id'] 
            return entity_id in self.get_lights or entity_id == self.get_lights
        except Exception:
            return False

    async def external_control_off_event(self, event_name, data, kwargs):
        if self.event_contains_lights(data):
            await self.cancel_listen_state(self._motion_listener)
            self._motion_listener = self.motion_listener
            self.log(f'External control turned off')
            await self.turn_off(self.blocker)

    async def external_control_on_event(self, event_name, data, kwargs):
        if self.event_contains_lights(data):
            await self.cancel_listen_state(self._motion_listener)
            self._motion_listener = self.motion_listener
            self.log(f'External control turned on')
            await self.turn_on(self.blocker)

    @property
    def get_lights(self) -> List[str]:
        return self.get_state(self.light_group, attribute='entity_id')

    def reset_motion_handle(self):
        if self._motion_run_handle:
            if not self._motion_run_handle.done():
                self._motion_run_handle.cancel()
        if self._motion_off_run_handle:
            if not self._motion_off_run_handle.done():
                self._motion_off_run_handle.cancel()

    def reset_mode_changed_handle(self):
        if self._mode_changed_handle:
            if not self._mode_changed_handle.done():
                self._mode_changed_handle.cancel()

    def ad_api_all_apps(self):
        objs = self.get_ad_api().AD.app_management.objects
        self.log(objs)
