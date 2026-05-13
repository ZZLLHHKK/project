from __future__ import annotations

from .hardware_7seg import SevenSegDisplay
from .hardware_dht11 import DHT11Reader
from .hardware_fan import FanController
from .hardware_led import LedController


class DeviceController:
    def __init__(self) -> None:
        self.fan = FanController()
        self.led = LedController()
        self.seven_seg = SevenSegDisplay()
        self.dht11 = DHT11Reader()

    def setup(self) -> None:
        self.fan.setup()
        self.led.setup()
        self.seven_seg.setup()
        self.seven_seg.start()
        self.dht11.start()

    def cleanup(self) -> None:
        self.fan.cleanup()
        self.led.cleanup()
        self.seven_seg.cleanup()
        self.dht11.stop()
        try:
            import RPi.GPIO as GPIO

            GPIO.cleanup()
        except Exception:
            pass

    def set_fan(self, state: str) -> None:
        self.fan.set_fan(state)

    def set_led(self, location: str, state: str) -> None:
        self.led.set_led(location, state)

    def set_temp(self, temp: int) -> None:
        self.seven_seg.set_temp(temp)

    def get_temp(self):
        return self.dht11.get_temp_int()

    def get_humidity(self):
        return self.dht11.get_humidity()

    def execute_actions(self, actions: list[dict]) -> list[dict]:
        results: list[dict] = []
        for action in actions:
            print(f"[DEVICE CONTROLLER] executing: {action}")
            result = dict(action)
            result["success"] = True
            try:
                action_type = str(action.get("type", "")).upper()
                if action_type == "LED":
                    self.set_led(str(action.get("location", "LIVING")).upper(), str(action.get("state", "off")).lower())
                elif action_type == "FAN":
                    self.set_fan(str(action.get("state", "off")).lower())
                elif action_type == "SET_TEMP":
                    self.set_temp(int(action.get("value", 25)))
                elif action_type == "AC_ON":
                    # 冷氣開啟時顯示上次的溫度
                    self.seven_seg.show_last_temp()
                elif action_type == "AC_OFF":
                    # 冷氣關閉時只顯示中間的橫線（g線段）
                    self.seven_seg.show_middle_line()
                else:
                    result["success"] = False
                    result["error"] = f"unsupported action: {action_type}"
            except Exception as exc:
                result["success"] = False
                result["error"] = str(exc)
            results.append(result)
        return results
