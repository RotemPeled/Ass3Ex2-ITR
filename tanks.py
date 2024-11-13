import os
import random
import pygame
from math import sin, cos, radians,sqrt
from abc import ABC, abstractmethod
from typing import List, Tuple
import sys
import os
import importlib.util
import inspect
import logging
import os


PLAY_MUSIC=False
PLAY_SOUNDS=False
SPLIT_TO_TEAMS=False

# Game Constants
MUSIC_VOLUME_REGULAR=0.4
MUSIC_VOLUME_WHILE_THERE_IS_SPEECH=0.10
WIDTH, HEIGHT = 1200, 800
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
TREE_RADIUS = 20
TANK_SIZE = (50, 35)
BULLET_SPEED = 4
BULLET_RADIUS = 5
FPS = 60
GAME_STEPS = 5000
TANK_SPEED=1
NUM_OF_TREES=25
BULLET_HIT_HEALTH_DECREASE=5
INITIAL_TANK_HEALTH=100
GAME_SPEED=1
INCLUDE_ONLY_NON_CPU_TANKS=False

ORANGE = (255, 165, 0)  # RGB color for orange

SUPER_BULLET_SPEED = 7  # Faster than the regular bullet
SUPER_BULLET_RADIUS = 7
SUPER_BULLET_DAMAGE = 10  # Higher damage than the regular bullet
SUPER_BULLET_COOLDOWN = 5000  # Cooldown in milliseconds (5 seconds)

# Tank Actions
TURN_LEFT = "TURN_LEFT"
TURN_RIGHT = "TURN_RIGHT"
MOVE_FORWARD = "MOVE_FORWARD"
MOVE_BACKWARD = "MOVE_BACKWARD"
SHOOT = "SHOOT"
SHOOT_SUPER = "SHOOT_SUPER"

gameEventsToReport=[]


pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Tanks competition")

# Button Constants
BUTTON_WIDTH = 100
BUTTON_HEIGHT = 50
BUTTON_PADDING = 10

# Button colors
BUTTON_BG_COLOR = WHITE
BUTTON_TEXT_COLOR = BLACK


SCREEN_MARGIN=0
tankIdFont = pygame.font.Font(None, 20)
leaderboardFont = pygame.font.Font(None, 24)
    
def normalize_angle(angle: float) -> float:
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle

import hashlib

def string_to_bool(s):
    # Create a new SHA256 hash object
    hasher = hashlib.sha256()

    # Feed the string into the hash object
    hasher.update(s.encode())

    # Get the hash digest as an integer
    hash_value = int(hasher.hexdigest(), 16)

    # Return True if the hash value is even, False if it's odd
    return hash_value % 2 == 0


# Helper Functions
def get_random_position():
    x = random.randint(TREE_RADIUS+SCREEN_MARGIN, WIDTH - TREE_RADIUS-SCREEN_MARGIN)
    y = random.randint(TREE_RADIUS+SCREEN_MARGIN, HEIGHT - TREE_RADIUS-SCREEN_MARGIN)
    return x, y

def check_collision(position_a, position_b, radius_a, radius_b):
    x1, y1 = position_a
    x2, y2 = position_b
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) <= (radius_a + radius_b) ** 2

class GameState:
    def __init__(self, tanks, trees, bullets):
        self.tanks = tanks
        self.trees = trees
        self.bullets = bullets
        
class Entity:
    def __init__(self, position: Tuple[int, int]):
        self.position = position

class Tree(Entity):
    pass

class Bullet(Entity):
    def __init__(self, position: Tuple[int, int], angle: float, tank_id: str, is_super=False):
        super().__init__(position)
        self.angle = angle
        self.tank_id = tank_id
        self.is_super = is_super  # Indicates if it's a super bullet

