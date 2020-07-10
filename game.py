# -*- coding: utf-8 -*-

# pip install -r requirements.txt

from astrobox.space_field import SpaceField
# TODO - Переименуйте класс своего дрона по шаблону [Фамилия]Drone
from pestov import NostromoDrone


if __name__ == '__main__':
    scene = SpaceField(
        speed=3,
        asteroids_count=5,
    )
    d = NostromoDrone()
    scene.go()
