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
        self.next_target = None
        self._logger = logger

    def on_born(self):
        """Действие при активации дрона"""
        self.my_team.append(self)
        self.move_to_the_closest_asteroid()

    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        if self.next_target:
            self.turn_to(self.next_target)
        elif self.payload + asteroid.payload >= 90:
            self.turn_to(self.my_mothership)
        self.load_from(asteroid)

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if self.target.payload != 0:
            self.unavailable_asteroids.remove(self.target)
        if self.payload >= 90:
            self.move_to_mothership()
        elif self.next_target:
            self.target = self.next_target
            self.next_target = None
            self.move_at(self.target)
        else:
            try:
                self.intercept_asteroid()
            except CantInterceptException:
                self.move_to_the_closest_asteroid()

    def on_stop_at_mothership(self, mothership):
        """Действие при возвращении на базу"""
        self.turn_to(self.previous_target)  # да, бессмысленно, но главное, что развернется на ~180 градусов
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        if not self.is_empty:
            self.unload_to(mothership)
        else:
            self.try_to_depart()

    def on_unload_complete(self):
        """Действие при завершении разгрузки дрона"""
        self.try_to_depart()

    def try_to_depart(self):
        """Отправление с базы"""
        self.move_to_the_closest_asteroid()
        if self.target == self.my_mothership:
            self.waiting = True

    def on_wake_up(self):
        self.move_to_the_closest_asteroid()

    def move_to_mothership(self):
        """Двигаться на базу"""
        self.target = self.my_mothership
        self.next_target = None
        self.move_at(self.target)

    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        self.target = self.get_the_closest_asteroid()
        if self.target:
            self.unavailable_asteroids.append(self.target)
            if self.target.payload < 90:
                self.next_target = self.make_route()
                if self.next_target:
                    self.unavailable_asteroids.append(self.next_target)
            self.move_at(self.target)
        else:
            self.target = self.my_mothership
            if self.near(self.my_mothership):
                self.waiting = True
            else:
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
                if drone != self and\
                        drone.target == asteroid and\
                        drone.distance_to(asteroid) > distance:
                    distances[asteroid] = [drone, distance]
        for asteroid, drone_distance_pair in distances.items():
            closest_drone = min(distances.values(), key=lambda x: x[1])
            if drone_distance_pair == closest_drone:
                self._logger.log_route(self)
                self.previous_target = Point(self.x, self.y)
                self.unavailable_asteroids.remove(asteroid)
                self.move_to_the_closest_asteroid()
                drone_distance_pair[0]._logger.log_route(drone_distance_pair[0])
                drone_distance_pair[0].previous_target = Point(self.x, self.y)
                drone_distance_pair[0].move_to_the_closest_asteroid()
                break
        else:
            raise CantInterceptException

    def get_the_closest_asteroid(self):
        """
        Выбор ближайшего к дрону астероида.
        В первую очередь выбираются богатые элериумом астероиды.
        """
        distances = [(asteroid, self.distance_to(asteroid)) for asteroid in self.asteroids
                     if asteroid not in self.unavailable_asteroids]

        for drone in self.scene.drones:
            if self.target and drone.target:
                distance_to_target = self.target.distance_to(drone.target)
                self.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)

        distances_to_rich = [
            asteroid_distance_pair for asteroid_distance_pair in distances
            if asteroid_distance_pair[0].payload >= 90]

        if distances_to_rich:
            return (min(distances_to_rich, key=lambda x: x[1]))[0]
        elif distances:
            return (min(distances, key=lambda x: x[1]))[0]

    def make_route(self):
        """Выбрать ближайший к текущей цели астероид"""
        distances = [(asteroid, self.target.distance_to(asteroid)) for asteroid in self.asteroids
                     if asteroid not in self.unavailable_asteroids]

        for drone in self.scene.drones:
            if self.target and drone.target:
                distance_to_target = self.distance_to(self.target) + self.target.distance_to(drone.target)
                self.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)

        if distances:
            return (min(distances, key=lambda x: x[1]))[0]

    def remove_asteroid_occupied_by_enemy(self, drone, distance_to_target, distances):
        if drone not in self.my_team and drone.distance_to(drone.target) < distance_to_target:
            for asteroid_distance_pair in distances:
                if asteroid_distance_pair[0] == drone.target:
                    distances.remove(asteroid_distance_pair)
                    break

    def game_step(self):
        super().game_step()
        if self.waiting:
            if len(self.asteroids) > len(self.unavailable_asteroids):
                self.waiting = False
                self.try_to_depart()
        for asteroid in self.asteroids:
            if asteroid not in self.unavailable_asteroids and asteroid.payload == 0:
                self.unavailable_asteroids.append(asteroid)
        if not self._logger.statistics_written:
            for drone in self.my_team:
                if not drone.waiting:
                    break
            else:
                self._logger.write_statistics()
