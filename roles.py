from robogame_engine.geometry import Point
from astrobox.core import Asteroid

SUFFICIENT_PAYLOAD = 90


class CantInterceptException(Exception):
    pass


class Role:
    def __init__(self, drone):
        self.drone = drone


class Fighter(Role):
    def __init__(self, drone):
        super().__init__(drone)

    def attack_mode(self):
        """атака вражеских дронов или базы в радиусе поражения"""
        enemy = self.drone.check_for_enemy_drones()
        if enemy:
            self.drone.turn_to(enemy)
            self.drone.gun.shot(enemy)
        elif self.drone.check_target_base():
            self.drone.turn_to(self.drone.attack_plan.target_mothership)
            self.drone.gun.shot(self.drone.attack_plan.target_mothership)
        else:
            self.drone.attacking = False

    def check_for_enemy_drones(self):
        """проверка на вражеских дронов в радиусе поражения"""
        for drone in self.drone.scene.drones:
            if drone not in self.drone.__class__.my_team and self.drone.distance_to(drone) <= 600 and drone.is_alive:
                return drone

    def check_target_base(self):
        if self.drone.attack_plan.target_mothership:
            if self.drone.attack_plan.target_mothership.is_alive:
                return self.drone.distance_to(self.drone.attack_plan.target_mothership) <= 600
            else:
                self.drone.attack_plan.abort_attack()
                return False
        else:
            return False


class Harvester(Role):
    def __init__(self, drone):
        super().__init__(drone)

    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        self.drone._logger.log_route(self.drone)
        self.drone.previous_target = Point(self.drone.x, self.drone.y)
        if self.drone.next_target:
            self.drone.turn_to(self.drone.next_target)
        elif self.drone.payload + asteroid.payload >= SUFFICIENT_PAYLOAD:
            self.drone.turn_to(self.drone.my_mothership)
        self.drone.load_from(asteroid)

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if isinstance(self.drone.target, Asteroid) and self.drone.target in self.drone.__class__.unavailable_asteroids:
            if self.drone.target.payload != 0:
                self.drone.__class__.unavailable_asteroids.remove(self.drone.target)
        if self.drone.payload >= SUFFICIENT_PAYLOAD:
            self.drone.move_to_mothership()
        elif self.drone.next_target:
            self.drone.target = self.drone.next_target
            max_payload = SUFFICIENT_PAYLOAD - self.drone.payload
            self.drone.make_route(max_payload)
            self.drone.move_at(self.drone.target)
        else:
            try:
                self.drone.intercept_asteroid()
            except CantInterceptException:
                self.drone.move_to_the_closest_asteroid()

    def make_route(self, max_payload):
        if self.drone.target.payload < max_payload:
            self.drone.next_target = self.drone.get_next_asteroid()
            if self.drone.next_target:
                self.drone.__class__.unavailable_asteroids.append(self.drone.next_target)
        else:
            self.drone.next_target = None

    def try_to_depart(self):
        """Отправление с базы"""
        self.drone.move_to_the_closest_asteroid()
        if self.drone.target == self.drone.my_mothership:
            self.drone.waiting = True

    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        self.drone.target = self.drone.get_the_closest_asteroid()
        if self.drone.target:
            self.drone.__class__.unavailable_asteroids.append(self.drone.target)
            self.drone.make_route(SUFFICIENT_PAYLOAD)
            self.drone.move_at(self.drone.target)
        else:
            self.drone.target = self.drone.my_mothership
            if self.drone.near(self.drone.my_mothership):
                self.drone.waiting = True
            else:
                self.drone.move_at(self.drone.target)

    def intercept_asteroid(self):
        """
        Попытка перехватить цель у другого дрона,
        если этот дрон находится ближе к цели.
        """
        distances = {}
        for asteroid in self.drone.__class__.unavailable_asteroids:
            distance = self.drone.distance_to(asteroid)
            for drone in self.drone.teammates:
                if drone.target == asteroid and drone.distance_to(asteroid) > distance:
                    distances[asteroid] = [drone, distance]
        for asteroid, drone_distance_pair in distances.items():
            closest_drone = min(distances.values(), key=lambda x: x[1])
            if drone_distance_pair == closest_drone:
                self.drone._logger.log_route(self.drone)
                self.drone.previous_target = Point(self.drone.x, self.drone.y)
                self.drone.__class__.unavailable_asteroids.remove(asteroid)
                self.drone.move_to_the_closest_asteroid()
                drone_distance_pair[0]._logger.log_route(drone_distance_pair[0])
                coords = Point(drone_distance_pair[0].x, drone_distance_pair[0].y)
                drone_distance_pair[0].previous_target = coords
                drone_distance_pair[0].move_to_the_closest_asteroid()
                break
        else:
            raise CantInterceptException

    def get_the_closest_asteroid(self):
        """
        Выбор ближайшего к дрону астероида.
        В первую очередь выбираются богатые элериумом астероиды.
        """
        distances = [(asteroid, self.drone.distance_to(asteroid)) for asteroid in self.drone.asteroids
                     if asteroid not in self.drone.__class__.unavailable_asteroids]

        for drone in self.drone.scene.drones:
            if self.drone.target and drone.target:
                distance_to_target = self.drone.target.distance_to(drone.target)
                self.drone.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)

        distances_to_rich = [
            asteroid_distance_pair for asteroid_distance_pair in distances
            if asteroid_distance_pair[0].payload >= SUFFICIENT_PAYLOAD]

        if distances_to_rich:
            return (min(distances_to_rich, key=lambda x: x[1]))[0]
        elif distances:
            return (min(distances, key=lambda x: x[1]))[0]

    def get_next_asteroid(self):
        """Выбрать ближайший к текущей цели астероид"""
        distances = [(asteroid, self.drone.target.distance_to(asteroid)) for asteroid in self.drone.asteroids
                     if asteroid not in self.drone.__class__.unavailable_asteroids]

        for drone in self.drone.scene.drones:
            if self.drone.target and drone.target:
                distance_to_target = self.drone.distance_to(self.drone.target) + self.drone.target.distance_to(
                    drone.target)
                self.drone.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)

        if distances:
            return (min(distances, key=lambda x: x[1]))[0]

    def remove_asteroid_occupied_by_enemy(self, drone, distance_to_target, distances):
        if drone not in self.drone.__class__.my_team and drone.distance_to(drone.target) < distance_to_target:
            for asteroid_distance_pair in distances:
                if asteroid_distance_pair[0] == drone.target:
                    distances.remove(asteroid_distance_pair)
                    break
