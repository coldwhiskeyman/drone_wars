from astrobox.space_field import SpaceField
from stage_03_harvesters.reaper import ReaperDrone
from stage_03_harvesters.driller import DrillerDrone
from stage_04_soldiers.devastator import DevastatorDrone
from pestov import PestovDrone

NUMBER_OF_DRONES = 5


if __name__ == '__main__':
    scene = SpaceField(
        field=(1200, 900),
        speed=5,
        asteroids_count=17,
        can_fight=True,
    )

    team_1 = [PestovDrone() for _ in range(NUMBER_OF_DRONES)]
    team_2 = [ReaperDrone() for _ in range(NUMBER_OF_DRONES)]
    team_3 = [DrillerDrone() for _ in range(NUMBER_OF_DRONES)]
    team_4 = [DevastatorDrone() for _ in range(NUMBER_OF_DRONES)]

    scene.go()
