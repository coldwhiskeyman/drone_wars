from random import choice

from astrobox.core import Drone, Asteroid, MotherShip
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
        self.offensive = True
        self.attacking = False
        self.maneuvering = False
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
            # if self.check_for_enemy_drones():  # защита базы, при приближении вражеских дронов
            #     self.go_to_defense_position()
            if len(self.asteroids) > len(self.unavailable_asteroids):
                self.waiting = False
                self.try_to_depart()  # отправка на добычу, при наличии свободных астероидов
            # else:
            #     for mothership in self.scene.motherships:  # атака на вражескую базу
            #         if mothership != self.my_mothership and not mothership.is_empty:
            #             self.target = mothership
            #             self.waiting = False
            #             self.offensive = True
            #             self.move_at(mothership)

        # for mothership in self.scene.motherships:  # разграбление вражеской базы
        #     if mothership != self.my_mothership and self.near(mothership):
        #         self.offensive = False
        #         self.load_from(mothership)

        if self.health <= 40:
            self.retreat()

        # if self.target in DEFENSE_POSITIONS and self.near(self.target) and not self.guarding:
        #     self.guarding = True  # режим защиты базы, после выхода на позицию
        # if self.guarding:
        #     self.guarding_mode()

        if self.offensive:
            if isinstance(self.target, MotherShip) and self.target != self.my_mothership:
                self.attack_mission()
            else:
                for mothership in self.scene.motherships:
                    if mothership != self.my_mothership and mothership.is_alive:
                        self.target = mothership

        for drone in self.scene.drones:
            if drone not in self.my_team and drone.is_alive:
                break
        else:
            for mothership in self.scene.motherships:
                if mothership != self.my_mothership and mothership.is_alive:
                    break
            else:
                self.offensive = False

        for asteroid in self.asteroids:  # проверка, не опустели ли астероиды
            if asteroid not in self.unavailable_asteroids and asteroid.payload == 0:
                self.unavailable_asteroids.append(asteroid)
        # if not self._logger.statistics_written:  # запись статистики по завершении игры
        #     for drone in [drone for drone in self.scene.drones if drone not in self.my_team]:
        #         if drone.is_alive:
        #             break
        #     else:
        #         self._logger.write_statistics()

    # def go_to_defense_position(self):
    #     """Выход на позицию для защиты базы"""
    #     for point in DEFENSE_POSITIONS:
    #         if any([drone.near(point) or drone.target == point for drone in self.teammates]):
    #             continue
    #         else:
    #             self.waiting = False
    #             self.target = point
    #             self.move_at(self.target)
    #
    # def attack_mission(self):
    #     """действия в рамках атаки на вражескую базу"""
    #     if self.attacking:
    #         self.attack_mode()
    #     elif self.maneuvering and not self.next_target:
    #         self.barrel_roll()
    #     elif self.maneuvering and not self.check_for_attacking_ally_drones():
    #         self.maneuvering = False
    #         self.next_target = None
    #     elif self.maneuvering:
    #         pass
    #     elif self.target.is_empty:
    #         self.attacking = False
    #         self.offensive = False
    #         self.move_to_mothership()
    #     else:
    #         enemy = self.check_for_enemy_drones()
    #         ally = self.check_for_attacking_ally_drones()
    #         if (enemy or self.check_target_base()) and not ally:
    #             self.attacking = True
    #             self.stop()
    #         elif (enemy or self.check_target_base()) and ally:
    #             self.maneuvering = True
    #         else:
    #             self.move_at(self.target)
    #
    # def attack_mode(self):
    #     """атака вражеских дронов или базы в радиусе поражения"""
    #     enemy = self.check_for_enemy_drones()
    #     if enemy:
    #         self.turn_to(enemy)
    #         self.gun.shot(enemy)
    #     elif self.check_target_base():
    #         self.turn_to(self.target)
    #         self.gun.shot(self.target)
    #     else:
    #         self.attacking = False
    #
    # def barrel_roll(self):
    #     self.next_target = choice(self.asteroids)
    #     self.move_at(self.next_target)
    #
    # def check_for_attacking_ally_drones(self):
    #     """проверка на союзных дронов в режиме атаки в небольшом радиусе"""
    #     for drone in self.scene.drones:
    #         if drone in self.teammates and self.distance_to(drone) <= 100 and drone.is_alive and drone.attacking:
    #             return drone
    #
    # def check_for_enemy_drones(self):
    #     """проверка на вражеских дронов в радиусе поражения"""
    #     for drone in self.scene.drones:
    #         if drone not in self.my_team and self.distance_to(drone) <= 500 and drone.is_alive:
    #             return drone
    #
    # def check_target_base(self):
    #     return self.target != self.my_mothership and self.distance_to(self.target) <= 500 and self.target.is_alive
    #
    # def guarding_mode(self):
    #     """атака вражеских дронов в радиусе поражения"""
    #     enemy = self.check_for_enemy_drones()
    #     if enemy:
    #         self.turn_to(enemy)
    #         self.gun.shot(enemy)
    #     else:
    #         self.guarding = False
    #         self.move_to_mothership()
    #
    def retreat(self):
        """бегство из боя"""
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        self.guarding = False
        self.offensive = False
        self.attacking = False
        self.maneuvering = False
        if isinstance(self.target, Asteroid) and self.target in self.unavailable_asteroids:
            self.unavailable_asteroids.remove(self.target)
        self.move_to_mothership()
