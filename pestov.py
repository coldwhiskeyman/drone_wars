from astrobox.core import Drone
from robogame_engine.geometry import Point


class CantInterceptException(Exception):
    pass


class PestovDrone(Drone):
    my_team = []
    unavailable_asteroids = []

    def __init__(self, logger, **kwargs):
        super().__init__(**kwargs)
        self.waiting = False
        self.previous_target = Point(self.x, self.y)
        self._logger = logger

    def on_born(self):
        """Действие при активации дрона"""
        self.move_to_the_closest_asteroid()
        self.my_team.append(self)

    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        self.load_from(asteroid)

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if self.target.payload != 0:
            self.unavailable_asteroids.remove(self.target)
        if self.is_full:
            self.move_to_mothership()
        else:
            try:
                self.intercept_asteroid()
            except CantInterceptException:
                self.move_to_the_closest_asteroid()

    def on_stop_at_mothership(self, mothership):
        """Действие при возвращении на базу"""
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        if not self.is_empty:
            self.unload_to(mothership)
        else:
            self.on_unload_complete()

    def on_unload_complete(self):
        """Действие при завершении разгрузки дрона"""
        self.move_to_the_closest_asteroid()
        if self.target == self.my_mothership:
            self.waiting = True

    def on_wake_up(self):
        self.move_to_the_closest_asteroid()

    def move_to_mothership(self):
        """Двигаться на базу"""
        self.target = self.my_mothership
        self.move_at(self.target)

    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        self.target = self.get_the_closest_asteroid()
        if self.target:
            self.unavailable_asteroids.append(self.target)
            self.move_at(self.target)
        else:
            self.target = self.my_mothership
            self.move_at(self.target)

    def intercept_asteroid(self):
        """
        Попытка перехватить цель у другого дрона,
        если этот дрон находится ближе к цели.
        """
        distances = {}
        for asteroid in self.unavailable_asteroids:
            distance = self.distance_to(asteroid)
            for drone in self.my_team:
                if drone != self and drone.target == asteroid:
                    if drone.distance_to(asteroid) > distance:
                        distances[asteroid] = [drone, distance]
        for asteroid, data in distances.items():
            if data == min(distances.values(), key=lambda x: x[1]):
                self._logger.log_route(self)
                self.previous_target = Point(self.x, self.y)
                self.unavailable_asteroids.remove(asteroid)
                self.move_to_the_closest_asteroid()
                data[0]._logger.log_route(data[0])
                data[0].previous_target = Point(self.x, self.y)
                data[0].move_to_the_closest_asteroid()
                break
        else:
            raise CantInterceptException

    def get_the_closest_asteroid(self):
        """Выбор ближайшего к дрону астероида"""
        distances = []
        for asteroid in self.asteroids:
            if asteroid not in self.unavailable_asteroids:
                distance = self.distance_to(asteroid)
                distances.append((asteroid, distance))
        if distances:
            return (min(distances, key=lambda x: x[1]))[0]

    def game_step(self):
        super().game_step()
        if self.waiting:
            if len(self.asteroids) > len(self.unavailable_asteroids):
                self.waiting = False
                self.move_to_the_closest_asteroid()
        if not self._logger.statistics_written:
            for drone in self.my_team:
                if not drone.waiting:
                    break
            else:
                self._logger.write_statistics()
