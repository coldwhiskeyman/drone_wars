from math import ceil

from astrobox.core import Drone, Asteroid
from robogame_engine.geometry import Point

from roles import Fighter, Harvester

SUFFICIENT_PAYLOAD = 90


class RoleError(Exception):
    pass


class PestovDrone(Drone):
    my_team = []
    fighters = []
    harvesters = []
    unavailable_asteroids = []

    def __init__(self, logger, attack_plan, **kwargs):
        super().__init__(**kwargs)
        self.role = None
        self.attack_plan = attack_plan
        self.waiting = False
        self.offensive = False
        self.attacking = False
        self.previous_target = Point(self.x, self.y)
        self.next_target = None
        self._logger = logger

    def on_born(self):
        """Действие при активации дрона"""
        self.__class__.my_team.append(self)
        self.change_role('fighter')
        self.attack_plan.set_mothership(self.my_mothership)

    def change_role(self, role):
        if role == 'fighter':
            self.role = Fighter(self)
            self.offensive = True
            if self in self.__class__.harvesters:
                self.__class__.harvesters.remove(self)
            self.__class__.fighters.append(self)
        elif role == 'harvester':
            self.role = Harvester(self)
            self.offensive = False
            if self in self.__class__.fighters:
                self.__class__.fighters.remove(self)
            self.__class__.harvesters.append(self)

    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        if isinstance(self.role, Harvester):
            self.role.on_stop_at_asteroid(asteroid)
        else:
            pass

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if isinstance(self.role, Harvester):
            self.role.on_load_complete()
        else:
            raise RoleError('on_load_complete: Только сборщик может собирать ресурсы')

    def make_route(self, max_payload):
        if isinstance(self.role, Harvester):
            self.role.make_route(max_payload)
        else:
            raise RoleError('make_route: Только сборщик может собирать ресурсы')

    def on_stop_at_mothership(self, mothership):
        """Действие при возвращении на базу"""
        self.turn_to(self.previous_target)  # да, бессмысленно, но главное, что развернется на ~180 градусов
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        if isinstance(self.role, Harvester):
            if not self.is_empty:
                self.unload_to(mothership)
            else:
                self.try_to_depart()
        elif self.role == Fighter:
            if self.enemies_alive():
                self.offensive = True

    def on_unload_complete(self):
        """Действие при завершении разгрузки дрона"""
        if isinstance(self.role, Harvester):
            self.try_to_depart()
        else:
            raise RoleError('on_unload_complete: Только сборщик может собирать ресурсы')

    def try_to_depart(self):
        """Отправление с базы"""
        if isinstance(self.role, Harvester):
            self.role.try_to_depart()
        else:
            raise RoleError('try_to_depart: Только сборщик может собирать ресурсы')

    def on_wake_up(self):
        self.move_to_the_closest_asteroid()

    def move_to_mothership(self):
        """Двигаться на базу"""
        self.target = self.my_mothership
        self.next_target = None
        self.move_at(self.target)

    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        if isinstance(self.role, Harvester):
            self.role.move_to_the_closest_asteroid()
        else:
            raise RoleError('move_to_the_closest_asteroid: Только сборщик может собирать ресурсы')

    def intercept_asteroid(self):
        """
        Попытка перехватить цель у другого дрона,
        если этот дрон находится ближе к цели.
        """
        if isinstance(self.role, Harvester):
            self.role.intercept_asteroid()
        else:
            raise RoleError('intercept_asteroid: Только сборщик может собирать ресурсы')

    def get_the_closest_asteroid(self):
        """
        Выбор ближайшего к дрону астероида.
        В первую очередь выбираются богатые элериумом астероиды.
        """
        if isinstance(self.role, Harvester):
            self.role.get_the_closest_asteroid()
        else:
            raise RoleError('get_the_closest_asteroid: Только сборщик может собирать ресурсы')

    def get_next_asteroid(self):
        """Выбрать ближайший к текущей цели астероид"""
        if isinstance(self.role, Harvester):
            self.role.get_next_asteroid()
        else:
            raise RoleError('get_next_asteroid: Только сборщик может собирать ресурсы')

    def remove_asteroid_occupied_by_enemy(self, drone, distance_to_target, distances):
        if isinstance(self.role, Harvester):
            self.role.remove_asteroid_occupied_by_enemy(drone, distance_to_target, distances)
        else:
            raise RoleError('remove_asteroid_occupied_by_enemy: Только сборщик может собирать ресурсы')

    def game_step(self):
        super().game_step()

        if not self.is_alive:
            if self in self.__class__.harvesters:
                self.__class__.harvesters.remove(self)
            elif self in self.__class__.fighters:
                self.__class__.fighters.remove(self)

        for asteroid in self.asteroids:  # проверка, не опустели ли астероиды
            if asteroid not in self.__class__.unavailable_asteroids and asteroid.is_empty:
                self.__class__.unavailable_asteroids.append(asteroid)

        if self.health <= 40:
            self.retreat()

        if isinstance(self.role, Harvester):

            if self.waiting:  # возможные действия, при ожидании на базе
                if len(self.asteroids) > len(self.__class__.unavailable_asteroids):
                    self.waiting = False
                    self.try_to_depart()  # отправка на добычу, при наличии свободных астероидов

            for mothership in self.scene.motherships:  # разграбление вражеской базы
                if mothership != self.my_mothership and self.near(mothership):
                    self.offensive = False
                    self.load_from(mothership)

        elif isinstance(self.role, Fighter):
            if self.offensive:
                if not self.attack_plan.target_mothership:
                    for mothership in self.scene.motherships:
                        if mothership != self.my_mothership:
                            self.attack_plan.start_attack(mothership)
                elif self.target not in self.attack_plan.attack_positions:
                    self.attack_plan.go_to_attack_position(self)
                elif self.near(self.target) and (self.check_for_enemy_drones() or self.check_target_base()):
                    self.attacking = True

                for drone in self.__class__.fighters:
                    if self.target:
                        if drone.attacking or not self.near(self.target):
                            break
                    else:
                        break
                else:
                    self.attack_plan.advance_to_next_position()

            counter = 0
            for drone in self.__class__.my_team:
                if drone.offensive:
                    counter += 1
            if counter < ceil(float(len(self.__class__.my_team)) / 2):
                self.attack_plan.abort_attack()

            if not self.enemies_alive():
                self.change_role('harvester')

            if self.attacking:
                self.attack_mode()

        # if not self._logger.statistics_written:  # запись статистики по завершении игры
        #     for drone in [drone for drone in self.scene.drones if drone not in self.my_team]:
        #         if drone.is_alive:
        #             break
        #     else:
        #         self._logger.write_statistics()

    def enemies_alive(self):
        for drone in self.scene.drones:
            if drone not in self.__class__.my_team and drone.is_alive:
                return True
        else:
            for mothership in self.scene.motherships:
                if mothership != self.my_mothership and mothership.is_alive:
                    return True
            else:
                return False

    def attack_mode(self):
        """атака вражеских дронов или базы в радиусе поражения"""
        if isinstance(self.role, Fighter):
            self.role.attack_mode()
        else:
            raise RoleError('attack_mode: Только истребитель может участвовать в бою')

    def check_for_enemy_drones(self):
        """проверка на вражеских дронов в радиусе поражения"""
        if isinstance(self.role, Fighter):
            self.role.check_for_enemy_drones()
        else:
            raise RoleError('check_for_enemy_drones: Только истребитель может участвовать в бою')

    def check_target_base(self):
        if isinstance(self.role, Fighter):
            self.role.check_target_base()
        else:
            raise RoleError('check_target_base: Только истребитель может участвовать в бою')

    def retreat(self):
        """бегство из боя"""
        self._logger.log_route(self)
        self.previous_target = Point(self.x, self.y)
        self.offensive = False
        self.attacking = False
        if isinstance(self.target, Asteroid) and self.target in self.__class__.unavailable_asteroids:
            self.__class__.unavailable_asteroids.remove(self.target)
        self.move_to_mothership()
