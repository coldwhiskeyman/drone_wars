from math import ceil

from robogame_engine.geometry import Point, Vector, normalise_angle


class AttackPlan:
    def __init__(self, my_mothership):
        self.my_mothership = my_mothership
        self.target_mothership = None
        self.attack_stage = 0
        self.stages_number = 0
        self.attack_positions = []
        self.advance_distance = None

    def go_to_attack_position(self, soldier):
        """выход на позицию для атаки"""
        for point in self.attack_positions:
            if any([drone.near(point) or drone.target == point for drone in soldier.teammates]):
                continue
            else:
                soldier.waiting = False
                soldier.target = point
                soldier.move_at(soldier.target)

    def calculate_attack_stages(self):
        """расчет количества этапов наступления"""
        distance = self.my_mothership.distance_to(self.target_mothership)
        stages = int(ceil(distance / 500))
        x = (self.target_mothership.x - self.my_mothership.x) / stages
        y = (self.target_mothership.y - self.my_mothership.y) / stages
        self.advance_distance = Vector(x, y)
        self.stages_number = stages

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
            self.attack_positions.append(point1)
            point2 = Point(central_position.x + (wing_vector * 2).x, central_position.y + (wing_vector * 2).y)
            self.attack_positions.append(point2)

    def advance_to_next_position(self):
        """продолжение наступления"""
        self.attack_stage += 1
        self.create_attack_positions()
