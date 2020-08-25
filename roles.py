from robogame_engine.geometry import Point
from astrobox.core import Asteroid

SUFFICIENT_PAYLOAD = 90


class CantInterceptException(Exception):
    pass


class Role:
    def __init__(self, drone):
        self.unit = drone


class Fighter(Role):
    def __init__(self, drone):
        super().__init__(drone)

    def attack_mode(self):
        """атака вражеских дронов или базы в радиусе поражения"""
        enemy = self.unit.check_for_enemy_drones()
        if enemy:
            self.unit.turn_to(enemy)
            self.unit.gun.shot(enemy)
        elif self.unit.check_target_base():
            self.unit.turn_to(self.unit.attack_plan.target_mothership)
            self.unit.gun.shot(self.unit.attack_plan.target_mothership)
        else:
            self.unit.attacking = False

    def check_for_enemy_drones(self):
        """проверка на вражеских дронов в радиусе поражения"""
        for drone in self.unit.scene.drones:
            if drone not in self.unit.__class__.my_team and self.unit.distance_to(drone) <= 600 and drone.is_alive:
                return drone

    def check_target_base(self):
        if self.unit.attack_plan.target_mothership:
            if self.unit.attack_plan.target_mothership.is_alive:
                return self.unit.distance_to(self.unit.attack_plan.target_mothership) <= 600
            else:
                self.unit.attack_plan.abort_attack(self.unit.__class__.fighters)
                return False
        else:
            return False


class Harvester(Role):
    def __init__(self, drone):
        super().__init__(drone)

    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        self.unit.previous_target = Point(self.unit.x, self.unit.y)
        if self.unit.next_target:
            self.unit.turn_to(self.unit.next_target)
        elif self.unit.payload + asteroid.payload >= SUFFICIENT_PAYLOAD:
            self.unit.turn_to(self.unit.my_mothership)
        self.unit.load_from(asteroid)

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if isinstance(self.unit.target, Asteroid) and self.unit.target in self.unit.__class__.unavailable_asteroids:
            if self.unit.target.payload != 0:
                self.unit.__class__.unavailable_asteroids.remove(self.unit.target)
        if self.unit.payload >= SUFFICIENT_PAYLOAD:
            self.unit.move_to_mothership()
        elif self.unit.next_target:
            self.unit.target = self.unit.next_target
            max_payload = SUFFICIENT_PAYLOAD - self.unit.payload
            self.unit.make_route(max_payload)
            self.unit.move_at(self.unit.target)
        else:
            try:
                self.unit.intercept_asteroid()
            except CantInterceptException:
                self.unit.move_to_the_closest_asteroid()

    def make_route(self, max_payload):
        if self.unit.target.payload < max_payload:
            self.unit.next_target = self.unit.get_next_asteroid()
            if self.unit.next_target:
                self.unit.__class__.unavailable_asteroids.append(self.unit.next_target)
        else:
            self.unit.next_target = None

    def try_to_depart(self):
        """Отправление с базы"""
        self.unit.move_to_the_closest_asteroid()
        if self.unit.target == self.unit.my_mothership:
            self.unit.waiting = True

    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        self.unit.target = self.unit.get_the_closest_asteroid()
        if self.unit.target:
            self.unit.__class__.unavailable_asteroids.append(self.unit.target)
            self.unit.make_route(SUFFICIENT_PAYLOAD)
            self.unit.move_at(self.unit.target)
        else:
            self.unit.target = self.unit.my_mothership
            if self.unit.near(self.unit.my_mothership):
                self.unit.waiting = True
            else:
                self.unit.move_at(self.unit.target)

    def intercept_asteroid(self):
        """
        Попытка перехватить цель у другого дрона,
        если этот дрон находится ближе к цели.
        """
        distances = {}
        for asteroid in self.unit.__class__.unavailable_asteroids:
            distance = self.unit.distance_to(asteroid)
            for drone in self.unit.teammates:
                if drone.target == asteroid and drone.distance_to(asteroid) > distance:
                    distances[asteroid] = [drone, distance]
        for asteroid, drone_distance_pair in distances.items():
            closest_drone = min(distances.values(), key=lambda x: x[1])
            if drone_distance_pair == closest_drone:
                self.unit.previous_target = Point(self.unit.x, self.unit.y)
                self.unit.__class__.unavailable_asteroids.remove(asteroid)
                self.unit.move_to_the_closest_asteroid()
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

        distances = self.get_distances()

        for drone in self.unit.scene.drones:
            if self.unit.target and drone.target:
                distance_to_target = self.unit.target.distance_to(drone.target)
                self.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)

        distances_to_rich = [
            asteroid_distance_pair for asteroid_distance_pair in distances
            if asteroid_distance_pair[0].payload >= SUFFICIENT_PAYLOAD]

        if distances_to_rich:
            return (min(distances_to_rich, key=lambda x: x[1]))[0]
        elif distances:
            return (min(distances, key=lambda x: x[1]))[0]

    def get_next_asteroid(self):
        """Выбрать ближайший к текущей цели астероид"""
        distances = self.get_distances()

        for drone in self.unit.scene.drones:
            if self.unit.target and drone.target:
                distance_to_target = self.unit.distance_to(self.unit.target) + self.unit.target.distance_to(
                    drone.target)
                self.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)

        if distances:
            return (min(distances, key=lambda x: x[1]))[0]

    def get_distances(self):
        distances_to_asteroids = [(asteroid, self.unit.distance_to(asteroid)) for asteroid in self.unit.asteroids
                                  if asteroid not in self.unit.__class__.unavailable_asteroids]

        distances_to_dead_enemies = [(drone, self.unit.distance_to(drone)) for drone in self.unit.scene.drones
                                     if
                                     drone not in self.unit.__class__.my_team and not drone.is_alive and not drone.is_empty]

        distances_to_motherships = [(base, self.unit.distance_to(base)) for base in self.unit.scene.motherships
                                    if base != self.unit.my_mothership and not base.is_alive and not base.is_empty]

        return distances_to_asteroids + distances_to_dead_enemies + distances_to_motherships

    def remove_asteroid_occupied_by_enemy(self, drone, distance_to_target, distances):
        if drone not in self.unit.__class__.my_team and drone.distance_to(drone.target) < distance_to_target:
            for asteroid_distance_pair in distances:
                if asteroid_distance_pair[0] == drone.target:
                    distances.remove(asteroid_distance_pair)
                    break