class Tank(Entity):
    tank_image = pygame.transform.scale(pygame.image.load('tank.png'), TANK_SIZE)
    red_tank_image = pygame.transform.scale(pygame.image.load('tank-red.png'), TANK_SIZE)
    TANK_DESTROYED_IMAGE = pygame.transform.scale(pygame.image.load('destroyed-tank.png'), TANK_SIZE)

    def __init__(self, tank_id: str, angle: float, position):
        super().__init__(position)
        self.tank_id = tank_id
        self.angle = angle
        self.health = INITIAL_TANK_HEALTH
        self.last_shot_time = 0
        isBlue=string_to_bool(tank_id)
        
        if SPLIT_TO_TEAMS:
            if isBlue:
                self.team="Blue"
            else:
                self.team="Red"
        else:
            self.team="Blue"
        

        self.tank_id_text = tankIdFont.render(self.id, True, BLACK)
        self.last_super_shot_time = 0  # Track the last time a super bullet was shot


    @property
    def id(self) -> str:
        return self.tank_id

def find_valid_position(trees: List[Tree], tanks: List[Tank], radius: int) -> Tuple[int, int]:
    while True:
        position = get_random_position()
        tree_collision = any(check_collision(position, tree.position, radius, TREE_RADIUS) for tree in trees)
        tank_collision = any(check_collision(position, tank.position, radius, max(TANK_SIZE)) for tank in tanks)

        if not tree_collision and not tank_collision:
            return position



class TankController(ABC):
    @abstractmethod
    def decide_what_to_do_next(self, gamestate: GameState) -> str:
        pass

