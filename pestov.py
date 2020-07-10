from astrobox.core import Drone


class NostromoDrone(Drone):
    my_team = []

    def on_born(self):
        self.target = self.get_the_closest_asteroid()
        self.move_at(self.target)
        self.my_team.append(self)

    def on_stop_at_asteroid(self, asteroid):
        self.load_from(asteroid)

    def on_load_complete(self):
        if self.is_full:
            self.move_at(self.my_mothership)
        else:
            self.target = self.get_the_closest_asteroid()
            if self.target:
                self.move_at(self.target)
            else:
                self.move_at(self.my_mothership)

    def on_stop_at_mothership(self, mothership):
        self.unload_to(mothership)

    def on_unload_complete(self):
        self.target = self.get_the_closest_asteroid()
        # TODO - Здесь ругается на ошибку (видимо нет подходящих астеройдов) в конце игры
        self.move_at(self.target)

    def on_wake_up(self):
        self.target = self.get_the_closest_asteroid()
        if self.target:
            self.move_at(self.target)

    def get_the_closest_asteroid(self):
        distances = {}
        for asteroid in self.asteroids:
            if asteroid.payload != 0:
                distance = self.distance_to(asteroid)
                distances[asteroid] = distance
        for asteroid, distance in distances.items():
            if distance == min(distances.values()):
                return asteroid
