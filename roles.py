from robogame_engine.geometry import Point
from astrobox.core import Asteroid

SUFFICIENT_PAYLOAD = 90


class CantInterceptException(Exception):
    pass


class Role:
    pass


class Fighter(Role):
    @staticmethod
    def attack_mode(self):
        """атака вражеских дронов или базы в радиусе поражения"""
        enemy = self.check_for_enemy_drones()
        if enemy:
            self.turn_to(enemy)
            self.gun.shot(enemy)
        elif self.check_target_base():
            self.__class__.attack_distance = 600
            self.turn_to(self.attack_plan.target_mothership)
            self.gun.shot(self.attack_plan.target_mothership)
        else:
            self.attacking = False

    @staticmethod
    def check_for_enemy_drones(self):
        """проверка на вражеских дронов в радиусе поражения"""
        for drone in self.scene.drones:
            if drone not in self.my_team and self.distance_to(drone) <= self.__class__.attack_distance and drone.is_alive:
                return drone

    @staticmethod
    def check_target_base(self):
        if self.attack_plan.target_mothership:
            if self.attack_plan.target_mothership.is_alive:
                return self.distance_to(self.attack_plan.target_mothership) <= self.__class__.attack_distance
            else:
                self.attack_plan.abort_attack()
                return False
        else:
            return False


class Harvester(Role):
    @staticmethod
    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        if self.next_target:
            self.turn_to(self.next_target)
        elif self.payload + asteroid.payload >= SUFFICIENT_PAYLOAD:
            self.turn_to(self.my_mothership)
        self.load_from(asteroid)

    @staticmethod
    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if isinstance(self.target, Asteroid) and self.target in self.unavailable_asteroids:
            if self.target.payload != 0:
                self.unavailable_asteroids.remove(self.target)
        if self.payload >= SUFFICIENT_PAYLOAD:
            self.move_to_mothership()
        elif self.next_target:
            self.target = self.next_target
            max_payload = SUFFICIENT_PAYLOAD - self.payload
            self.make_route(max_payload)
            self.move_at(self.target)
        else:
            try:
                self.intercept_asteroid()
            except CantInterceptException:
                self.move_to_the_closest_asteroid()

    @staticmethod
    def make_route(self, max_payload):
        if self.target.payload < max_payload:
            self.next_target = self.get_next_asteroid()
            if self.next_target:
                self.unavailable_asteroids.append(self.next_target)
        else:
            self.next_target = None

    @staticmethod
    def try_to_depart(self):
        """Отправление с базы"""
        self.move_to_the_closest_asteroid()
        if self.target == self.my_mothership:
            self.waiting = True

    @staticmethod
    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        self.target = self.get_the_closest_asteroid()
        if self.target:
            self.unavailable_asteroids.append(self.target)
            self.make_route(SUFFICIENT_PAYLOAD)
            self.move_at(self.target)
        else:
            self.target = self.my_mothership
            if self.near(self.my_mothership):
                self.waiting = True
            else:
                self.move_at(self.target)

    @staticmethod
    def intercept_asteroid(self):
        """
        Попытка перехватить цель у другого дрона,
        если этот дрон находится ближе к цели.
        """
        distances = {}
        for asteroid in self.unavailable_asteroids:
            distance = self.distance_to(asteroid)
            for drone in self.teammates:
                if drone.target == asteroid and drone.distance_to(asteroid) > distance:
                    distances[asteroid] = [drone, distance]
        for asteroid, drone_distance_pair in distances.items():
            closest_drone = min(distances.values(), key=lambda x: x[1])
            if drone_distance_pair == closest_drone:
                self._logger.log_route(self)
                self.previous_target = Point(self.x, self.y)
                self.unavailable_asteroids.remove(asteroid)
                self.move_to_the_closest_asteroid()
                drone_distance_pair[0]._logger.log_route(drone_distance_pair[0])
                coords = Point(drone_distance_pair[0].x, drone_distance_pair[0].y)
                drone_distance_pair[0].previous_target = coords
                drone_distance_pair[0].move_to_the_closest_asteroid()
                break
        else:
            raise CantInterceptException

    @staticmethod
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

    @staticmethod
    def get_next_asteroid(self):
        """Выбрать ближайший к текущей цели астероид"""
        distances = [(asteroid, self.target.distance_to(asteroid)) for asteroid in self.asteroids
                     if asteroid not in self.unavailable_asteroids]

        for drone in self.scene.drones:
            if self.target and drone.target:
                distance_to_target = self.distance_to(self.target) + self.target.distance_to(drone.target)
                self.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)

        if distances:
            return (min(distances, key=lambda x: x[1]))[0]

    @staticmethod
    def remove_asteroid_occupied_by_enemy(self, drone, distance_to_target, distances):
        if drone not in self.my_team and drone.distance_to(drone.target) < distance_to_target:
            for asteroid_distance_pair in distances:
                if asteroid_distance_pair[0] == drone.target:
                    distances.remove(asteroid_distance_pair)
                    break
