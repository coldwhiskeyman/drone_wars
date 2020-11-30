from math import ceil

from robogame_engine.geometry import Point, Vector, normalise_angle


class AttackPlan:

    def __init__(self):
        self.my_mothership = None
        self.mothership_position_coefficients = None
        self.target_mothership = None
        self.attack_stage = 0
        self.attack_positions = []
        self.defense_positions = []
        self.advance_distance = None

    def set_mothership(self, mothership):
        """Привязка материнского корабля"""
        if not self.my_mothership:
            self.my_mothership = mothership
            self.mothership_position_coefficients = self.check_base_position()
            self.create_defense_positions()

    def start_attack(self, target_mothership):
        """Инициализация наступления на вражескую базу"""
        self.target_mothership = target_mothership
        self.calculate_attack_stages()
        self.create_attack_positions()

    def go_to_attack_position(self, soldier):
        """Отправка дрона на позицию для атаки"""
        if self.attack_positions:
            index = soldier.__class__.fighters.index(soldier)
            soldier.target = self.attack_positions[index]
            soldier.move_at(soldier.target)

    def go_to_defense_position(self, soldier):
        """Отправка дрона на позицию для обороны"""
        if self.defense_positions:
            index = soldier.__class__.guardians.index(soldier)
            soldier.target = self.defense_positions[index]
            soldier.move_at(soldier.target)

    def check_base_position(self):
        """Проверка расположения материнского корабля на поле боя"""
        if self.my_mothership.x == 90:
            if self.my_mothership.y == 90:
                return 1, 1
            else:
                return 1, -1
        else:
            if self.my_mothership.y == 90:
                return -1, 1
            else:
                return -1, -1

    def create_defense_positions(self):
        """создание позиций для обороны"""
        point = Point(self.my_mothership.x + (150 * self.mothership_position_coefficients[0]),
                      self.my_mothership.y + (50 * self.mothership_position_coefficients[1]))
        self.defense_positions.append(point)
        point = Point(self.my_mothership.x + (50 * self.mothership_position_coefficients[0]),
                      self.my_mothership.y + (150 * self.mothership_position_coefficients[1]))
        self.defense_positions.append(point)

    def calculate_attack_stages(self):
        """расчет количества этапов наступления"""
        distance = self.my_mothership.distance_to(self.target_mothership)
        stages = int(ceil(distance / 400))
        x = (self.target_mothership.x - self.my_mothership.x) / stages
        y = (self.target_mothership.y - self.my_mothership.y) / stages
        self.advance_distance = Vector(x, y)

    def create_attack_positions(self):
        """создание позиций для атаки"""
        self.attack_positions = []
        main_vector = self.advance_distance * (self.attack_stage + 1)
        central_position = Point(self.my_mothership.x + main_vector.x, self.my_mothership.y + main_vector.y)
        self.attack_positions.append(central_position)

        for angle in [-90, 90]:
            wing_angle = normalise_angle(main_vector.direction + angle)
            wing_vector = Vector.from_direction(wing_angle, 100)
            point1 = Point(central_position.x + wing_vector.x, central_position.y + wing_vector.y)
            if not 0 <= point1.x <= 1200 or not 0 <= point1.y <= 1200:
                point1 = self.rebase_drone_in_formation(point1, wing_vector)
            self.attack_positions.append(point1)
            point2 = Point(central_position.x + (wing_vector * 2).x, central_position.y + (wing_vector * 2).y)
            if not 0 <= point2.x <= 1200 or not 0 <= point2.y <= 1200:
                point2 = self.rebase_drone_in_formation(point2, wing_vector)
            self.attack_positions.append(point2)

    @staticmethod
    def rebase_drone_in_formation(point, vector):
        """Перерасчет позиции в звене, если дрон выходит за пределы поля боя"""
        return Point(point.x - vector.x * 5, point.y - vector.y * 5)

    def advance_to_next_position(self):
        """продолжение наступления"""
        self.attack_stage += 1
        self.create_attack_positions()

    def abort_attack(self, fighters):
        """Переход в отступление"""
        self.target_mothership = None
        self.attack_stage = 0
        self.attack_positions = []
        self.advance_distance = None
        for drone in fighters:
            if drone.offensive:
                drone.retreat()
