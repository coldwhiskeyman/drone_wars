from math import ceil

from astrobox.core import Drone, Asteroid
from robogame_engine.geometry import Point

SUFFICIENT_PAYLOAD = 90
DEFENSE_POSITIONS = [Point(100, 350), Point(160, 290), Point(225, 225), Point(290, 160), Point(350, 100)]


class CantInterceptException(Exception):
    pass


class PestovDrone(Drone):
    my_team = []
    unavailable_asteroids = []
    attack_distance = 1000

    def __init__(self, logger, attack_plan, **kwargs):
        super().__init__(**kwargs)
        self.attack_plan = attack_plan
        self.waiting = False
        self.offensive = True
        self.attacking = False
        self.previous_target = Point(self.x, self.y)
        self.next_target = None
        self._logger = logger

    def on_born(self):
        """Действие при активации дрона"""
        self.my_team.append(self)
        self.attack_plan.set_mothership(self.my_mothership)

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
            max_payload = SUFFICIENT_PAYLOAD - self.payload
            self.make_route(max_payload)
            self.move_at(self.target)
        else:
            try:
                self.intercept_asteroid()
            except CantInterceptException:
                self.move_to_the_closest_asteroid()

    def make_route(self, max_payload):
        if self.target.payload < max_payload:
            self.next_target = self.get_next_asteroid()
            if self.next_target:
                self.unavailable_asteroids.append(self.next_target)
        else:
            self.next_target = None

    def on_stop_at_mothership(self, mothership):
        """Действие при возвращении на базу"""
        self.turn_to(self.previous_target)  # да, бессмысленно, но главное, что развернется на ~180 градусов
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        if not self.is_empty:
            self.unload_to(mothership)
        elif self.enemies_alive():
            self.offensive = True
        else:
            self.try_to_depart()

    def on_unload_complete(self):
        """Действие при завершении разгрузки дрона"""
        if self.enemies_alive():
            self.offensive = True
        else:
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
            self.make_route(SUFFICIENT_PAYLOAD)
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

    def remove_asteroid_occupied_by_enemy(self, drone, distance_to_target, distances):
        if drone not in self.my_team and drone.distance_to(drone.target) < distance_to_target:
            for asteroid_distance_pair in distances:
                if asteroid_distance_pair[0] == drone.target:
                    distances.remove(asteroid_distance_pair)
                    break

    def game_step(self):
        super().game_step()
        if self.waiting:  # возможные действия, при ожидании на базе
            if len(self.asteroids) > len(self.unavailable_asteroids):
                self.waiting = False
                self.try_to_depart()  # отправка на добычу, при наличии свободных астероидов

        for mothership in self.scene.motherships:  # разграбление вражеской базы
            if mothership != self.my_mothership and self.near(mothership):
                self.offensive = False
                self.load_from(mothership)

        if self.health <= 40:
            self.retreat()

        if self.offensive:
            if not self.attack_plan.target_mothership:
                for mothership in self.scene.motherships:
                    if mothership != self.my_mothership:
                        self.attack_plan.start_attack(mothership)
            elif self.target not in self.attack_plan.attack_positions:
                self.attack_plan.go_to_attack_position(self)
            elif self.near(self.target) and (self.check_for_enemy_drones() or self.check_target_base()):
                self.attacking = True

            for drone in self.my_team:
                if self.target:
                    if drone.attacking or not self.near(self.target):
                        break
                else:
                    break
            else:
                self.attack_plan.advance_to_next_position()

        counter = 0
        for drone in self.my_team:
            if drone.offensive:
                counter += 1
        # if counter < ceil(float(len(self.my_team)) / 2):
        #     self.attack_plan.abort_attack()

        if not self.enemies_alive():
            self.offensive = False

        if self.attacking:
            self.attack_mode()

        for asteroid in self.asteroids:  # проверка, не опустели ли астероиды
            if asteroid not in self.unavailable_asteroids and asteroid.is_empty:
                self.unavailable_asteroids.append(asteroid)
        # if not self._logger.statistics_written:  # запись статистики по завершении игры
        #     for drone in [drone for drone in self.scene.drones if drone not in self.my_team]:
        #         if drone.is_alive:
        #             break
        #     else:
        #         self._logger.write_statistics()

    def enemies_alive(self):
        for drone in self.scene.drones:
            if drone not in self.my_team and drone.is_alive:
                return True
        else:
            for mothership in self.scene.motherships:
                if mothership != self.my_mothership and mothership.is_alive:
                    return True
            else:
                return False

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

    def check_for_enemy_drones(self):
        """проверка на вражеских дронов в радиусе поражения"""
        for drone in self.scene.drones:
            if drone not in self.my_team and self.distance_to(drone) <= self.__class__.attack_distance and drone.is_alive:
                return drone

    def check_target_base(self):
        if self.attack_plan.target_mothership:
            # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            return self.distance_to(self.attack_plan.target_mothership) <= self.__class__.attack_distance
        else:
            return False

    def retreat(self):
        """бегство из боя"""
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        self.offensive = False
        self.attacking = False
        if isinstance(self.target, Asteroid) and self.target in self.unavailable_asteroids:
            self.unavailable_asteroids.remove(self.target)
        self.move_to_mothership()
