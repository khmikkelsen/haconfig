import random
import warnings
from collections import OrderedDict

import appdaemon.plugins.hass.hassapi as hass
from typing import List

BASE_DELAY = 0.1


# noinspection PyAttributeOutsideInit
class Dimmer(hass.Hass):
    """Hue Dimmer Switch class
    args:
        light_group: light group to control
        dimmer_switch: dimmer switch to listen to
        scene_selector: Input selector to choose scene from
        party_boolean: party boolean to check if
        scene_selector: Input_select to derive scene from
        trans_max: input_number transition maximum
        trans_min: input_number transition minimum
        trans_max_step(optional): step for maximum transition time
        trans_min_step(optional): step for minimum transition time
        master (optional): if the dimmer switch is a master switch (party controls all lights)

    """

    def initialize(self):
        self.log("initializing ...")
        warnings.filterwarnings("error")
        try:
            self.log(f'args: {self.args}')
            if self.args.get('logger'):
                self.logger = self.get_user_log(self.args['logger'])
            self._dimmer = self.args['dimmer_switch']
            self._light_group = self.args['light_group']
            self.party_state = self.args['party_boolean']
            self._scene_selector = self.args['scene_selector']
            self._master = self.args.get('master', False)
            if self._master:
                self._master = True
            self.blocker = self.args.get('blocker')
            self._scenes = self.party_scenes
            self._trans_max = self.args['trans_max']
            self._trans_min = self.args['trans_min']
            self._trans_max_step = float(self.args.get('trans_max_step', 2))
            self._trans_min_step = float(self.args.get('trans_min_step', 1))
            self._party_index = 0
            self._handles = []
        except (TypeError, ValueError) as e:
            self.log('Incomplete configuration', level="ERROR")
            raise e
        self.apps = self.all_apps_of_me()
        #self.blocker_off_handler = self.listen_state(self.lights_off, self._light_group, new='off')
        #self.dimmer_handler = self.listen_state(self.dimmer_button_pressed, self._dimmer, attribute='action')
        self.scene_handler = self.listen_state(self.scene_selector_changed, self._scene_selector)

        self.hold_ts = None

        self.register_constraint('is_party')
        # dimmer actions - party off
        self.poff_on_press_h = self.listen_state(self.poff_on_press, self._dimmer, attribute='action', new='on_press', is_party='off')
        self.poff_up_press_h = self.listen_state(self.poff_up_press, self._dimmer, attribute='action', new='up_press', is_party='off')
        self.poff_down_press_h = self.listen_state(self.poff_down_press, self._dimmer, attribute='action', new='down_press', is_party='off')
        self.poff_off_press_h = self.listen_state(self.poff_off_press, self._dimmer, attribute='action', new='off_press', is_party='off')
        self.poff_off_hold_h = self.listen_state(self.poff_off_hold, self._dimmer, attribute='action', new='off_hold', is_party='off')

        # dimmer actions - party on
        self.pon_on_press_h = self.listen_state(self.pon_on_press, self._dimmer, attribute='action', new='on_press', is_party='on')
        self.pon_up_press_h = self.listen_state(self.pon_up_press, self._dimmer, attribute='action', new='up_press', is_party='on')
        self.pon_down_press_h = self.listen_state(self.pon_down_press, self._dimmer, attribute='action', new='down_press', is_party='on')
        self.pon_off_press_h = self.listen_state(self.pon_off_press, self._dimmer, attribute='action', new='off_press', is_party='on')

        # party
        self.party_on_handler = self.listen_state(self.party_on, self.party_state, old='off', new='on')
        self.party_off_handler = self.listen_state(self.party_off, self.party_state, old='on', new='off')

    def is_party(self, value):
        if value == 'off':
            if self.get_state(self.party_state) == 'off':
                return True
        elif value == 'on':
            if self.get_state(self.party_state) == 'on':
                return True
        else:
            return False

    def poff_on_press(self, entity, attribute, old, new, kwargs):
        self.toggle(self._light_group)
        new_state = self.get_state(self._light_group)
        self.check_state()

    def pon_on_press(self, entity, attribute, old, new, kwargs):
        self.toggle_party_state()
        self.check_call_on_slaves('toggle_party_state')
    
    def poff_up_press(self, entity, attribute, old, new, kwargs):
        self.increase_brightness()
        new_state = self.get_state(self._light_group)
        self.check_state()
    
    def pon_up_press(self, entity, attribute, old, new, kwargs):
        self.increase_transition()
        self.check_call_on_slaves('increase_transition')

    def poff_down_press(self, entity, attribute, old, new, kwargs):
        self.decrease_brightness()
        new_state = self.get_state(self._light_group)
        self.check_state()

    def pon_down_press(self, entity, attribute, old, new, kwargs):
        self.decrease_transition()
        self.check_call_on_slaves('decrease_transition')

    def poff_off_press(self, entity, attribute, old, new, kwargs):
        self.create_task(self.next_scene())
        self.check_state()

    def pon_off_press(self, entity, attribute, old, new, kwargs):
        self.next_party_scene()
        self.check_call_on_slaves('next_party_scene')
    
    def poff_off_hold(self, entity, attribute, old, new, kwargs):
        self.strobe_lights()
        if self.hold_ts:
            self.log(f'{self.hold_ts}')
            if self.hold_ts + 2 < self.get_now_ts():
                self.toggle_party_state()
                self.check_call_on_slaves('toggle_party_state')
        else:
            self.log('no hold')
            self.hold_ts = self.get_now_ts()
            self.create_task(self.reset_hold())
        self.check_call_on_slaves('strobe_lights')

    async def reset_hold(self, **kwargs):
        await self.sleep(5)
        self.hold_ts = None
        self.log('hold reset')
            
    def check_call_on_slaves(self, attr):
        if self._master:
            for app in self.apps:
                getattr(app, attr)()

    def toggle_party_state(self):
        self.toggle(self.party_state)

    def check_state(self):
        self.create_task(self.check_state_task())
    
    async def check_state_task(self, **kwargs):
        await self.sleep(0.7)
        state = await self.get_state(self._light_group)
        if state == 'on':
            await self.turn_on(self.blocker)
        elif state == 'off':
            await self.turn_off(self.blocker)

    def set_inputs(self):
        choice = self.party_scene
        trans_max = choice.get('trans_max', 4)
        trans_min = choice.get('trans_min', 3)
        self.set_value(self._trans_max, trans_max)
        self.set_value(self._trans_min, trans_min)

    async def party_on(self, entity, attribute, old, new, kwargs):
        await self.sleep(0.5)
        await self.save_scene_async()
        self.set_inputs()
        await self.create_handles_async()

    async def party_scene_run(self, **kwargs):
        self.log(f'entered with state: {await self.get_state(self.party_state)}')
        light = kwargs.get('light')
        scene = kwargs.get('scene')
        colours = scene['colours']
        wait = scene.get('wait', 0)
        while await self.get_state(self.party_state) == 'on':
            if len(colours) > 1:
                choice = random.choice(colours)
            else:
                choice = colours[0]
            hue = self.aggr_hue(choice)
            trans = await self.aggr_trans()
            sat = self.aggr_sat(choice)
            val = self.aggr_val(choice)
            wait = trans + wait + BASE_DELAY
            self.log(f'hue={hue}, trans={trans}, sat={sat}, val={val}, wait={wait}', level='INFO')
            self.turn_on(light, hs_color=[hue, sat], brightness=val, transition=trans)
            await self.sleep(wait)

        self.log('exited ')

    def party_off(self, entity, attribute, old, new, kwargs):
        self._cancel_handles()
        max_init = self.get_state(self._trans_max, attribute='initial')
        self.set_value(self._trans_max, max_init)
        min_init = self.get_state(self._trans_min, attribute='initial')
        self.set_value(self._trans_min, min_init)
        self.turn_on(f'scene.{self.get_scene_id()}', transition=0.5)

    def aggr_hue(self, choice):
        if choice.get('hue_dev') != 0:
            lower = choice.get('hue') - choice.get('hue_dev')
            upper = choice.get('hue') + choice.get('hue_dev')
            if upper > lower:
                hue = random.randint(lower, upper) % 361
            else:
                hue = lower % 361
        else:
            hue = random.randint(0, 360)
        self.log(f'hue={hue}', level='DEBUG')
        return hue

    async def aggr_trans(self):
        trans = round(
            random.uniform(float(await self.get_state(self._trans_min)), float(await self.get_state(self._trans_max))),
            1)
        self.log(f'trans={trans}', level='DEBUG')
        return trans

    def aggr_sat(self, choice):
        if choice.get('sat_dev') != 0:
            sat = random.randint(choice.get('sat') - choice.get('sat_dev'),
                                 choice.get('sat') + choice.get('sat_dev'))
        else:
            sat = choice.get('sat')
        if sat >= 100:
            sat = 100
        elif sat < 0:
            sat = 1
        self.log(f'sat={sat}', level='DEBUG')
        return sat

    def aggr_val(self, choice):
        if choice.get('val') != 0:
            lower = choice.get('val') - choice.get('val_dev')
            upper = choice.get('val') + choice.get('val_dev')
            if lower != upper:
                val = random.randint(lower, upper)
            else:
                val = lower
        else:
            val = choice.get('val')
        if val >= 255:
            val = 255
        elif val < 0:
            val = 1
        self.log(f'val={val}', level='DEBUG')
        return val

    def scene_selector_changed(self, entity, attribute, old, new, kwargs):
        state = self.get_state(self._scene_selector)
        self.log(f'Scene selected: {state}')
        try:
            self.turn_on(f'scene.{state}', transition=0.4)
        except BadRequest as e:
            raise e

    async def next_scene(self):
        self.log(f'selector: {self._scene_selector}')
        try:
            await self.sleep(0.05)
            if await self.get_state(self._dimmer, attribute='action') != 'off_hold':
                await self.call_service("input_select/select_next", entity_id=self._scene_selector)
        except BadRequest as e:
            raise e

    def next_party_scene(self):
        self._cancel_handles()
        self._party_index = (self._party_index + 1) % len(self._scenes)
        self.set_inputs()
        self.create_handles()

    def increase_brightness(self):
        lights = self._light_group
        brightness = self.get_state(lights, attribute='brightness')
        if brightness is None:
            self.turn_on(lights, brightness=36, transition=0.5)
        else:
            new_brightness = brightness + 36
            if new_brightness > 255:
                new_brightness = 255
            self.turn_on(lights, brightness=new_brightness, transition=0.5)

    def decrease_brightness(self):
        lights = self._light_group
        brightness = self.get_state(lights, attribute='brightness')
        if brightness is not None:
            new_brightness = brightness - 36
            if new_brightness <= 0:
                self.turn_off(lights, transition=0.2)
            else:
                self.turn_on(lights, brightness=new_brightness, transition=0.2)

    def increase_transition(self):
        state_max = self.get_state(self._trans_max, attribute='all')
        state_min = self.get_state(self._trans_min, attribute='all')
        limit_max = state_max['attributes'].get('max')
        limit_min = state_min['attributes'].get('max')
        curr_max = float(state_max.get('state'))
        curr_min = float(state_min.get('state'))
        new_max = curr_max + self._trans_max_step
        new_min = curr_min + self._trans_min_step

        if new_max > limit_max - self._trans_max_step:
            new_max = curr_max + state_max['attributes'].get('step') * 2
            if new_max > limit_max:
                new_max = limit_max
        if new_min > limit_min - self._trans_min_step:
            new_min = curr_min + state_min['attributes'].get('step') * 2
            if new_min > limit_min:
                new_min = limit_min

        self.log(f'new_max={new_max}, new_min={new_min}')
        self.call_service('input_number/set_value', entity_id=self._trans_max, value=new_max)
        self.call_service('input_number/set_value', entity_id=self._trans_min, value=new_min)

    def decrease_transition(self):
        state_max = self.get_state(self._trans_max, attribute='all')
        state_min = self.get_state(self._trans_min, attribute='all')
        limit_max = state_max['attributes'].get('min') * 4
        limit_min = state_min['attributes'].get('min') * 3
        curr_max = float(state_max.get('state'))
        curr_min = float(state_min.get('state'))
        new_max = curr_max - self._trans_max_step
        new_min = curr_min - self._trans_min_step

        if new_max < limit_max + self._trans_max_step:
            new_max = curr_max - state_max['attributes'].get('step') * 2
            if new_max < limit_max:
                new_max = limit_max
        if new_min > limit_min + self._trans_min_step:
            new_min = curr_min - state_min['attributes'].get('step') * 2
            if new_min < limit_min:
                new_min = limit_min
        self.log(f'new_max={new_max}, new_min={new_min}')
        self.call_service('input_number/set_value', entity_id=self._trans_max, value=new_max)
        self.call_service('input_number/set_value', entity_id=self._trans_min, value=new_min)

    def get_lights(self) -> List[str]:
        return self.get_state(self._light_group, attribute='entity_id')

    async def get_lights_async(self) -> List[str]:
        return await self.get_state(self._light_group, attribute='entity_id')

    def strobe_lights(self):
        self.turn_on(self._light_group, flash="short")

    @property
    def party_scene(self):
        return self._scenes[self._party_index]

    def get_scene_id(self) -> str:
        id_ = self.get_state(self._light_group, attribute='all').get('entity_id') + 'party'
        id_ = id_.split('.')[1]
        self.log(f'scene id: {id_}')
        return id_
    
    async def get_scene_id_async(self) -> str:
        tmp = await self.get_state(self._light_group, attribute='all') 
        id_ = tmp.get('entity_id') + 'party'
        id_ = id_.split('.')[1]
        self.log(f'scene id: {id_}')
        return id_

    def save_scene(self):
        self.call_service("scene/create",
                    scene_id=self.get_scene_id(),
                    snapshot_entities=self.get_lights())

    async def save_scene_async(self):
        self.call_service("scene/create",
                    scene_id=await self.get_scene_id_async(),
                    snapshot_entities=await self.get_lights_async())

    def create_handles(self):
        for light in self.get_lights():
            self._handles.append(self.create_task(self.party_scene_run(light=light, scene=self.party_scene)))

    async def create_handles_async(self):
        for light in await self.get_lights_async():
            self._handles.append(await self.create_task(self.party_scene_run(light=light, scene=self.party_scene)))

    def _cancel_handles(self):
        for h in self._handles:
            if not h.done():
                h.cancel()

    def all_apps_of_me(self):
        objs = self.get_ad_api().AD.app_management.objects
        lst = []
        for key, val in objs.items():
            obj = val['object']
            if isinstance(obj, self.__class__):
                lst.append(obj)
        self.log(str(lst), log='test_log')
        return lst
    
    def lights_off(self, entity, attribute, old, new, kwargs):
        self.turn_off(self.blocker)

    @property
    def party_scenes(self):
        return [
                {"wait": 0,
                 "trans_max": 3,
                 "trans_min": 1,
                 "colours": [{
                     "hue": 1,
                     "sat": 50,
                     "val": 255,
                     "hue_dev": 179,
                     "sat_dev": 49,
                     "val_dev": 1}]},
                {"wait": 0,
                 "trans_max": 26,
                 "trans_min": 15,
                 "colours": [{
                     "hue": 35,
                     "sat": 90,
                     "val": 210,
                     "hue_dev": 15,
                     "sat_dev": 10,
                     "val_dev": 35}]},
                {"wait": 4,
                 "trans_max": 1,
                 "trans_min": 0.5,
                 "colours": [{
                     "hue": 360,
                     "sat": 100,
                     "val": 255,
                     "hue_dev": 10,
                     "sat_dev": 0,
                     "val_dev": 10},
                     {"hue": 360,
                      "sat": 1,
                      "val": 255,
                      "hue_dev": 0,
                      "sat_dev": 0,
                      "val_dev": 10}]}
            ]
