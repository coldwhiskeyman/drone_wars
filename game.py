# -*- coding: utf-8 -*-

# pip install -r requirements.txt

from astrobox.space_field import SpaceField
from pestov import PestovDrone


if __name__ == '__main__':
    scene = SpaceField(
        speed=3,
        asteroids_count=5,
    )
    drones = [PestovDrone() for _ in range(5)]
    scene.go()

# Первый этап: зачёт!
