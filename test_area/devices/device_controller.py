from devices.hardware_fan import FanController
from devices.hardware_led import LedController
from devices.hardware_7seg import SevenSegDisplay
from devices.hardware_dht11 import DHT11Reader

class DeviceController:
    def __init__(self):
        # 初始化各硬體
        self.fan = FanController()
        self.led = LedController()
        self.seven_seg = SevenSegDisplay()
        self.dht11 = DHT11Reader()

    def setup(self):
        self.fan.setup()
        self.led.setup()
        self.seven_seg.setup()
        self.seven_seg.start()
        self.dht11.start()
    
    def cleanup(self):
        self.fan.cleanup()
        self.led.cleanup()
        self.seven_seg.cleanup()
        self.dht11.stop()

    # 風扇控制
    def set_fan(self, state):
        self.fan.set_fan(state)

    # LED 控制
    def set_led(self, location, state):
        self.led.set_led(location, state)

    # 七段顯示器
    def set_temp(self, temp):
        self.seven_seg.set_temp(temp)

    # DHT11 讀取
    def get_temp(self):
        return self.dht11.get_temp_int()
    
    def get_humidity(self):
        return self.dht11.get_humidity()
