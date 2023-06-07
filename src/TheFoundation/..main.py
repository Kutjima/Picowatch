import os
import time
import machine
import network
import ntptime


class Pool():

    @staticmethod
    def network_connect(ssid: str, password: str):
        wlan = network.WLAN(network.STA_IF)
        # activate the interface
        wlan.active(True)
        # connect to the access point with the ssid and password
        wlan.connect(ssid, password)

        for c in range(0, 5):
            time.sleep(1)

            if wlan.status() < 0 or wlan.status() >= 3:
                break

        if wlan.isconnected() == False:
            raise RuntimeError('Connection failed to WiFi')
        else:
            ifconfig = wlan.ifconfig()
            print(s := f'Connection succeeded to WiFi = {ssid} with IP = {ifconfig[0]}')
            print('-' * len(s))

    def __init__(self, timezone: int = 0, clock_interval: int = 1):
        self.timezone: int = timezone
        self.clock_interval: int = clock_interval
        self.schedules: dict[str, callable] = {}

        tm = time.gmtime(ntptime.time())
        machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3] + timezone, tm[4], tm[5], 0))

    def schedule(self, at: str, date: str, schedule_id: str = ''):
        if not schedule_id:
            seeds = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            schedule_id = ''.join([seeds[x] for x in [(os.urandom(1)[0] % len(seeds)) for _ in range(8)]])
            
        def decorator(callback: callable) -> callable:
            self.schedules[schedule_id] = (date, at, callback)

            return callback
        return decorator

    def stop(self, schedule_id: str):
        print(self.schedules)
        pass

    async def clock(self):
        while True:
            _, mth, dte, hrs, mnt, sec, wkd, yrd = time.localtime()

            time.sleep(self.clock_interval)


# Pool.network_connect(ssid='SFR-a9c8', password='abc123de45f6')
Pool.network_connect(ssid='PMD', password="Primadiag2021'...")
pool = Pool(timezone=2)

@pool.schedule(date='21/12', at='01:00')
def explore():
    return 1


pool.stop('s')

while True:
    _, mt, dd, hh, mm, ss, wd, yd = time.localtime()

    for schedule_id, d in pool.schedules.items():
        print(schedule_id, d)

    print('date:', mt, '-', dd, 'time:', hh, ':', mm, ':', ss, 'wd:', wd, 'yd:', yd)
    time.sleep(1)
# while True:
#     print(time.localtime())
#     time.sleep(1)
