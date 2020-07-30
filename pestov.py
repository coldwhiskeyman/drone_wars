from astrobox.core import Drone, Asteroid
from robogame_engine.geometry import Point

SUFFICIENT_PAYLOAD = 90
DEFENSE_POSITIONS = [Point(100, 350), Point(160, 290), Point(225, 225), Point(290, 160), Point(350, 100)]


class CantInterceptException(Exception):
    pass


class PestovDrone(Drone):
    my_team = []
    unavailable_asteroids = []

    def __init__(self, logger, **kwargs):
        super().__init__(**kwargs)
        self.waiting = False
        self.guarding = False
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
        elif self.payload + asteroid.payload >= SUFFICIENT_PAYLOAD:
            self.turn_to(self.my_mothership)
        self.load_from(asteroid)

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if isinstance(self.target, Asteroid) and self.target in self.unavailable_asteroids:
            if self.target.payload != 0:
                self.unavailable_asteroids.remove(self.target)
        if self.payload >= SUFFICIENT_PAYLOAD:
            self.move_to_mothership()
        elif self.next_target:
            self.target = self.next_target
            if self.target.payload < SUFFICIENT_PAYLOAD - self.payload:
                self.next_target = self.make_route()
                if self.next_target:
                    self.unavailable_asteroids.append(self.next_target)
            else:
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
        self.guarding = False
        self.next_target = None
        self.move_at(self.target)

    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        self.target = self.get_the_closest_asteroid()
        if self.target:
            self.unavailable_asteroids.append(self.target)
            if self.target.payload < SUFFICIENT_PAYLOAD:
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
            if asteroid_distance_pair[0].payload >= SUFFICIENT_PAYLOAD]

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
        if self.waiting:  # возможные действия, при ожидании на базе
            for drone in self.scene.drones:  # защита базы, при приближении вражеских дронов
                if self.check_for_enemy_drones(drone):
                    self.go_to_defense_position()
            if len(self.asteroids) > len(self.unavailable_asteroids):  # отправка на добычу, при наличии свободных астероидов
                self.waiting = False
                self.try_to_depart()

        if self.target in DEFENSE_POSITIONS and self.near(self.target) and not self.guarding:  # режим защиты базы, после выхода на позицию
            self.guarding = True
        if self.guarding:  # атака вражеских дронов в радиусе поражения
            for drone in self.scene.drones:
                if self.check_for_enemy_drones(drone):
                    self.turn_to(drone)
                    self.gun.shot(drone)
                    break
            else:
                self.move_to_mothership()

        if self.health <= 30:  # бегство из боя
            self._logger.log_route(self)
            self.previous_target = Point(self.x, self.y)
            if isinstance(self.target, Asteroid) and self.target in self.unavailable_asteroids:
                self.unavailable_asteroids.remove(self.target)
            self.move_to_mothership()
            
        for asteroid in self.asteroids:  # проверка, не опустели ли астероиды
            if asteroid not in self.unavailable_asteroids and asteroid.payload == 0:
                self.unavailable_asteroids.append(asteroid)
        if not self._logger.statistics_written:  # запись статистики по завершении игры
            for drone in self.my_team:
                if not drone.waiting:
                    break
            else:
                self._logger.write_statistics()

    def go_to_defense_position(self):
        """Выход на позицию для защиты базы"""
        for point in DEFENSE_POSITIONS:
            if any([drone.near(point) or (drone.target == point and drone != self) for drone in self.my_team]):
                continue
            else:
                self.target = point
                self.move_at(self.target)

    def check_for_enemy_drones(self, drone):
        return drone not in self.my_team and self.distance_to(drone) <= 500 and drone.is_alive
