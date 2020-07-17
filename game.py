# -*- coding: utf-8 -*-

# pip install -r requirements.txt

from datetime import datetime

from astrobox.space_field import SpaceField
from pestov import PestovDrone


def log_init():
    with open('drones_statistics.log', 'a') as log:
        log.write('Игра началась: ' + datetime.today().strftime('%Y.%m.%d %H-%M') + '\n')


if __name__ == '__main__':
    scene = SpaceField(
        speed=3,
        asteroids_count=15,
    )
    drones = [PestovDrone() for _ in range(5)]
    log_init()
    scene.go()

# Первый этап: зачёт!
