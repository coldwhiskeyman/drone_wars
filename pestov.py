from math import ceil

from astrobox.core import Drone, Asteroid
from robogame_engine.geometry import Point

from attack_plan import AttackPlan
from roles import Fighter, Harvester, Guardian

FIGHTER = 'fighter'
HARVESTER = 'harvester'
GUARDIAN = 'guardian'


class RoleError(Exception):
    pass


class PestovDrone(Drone):
    my_team = []
    fighters = []
    harvesters = []
    guardians = []
    unavailable_asteroids = []
    attack_plan = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.role = None
        self.waiting = False
        self.offensive = False
        self.attacking = False
        self.previous_target = Point(self.x, self.y)
        self.next_target = None

    def on_born(self):
        """Действие при активации дрона"""
        self.__class__.my_team.append(self)
        if len(self.scene.motherships) == 4 and not self.__class__.harvesters:
            self.change_role(HARVESTER)
        else:
            self.change_role(FIGHTER)
        self.register_drone()
        self.attack_plan.set_mothership(self.my_mothership)

    def register_drone(self):
        if self.__class__.attack_plan is None:
            self.__class__.attack_plan = AttackPlan()
        self.attack_plan = self.__class__.attack_plan

    def change_role(self, role):
        if role == 'fighter':
            self.role = Fighter(self)
            self.offensive = True
            self.waiting = False
            if self in self.__class__.harvesters:
                self.__class__.harvesters.remove(self)
            elif self in self.__class__.guardians:
                self.__class__.guardians.remove(self)
            self.__class__.fighters.append(self)
        elif role == 'harvester':
            self.role = Harvester(self)
            self.offensive = False
            self.waiting = True
            if self in self.__class__.fighters:
                self.__class__.fighters.remove(self)
            elif self in self.__class__.guardians:
                self.__class__.guardians.remove(self)
            self.__class__.harvesters.append(self)
        elif role == 'guardian':
            self.role = Guardian(self)
            self.offensive = False
            self.waiting = False
            if self in self.__class__.harvesters:
                self.__class__.harvesters.remove(self)
            elif self in self.__class__.fighters:
                self.__class__.fighters.remove(self)
            self.__class__.guardians.append(self)

    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        if isinstance(self.role, Harvester):
            self.role.on_stop_at_asteroid(asteroid)

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if isinstance(self.role, Harvester):
            self.role.on_load_complete()

    def on_stop_at_mothership(self, mothership):
        """Действие при возвращении на базу"""
        self.turn_to(self.previous_target)  # да, бессмысленно, но главное, что развернется на ~180 градусов
        self.previous_target = Point(self.x, self.y)
        if isinstance(self.role, Harvester):
            if not self.is_empty:
                self.unload_to(mothership)
            else:
                self.try_to_depart()
        elif isinstance(self.role, Fighter):
            if self.enemies_alive():
                self.offensive = True
            else:
                self.change_role(HARVESTER)
        elif isinstance(self.role, Guardian):
            if self.enemies_alive():
                self.attack_plan.go_to_defense_position(self)
            else:
                self.change_role(HARVESTER)

    def on_unload_complete(self):
        """Действие при завершении разгрузки дрона"""
        if isinstance(self.role, Harvester):
            self.try_to_depart()

    def try_to_depart(self):
        """Отправление с базы"""
        if isinstance(self.role, Harvester):
            self.role.try_to_depart()
        else:
            raise RoleError('try_to_depart: Только сборщик может собирать ресурсы')

    def on_wake_up(self):
        return

    def move_to_mothership(self):
        """Двигаться на базу"""
        self.target = self.my_mothership
        self.next_target = None
        self.move_at(self.target)

    def game_step(self):
        super().game_step()

        if not self.is_alive:
            self.role = None
            if self in self.__class__.harvesters:
                self.__class__.harvesters.remove(self)
            elif self in self.__class__.fighters:
                self.__class__.fighters.remove(self)
            elif self in self.__class__.guardians:
                self.__class__.guardians.remove(self)

        for asteroid in self.asteroids:  # проверка, не опустели ли астероиды
            if asteroid not in self.__class__.unavailable_asteroids and asteroid.is_empty:
                self.__class__.unavailable_asteroids.append(asteroid)

        if self.health <= 50:
            self.retreat()

        if isinstance(self.role, Harvester):

            if self.waiting:  # возможные действия, при ожидании на базе
                if len(self.asteroids) > len(self.__class__.unavailable_asteroids):
                    self.waiting = False
                    self.try_to_depart()  # отправка на добычу, при наличии свободных астероидов

            for mothership in self.scene.motherships:
                if mothership != self.my_mothership and self.near(mothership):
                    self.load_from(mothership)

            for drone in self.scene.drones:
                if drone not in self.my_team and self.near(drone) and not drone.is_alive:
                    self.load_from(drone)

            if self.count_dead() >= 3 and self.count_enemies() >= 5 - self.count_dead():
                self.change_role(GUARDIAN)
                self.retreat()

        elif isinstance(self.role, Fighter) and not isinstance(self.role, Guardian):
            if self.offensive:
                if not self.attack_plan.target_mothership:
                    for mothership in self.scene.motherships:
                        if mothership != self.my_mothership:
                            if len([base for base in self.scene.motherships if base.is_alive]) > 2 and (
                                    mothership.x == self.my_mothership.x or mothership.y == self.my_mothership.y):
                                self.attack_plan.start_attack(mothership)
                elif self.target not in self.attack_plan.attack_positions or not self.near(self.target):
                    self.attack_plan.go_to_attack_position(self)
                elif any([self.near(point) for point in self.attack_plan.attack_positions]) and (
                        self.check_for_enemy_drones() or self.check_target_base()):
                    self.attacking = True

                for drone in self.__class__.fighters:
                    if self.target:
                        if drone.attacking or not self.near(self.target):
                            break
                    else:
                        break
                else:
                    self.attack_plan.advance_to_next_position()
            else:
                if self.health == 100:
                    self.offensive = True
                elif not self.is_moving and self.health >= 80:
                    self.offensive = True
                else:
                    self.move_to_mothership()

            if not self.attack_plan.target_mothership and all(
                    [drone.health >= 80 for drone in self.__class__.fighters]):
                for mothership in self.scene.motherships:
                    if mothership != self.my_mothership:
                        self.attack_plan.start_attack(mothership)
            elif self.attack_plan.target_mothership:
                counter = 0
                for drone in self.__class__.fighters:
                    if drone.offensive:
                        counter += 1
                if counter < ceil(float(len(self.__class__.fighters)) / 2):
                    self.attack_plan.abort_attack(self.__class__.fighters)

            if self.attacking:
                self.attack_mode()

            # if not self.is_moving and self.target:
            #     if self.near(self.target) and self.offensive:
            #         pass
            #     elif self.near(self.target):
            #         self.offensive = True
            #     elif self.near(self.my_mothership) or self.health >= 80:
            #         self.offensive = True
            #         self.attack_plan.go_to_attack_position(self)
            #     else:
            #         self.move_to_mothership()

            if self.count_dead() >= 3 and self.count_enemies() >= 5 - self.count_dead():
                self.change_role(GUARDIAN)
                self.retreat()

            elif not self.enemies_alive():
                self.change_role(HARVESTER)

        elif isinstance(self.role, Guardian):
            if self.target not in self.attack_plan.defense_positions or not self.near(self.target) and self.health >= 80:
                self.attack_plan.go_to_defense_position(self)
            elif self.near(self.target):
                self.attacking = True

            if self.attacking:
                self.attack_mode()

            if not self.enemies_alive():
                self.change_role(HARVESTER)
            elif self.count_enemies() < 5 - self.count_dead():
                self.change_role(FIGHTER)

    def count_enemies(self):
        count = 0
        for drone in self.scene.drones:
            if drone not in self.__class__.my_team and drone.is_alive:
                count += 1
        return count

    def count_dead(self):
        count = 0
        for drone in self.scene.drones:
            if isinstance(drone, PestovDrone) and not drone.is_alive:
                count += 1
        return count

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
        if isinstance(self.role, (Fighter, Guardian)):
            self.role.attack_mode()
        else:
            raise RoleError('attack_mode: Только истребитель может участвовать в бою')

    def check_for_enemy_drones(self):
        """проверка на вражеских дронов в радиусе поражения"""
        if isinstance(self.role, (Fighter, Guardian)):
            return self.role.check_for_enemy_drones()
        else:
            raise RoleError('check_for_enemy_drones: Только истребитель может участвовать в бою')

    def check_target_base(self):
        if isinstance(self.role, (Fighter, Guardian)):
            return self.role.check_target_base()
        else:
            raise RoleError('check_target_base: Только истребитель может участвовать в бою')

    def retreat(self):
        """бегство из боя"""
        self.previous_target = Point(self.x, self.y)
        self.offensive = False
        self.attacking = False
        if isinstance(self.target, Asteroid) and self.target in self.__class__.unavailable_asteroids:
            self.__class__.unavailable_asteroids.remove(self.target)
        self.move_to_mothership()
