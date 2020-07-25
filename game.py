# -*- coding: utf-8 -*-

# pip install -r requirements.txt
from datetime import datetime

from astrobox.space_field import SpaceField
from stage_03_harvesters.reaper import ReaperDrone
from stage_03_harvesters.driller import DrillerDrone
from pestov import PestovDrone

NUMBER_OF_DRONES = 5


class Logger:
    def __init__(self):
        self.empty_distance = 0.0
        self.not_full_distance = 0.0
        self.full_distance = 0.0
        self.statistics_written = False

    def log_init(self):
        with open('drones_statistics.log', 'a') as log:
            log.write('Игра началась: ' + datetime.today().strftime('%Y.%m.%d %H-%M') + '\n')

    def log_route(self, drone):
        distance = drone.distance_to(drone.previous_target)
        if drone.is_empty:
            self.empty_distance += distance
        elif drone.is_full:
            self.full_distance += distance
        else:
            self.not_full_distance += distance

    def write_statistics(self):
        with open('drones_statistics.log', 'a') as log:
            log.write('Пройдено в незагруженном состоянии: ' + str(round(self.empty_distance)) + '\n')
            log.write('Пройдено в полузагруженном состоянии: ' + str(round(self.not_full_distance)) + '\n')
            log.write('Пройдено в загруженном состоянии: ' + str(round(self.full_distance)) + '\n\n')
        self.statistics_written = True


if __name__ == '__main__':
    scene = SpaceField(
        speed=5,
        asteroids_count=20,
    )

    logger = Logger()
    logger.log_init()

    team_1 = [PestovDrone(logger=logger) for _ in range(NUMBER_OF_DRONES)]
    team_2 = [DrillerDrone() for _ in range(NUMBER_OF_DRONES)]
    scene.go()
