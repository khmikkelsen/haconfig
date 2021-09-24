import appdaemon.plugins.hass.hassapi as hass


class Global(hass.Hass):
    def initialize(self):
        self.log("initializing ...")
        try:
            self.log(f'args: {self.args}')
            if self.args.get('logger'):
                self.logger = self.get_user_log(self.args['logger'])
        except (TypeError, ValueError) as e:
            self.log('Incomplete configuration', level="ERROR")
            raise e