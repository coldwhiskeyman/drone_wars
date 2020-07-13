from astrobox.core import Drone


class CantInterceptException(Exception):
    pass


class PestovDrone(Drone):
    my_team = []
    unavailable_asteroids = []

    def on_born(self):
        """Действие при активации дрона"""
        self.move_to_the_closest_asteroid()
        self.my_team.append(self)

    def on_stop_at_asteroid(self, asteroid):
        """Действие при встрече с астероидом"""
        self.load_from(asteroid)

    def on_load_complete(self):
        """Действие при завершении загрузки элериума"""
        if self.is_full:
            if self.target.payload != 0:
                self.unavailable_asteroids.remove(self.target)
            self.move_at(self.my_mothership)
        else:
            try:
                self.intercept_asteroid()
            except CantInterceptException:
                self.move_to_the_closest_asteroid()

    def on_stop_at_mothership(self, mothership):
        """Действие при возвращении на базу"""
        self.unload_to(mothership)

    def on_unload_complete(self):
        """Действие при завершении разгрузки дрона"""
        self.move_to_the_closest_asteroid()

    def on_wake_up(self):
        self.move_to_the_closest_asteroid()

    def move_to_the_closest_asteroid(self):
        """Двигаться к ближайшему астероиду"""
        self.target = self.get_the_closest_asteroid()
        self.unavailable_asteroids.append(self.target)
        if self.target:
            self.move_at(self.target)
        else:
            self.move_at(self.my_mothership)

    def intercept_asteroid(self):
        """
        Попытка перехватить цель у другого дрона,
        если этот дрон находится ближе к цели.
        """
        distances = {}
        for asteroid in self.unavailable_asteroids:
            if asteroid:  # очень кривая попытка избежать ошибки
                # иногда в список попадает None, непонятно как.
                distance = self.distance_to(asteroid)
                for drone in self.my_team:
                    if drone != self and drone.target == asteroid:
                        if drone.distance_to(asteroid) > distance:
                            distances[asteroid] = [drone, distance]
        for asteroid, data in distances.items():
            if data == min(distances.values(), key=lambda x: x[1]):
                self.unavailable_asteroids.remove(asteroid)
                self.move_to_the_closest_asteroid()
                data[0].move_to_the_closest_asteroid()
                break
        else:
            raise CantInterceptException

    def get_the_closest_asteroid(self):
        """Выбор ближайшего к дрону астероида"""
        distances = {}
        for asteroid in self.asteroids:
            if asteroid not in self.unavailable_asteroids:
                distance = self.distance_to(asteroid)
                distances[asteroid] = distance
        for asteroid, distance in distances.items():
            if distance == min(distances.values()):
                return asteroid