class Game:
    def __init__(self, tank_controllers: List[TankController], num_trees: int = NUM_OF_TREES):
        self.tank_controllers = tank_controllers
        self.tanks = self.generate_tanks(tank_controllers)
        self.bullets = []
        self.trees = self.generate_trees(num_trees)
        self.tank_controller_mapping = {}
        self.commentatorText=""

    def generate_trees(self, num_trees: int) -> List[Tree]:
        trees = []
        for _ in range(num_trees):
            position = find_valid_position(trees, self.tanks, TREE_RADIUS)
            trees.append(Tree(position))
        return trees

    def generate_tanks(self, tank_controllers: List[TankController]) -> List[Tank]:
        tanks = []
        for tank_controller in tank_controllers:
            angle = random.uniform(0, 360)
            tank_id = tank_controller.id
            position = find_valid_position([], tanks, max(TANK_SIZE))
            tank = Tank(tank_id, angle,position)
            tank.position = position
            tanks.append(tank)
        return tanks

    def run(self):
        self.should_start=True
        self.explosion_sound = pygame.mixer.Sound("medium-explosion-40472.mp3")
        pygame.mixer.music.set_volume(MUSIC_VOLUME_REGULAR)
        pygame.mixer.music.load('music.mp3')
        if PLAY_MUSIC:
            pygame.mixer.music.play(-1)
        self.game_ended=False
        clock = pygame.time.Clock()
        gameEventsToReport.clear()
        gameEventsToReport.append(f"Game is starting")
        for tank, tank_controller in zip(self.tanks, self.tank_controllers):
            self.tank_controller_mapping[tank.id] = tank_controller

        tanksStartingTheGame=[]
        for tank in self.tanks:
            tanksStartingTheGame.append(tank.id) 
        gameEventsToReport.append(f"This is a battle between {len(tanksStartingTheGame)} tanks")
        gameEventsToReport.append(f"The tanks in this battle are: {','.join(tanksStartingTheGame)}")
        
        self.scores = {tank_controller.id: 0 for tank_controller in self.tank_controllers}


        self.bullets = []
        step=0
        
        

        #Game loop
        while(True):

            handle_events(self)

            screen.fill(WHITE)
            
            if (self.should_start):

                for tree in self.trees:
                    pygame.draw.circle(screen, GREEN, tree.position, TREE_RADIUS)

                for tank in self.tanks:
                    if tank.health > 0:
                        if (tank.team=="Blue"):
                            rotated_tank_image = pygame.transform.rotate(Tank.tank_image, tank.angle)
                        else:
                            rotated_tank_image = pygame.transform.rotate(Tank.red_tank_image, tank.angle)
                    else:
                        rotated_tank_image = pygame.transform.rotate(Tank.TANK_DESTROYED_IMAGE, tank.angle)

                    # Calculate the new position of the rotated image
                    new_rect = rotated_tank_image.get_rect(center=tank.position)

                    # Draw rotated tank image
                    screen.blit(rotated_tank_image, new_rect.topleft)
                    
                    tankIdIncreaseTextDistance=0
                    if (tank.position[1]<50):
                        tankIdIncreaseTextDistance=70

                    # Start of health bar drawing code
                    if tank.health > 0:
                        pygame.draw.rect(screen, RED, pygame.Rect(tank.position[0] - TANK_SIZE[0] / 2, tank.position[1] - TANK_SIZE[1] / 2 - 10+tankIdIncreaseTextDistance, TANK_SIZE[0], 5))
                        pygame.draw.rect(screen, GREEN, pygame.Rect(tank.position[0] - TANK_SIZE[0] / 2, tank.position[1] - TANK_SIZE[1] / 2 - 10+tankIdIncreaseTextDistance, TANK_SIZE[0] * (tank.health / 100), 5))
                    # End of health bar drawing code

                    # Draw tank's id

                    
                    

                    
                    tank_id_text_rect = tank.tank_id_text.get_rect(center=(tank.position[0], tank.position[1] - TANK_SIZE[1] / 2 - 20+tankIdIncreaseTextDistance))
                    screen.blit(tank.tank_id_text, tank_id_text_rect)
                    
                    if tank.health > 0:
                        tank_controller = self.tank_controller_mapping[tank.id]
                        game_state = GameState(self.tanks, self.trees, self.bullets)
                        
                        try:
                            action = tank_controller.decide_what_to_do_next(game_state)
                            self.execute_action(tank, action)
                        except Exception as e:
                            logging.exception(f"Error when tank {tank.id} is trying to decide what to do")

                for bullet in self.bullets:
                    if bullet.is_super:
                        pygame.draw.circle(screen, ORANGE, bullet.position, SUPER_BULLET_RADIUS)
                    else:
                        pygame.draw.circle(screen, RED, bullet.position, BULLET_RADIUS)

                self.update_bullets()
                self.check_collisions()
                self.show_leaderboard(screen, self.scores)
                
                if self.commentatorText:
                    self.showCommentatorSubtitles(screen,self.commentatorText)
                # Show remaining steps
                tankIdFont = pygame.font.Font(None, 24)
                remaining_steps = GAME_STEPS - step - 1
                text = tankIdFont.render(f"Steps Remaining: {remaining_steps}", True, BLACK)
                screen.blit(text, (10, 10))
                
                

                fps = int(clock.get_fps())
                fps_text = pygame.font.SysFont("Arial", 18).render(str(fps), True, pygame.Color("green"))
                screen.blit(fps_text, (10, 60))
        
                pygame.display.flip()
                clock.tick(FPS)
                step+=1
                
                # Check if the game should end
                alive_tanks = [tank for tank in self.tanks if tank.health > 0]
                if len(alive_tanks) <= 1 or step >= GAME_STEPS:
                    self.game_ended=True
                    break


        print("Game ended")
        pygame.mixer.music.stop()
        gameEventsToReport.append(f"Battle ended")
        # Sort the dictionary by values in descending order
        sorted_scores = {k: v for k, v in sorted(self.scores.items(), key=lambda item: item[1], reverse=True)}
        winnerName = next(iter(sorted_scores))
        winnerScore = sorted_scores[winnerName]
        print(sorted_scores)
        while self.game_ended:
            
            self.showWinner(screen,winnerName,winnerScore)
            if self.commentatorText:
                    self.showCommentatorSubtitles(screen,self.commentatorText)
            handle_events(self)
            pygame.display.flip()
            clock.tick(FPS)

    def execute_action(self, tank: Tank, action: str):
        if action == TURN_LEFT:
            tank.angle += 1*GAME_SPEED
            tank.angle = normalize_angle(tank.angle)
        elif action == TURN_RIGHT:
            tank.angle -= 1*GAME_SPEED
            tank.angle = normalize_angle(tank.angle)
        elif action == MOVE_FORWARD:
            new_x = tank.position[0] + cos(radians(tank.angle)) * TANK_SPEED*GAME_SPEED
            new_y = tank.position[1] - sin(radians(tank.angle)) * TANK_SPEED*GAME_SPEED
            if not self.check_collision_with_trees((new_x, new_y)) and SCREEN_MARGIN <= new_x <= WIDTH-SCREEN_MARGIN and SCREEN_MARGIN <= new_y <= HEIGHT-SCREEN_MARGIN:
                tank.position = (new_x, new_y)
        elif action == MOVE_BACKWARD:
            new_x = tank.position[0] - cos(radians(tank.angle)) * TANK_SPEED*GAME_SPEED
            new_y = tank.position[1] + sin(radians(tank.angle)) * TANK_SPEED*GAME_SPEED
            if not self.check_collision_with_trees((new_x, new_y)) and SCREEN_MARGIN <= new_x <= WIDTH-SCREEN_MARGIN and SCREEN_MARGIN <= new_y <= HEIGHT-SCREEN_MARGIN:
                tank.position = (new_x, new_y)
        elif action == SHOOT:
            current_time = pygame.time.get_ticks()
            if current_time - tank.last_shot_time >= 1000:
                tank.last_shot_time = current_time
                # Adjust bullet's starting position
                bullet_position = (tank.position[0] + cos(radians(tank.angle)) * TANK_SIZE[0] / 2,
                                tank.position[1] - sin(radians(tank.angle)) * TANK_SIZE[1] / 2)
                self.bullets.append(Bullet(bullet_position, tank.angle, tank.id))
        elif action == SHOOT_SUPER:
            current_time = pygame.time.get_ticks()
            if current_time - tank.last_super_shot_time >= SUPER_BULLET_COOLDOWN:
                tank.last_super_shot_time = current_time
                # Create and add the super bullet to the bullets list
                bullet_position = (tank.position[0] + cos(radians(tank.angle)) * TANK_SIZE[0] / 2,
                                tank.position[1] - sin(radians(tank.angle)) * TANK_SIZE[1] / 2)
                self.bullets.append(Bullet(bullet_position, tank.angle, tank.id, is_super=True))


            
    def check_collision_with_trees(self, position):
        for tree in self.trees:
            if check_collision(position, tree.position, max(TANK_SIZE) / 2, TREE_RADIUS):
                return True
        return False

    def update_bullets(self):
        #This method replaces the bullets with bullets that are still on the screen (removes the bullets that left the screen)
        new_bullets = []
        for bullet in self.bullets:
            new_position = (bullet.position[0] + cos(radians(bullet.angle)) * BULLET_SPEED*GAME_SPEED,
                            bullet.position[1] - sin(radians(bullet.angle)) * BULLET_SPEED*GAME_SPEED)
            if 0 <= new_position[0] <= WIDTH and 0 <= new_position[1] <= HEIGHT:
                bullet.position = new_position
                new_bullets.append(bullet)
        self.bullets = new_bullets
    
    def resolve_tank_collision(self,tank_a, tank_b):
        dx = tank_a.position[0] - tank_b.position[0]
        dy = tank_a.position[1] - tank_b.position[1]
        distance = sqrt(dx * dx + dy * dy)

        overlap = (max(TANK_SIZE) - distance) / 2

        tank_a.position = (tank_a.position[0] + (overlap * dx / distance), tank_a.position[1] + (overlap * dy / distance))
        tank_b.position = (tank_b.position[0] - (overlap * dx / distance), tank_b.position[1] - (overlap * dy / distance))
    
    def check_collisions(self):
        for bullet in self.bullets.copy():  # Make a copy of the list
            bullet_radius = SUPER_BULLET_RADIUS if bullet.is_super else BULLET_RADIUS
            
            # Check collision with trees
            for tree in self.trees:
                if check_collision(bullet.position, tree.position, bullet_radius, TREE_RADIUS):
                    self.bullets.remove(bullet)
                    break

            # Check collision with tanks
            for tank in self.tanks:
                if bullet.tank_id != tank.id and check_collision(bullet.position, tank.position, bullet_radius, max(TANK_SIZE) / 2):
                    if tank.health > 0:
                        damage = SUPER_BULLET_DAMAGE if bullet.is_super else BULLET_HIT_HEALTH_DECREASE
                        tank.health -= damage
                        gameEventsToReport.append(f"Tank {tank.tank_id} got hit by a {'super' if bullet.is_super else 'regular'} bullet")
                        #Reduce the score of the tank that got hit
                        self.scores[tank.tank_id] -= 2
                        # Award points to the shooting tank for hitting a tank
                        self.scores[bullet.tank_id] += 5
                        if tank.health <= 0:
                            print(f"Tank {tank.tank_id} destroyed")
                            gameEventsToReport.append(f"Tank {tank.tank_id} got destroyed")
                            if PLAY_SOUNDS:
                                self.explosion_sound.play()
                            #Reduce the score of the tank that got destroyed
                            self.scores[tank.tank_id] -= 40
                            # Award the shooting tank additional points for destroying a tank
                            self.scores[bullet.tank_id] += 20
                        if bullet in self.bullets:
                            self.bullets.remove(bullet)
                    break






    def showWinner(self,screen,winner,winnerScore):
        font = pygame.font.Font(None, 40)
        text = font.render(f"{winner} is the winner with a score of {winnerScore} !", True, BLACK)
        screen.blit(text, (WIDTH/2-200, HEIGHT/2))
        
    def showCommentatorSubtitles(self,screen,commentatorText):
        font = pygame.font.Font(None, 22)
        text = font.render(commentatorText, True, BLACK)
        screen.blit(text, (10, HEIGHT-45))
        
    def show_leaderboard(self, screen, game_results):
        sorted_results = sorted(game_results.items(), key=lambda x: x[1], reverse=True)
        top_10_results = sorted_results[:10]  # Get only the top 10 items
        for i, (tank_id, score) in enumerate(top_10_results):
            text = leaderboardFont.render(f"{tank_id}: {score}", True, BLACK)
            screen.blit(text, (WIDTH - 220, 30 * i + 10))









def load_tank_controllers_from_directory():
    student_tank_controllers = []
    directory = "tanks-definitions"

    for file in os.listdir(directory):
        if file.endswith(".py"):
            file_path = os.path.join(directory, file)
            spec = importlib.util.spec_from_file_location("student_tank_module", file_path)
            student_tank_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(student_tank_module)

            student_tank_class = None
            tank_controller_class = None
            for name, obj in inspect.getmembers(student_tank_module):
                if inspect.isclass(obj):
                    if obj.__name__ == 'TankController':
                        tank_controller_class = obj
                    elif hasattr(obj, 'decide_what_to_do_next'):
                        student_tank_class = obj
                        break

            if student_tank_class is not None:

                student_tank_controller = student_tank_class(student_tank_class.id)
                if student_tank_controller.id.startswith('cpu') and INCLUDE_ONLY_NON_CPU_TANKS:
                    continue
                student_tank_controllers.append(student_tank_controller)

    return student_tank_controllers


def handle_events(game:Game):
    global GAME_SPEED

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()







        

def main():

    tank_controllers = load_tank_controllers_from_directory()
    game = Game(tank_controllers)
    
    game.run()

if __name__ == "__main__":
    main()
