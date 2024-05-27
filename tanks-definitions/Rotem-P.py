from tanks import TankController, MOVE_FORWARD, MOVE_BACKWARD, TURN_LEFT, TURN_RIGHT, SHOOT, SHOOT_SUPER, TANK_SIZE, GameState, Tank, normalize_angle, TREE_RADIUS, SUPER_BULLET_COOLDOWN, BULLET_HIT_HEALTH_DECREASE, INITIAL_TANK_HEALTH
from math import degrees, atan2, sqrt
import random
import time
from collections import deque
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class RotemPTankController(TankController):
    def __init__(self, tank_id: str):
        self.tank_id = tank_id
        self.target_tank = None
        self.stuck_counter = 0
        self.turn_direction = TURN_LEFT
        self.last_super_shot_time = time.time()
        self.action_queue = deque()
        self.last_health = INITIAL_TANK_HEALTH
        self.getting_hit_counter = 0

    @property
    def id(self) -> str:
        return "Rotem-P-first"

    def decide_what_to_do_next(self, gamestate: GameState) -> str:
        my_tank = next(tank for tank in gamestate.tanks if tank.id == self.id)
        
        logging.debug(f"My tank position: {my_tank.position}, health: {my_tank.health}, angle: {my_tank.angle}")
        
        # Check if tank is getting hit
        if my_tank.health < self.last_health:
            self.getting_hit_counter += 1
            logging.debug("Tank is getting hit!")
        else:
            self.getting_hit_counter = max(0, self.getting_hit_counter - 1)
        
        self.last_health = my_tank.health
        
        # If getting hit repeatedly, move forward to escape
        if self.getting_hit_counter >= 3:
            self.action_queue.append(MOVE_FORWARD)
            self.getting_hit_counter = 0
            logging.debug("Moving forward to escape being hit")
            return self.action_queue.popleft()

        if not self.target_tank or self.target_tank.health <= 0:
            self.target_tank = self.find_closest_enemy_tank(gamestate)
            logging.debug(f"New target acquired: {self.target_tank.id if self.target_tank else 'None'}")

        if self.target_tank:
            dx = self.target_tank.position[0] - my_tank.position[0]
            dy = self.target_tank.position[1] - my_tank.position[1]
            distance = sqrt(dx * dx + dy * dy)
            desired_angle = normalize_angle(degrees(atan2(-dy, dx)))
            angle_diff = normalize_angle(desired_angle - my_tank.angle)

            current_time = time.time()

            if self.stuck_counter > 0:
                self.stuck_counter -= 1
                self.action_queue.append(self.turn_direction)
                logging.debug(f"Unstuck attempt, turn direction: {self.turn_direction}")
                return self.action_queue.popleft()

            if self.is_collision_with_trees(my_tank, gamestate):
                # Try to free the tank from the tree
                self.stuck_counter = 10
                self.turn_direction = TURN_LEFT if random.random() > 0.5 else TURN_RIGHT
                self.action_queue.append(self.turn_direction)
                logging.debug("Tank is stuck on a tree, attempting to turn")
                return self.action_queue.popleft()

            if abs(angle_diff) > 5:
                self.turn_direction = self.determine_turn_direction(my_tank.angle, desired_angle)
                self.action_queue.append(self.turn_direction)
                logging.debug(f"Turning towards target, direction: {self.turn_direction}, angle_diff: {angle_diff}")
            elif distance > max(TANK_SIZE) * 4:
                self.action_queue.append(MOVE_FORWARD)
                logging.debug("Moving forward towards target")
            elif current_time - self.last_super_shot_time >= SUPER_BULLET_COOLDOWN / 1000:
                self.last_super_shot_time = current_time
                self.action_queue.append(SHOOT_SUPER)
                logging.debug("Shooting super bullet")
            elif self.clear_shot(gamestate, my_tank, self.target_tank):
                self.action_queue.append(SHOOT)
                logging.debug("Shooting regular bullet")
            else:
                self.action_queue.append(MOVE_FORWARD)
                logging.debug("Moving forward")

        if self.action_queue:
            action = self.action_queue.popleft()
            logging.debug(f"Action taken: {action}")
            return action
        else:
            logging.debug("Default action: MOVE_FORWARD")
            return MOVE_FORWARD

    def determine_turn_direction(self, current_angle, target_angle):
        angle_diff = normalize_angle(target_angle - current_angle)
        if angle_diff > 180:
            return TURN_RIGHT
        else:
            return TURN_LEFT

    def find_closest_enemy_tank(self, gamestate: GameState) -> Tank:
        my_tank = next(tank for tank in gamestate.tanks if tank.id == self.id)
        alive_enemy_tanks = [tank for tank in gamestate.tanks if tank.id != self.id and tank.health > 0]

        min_distance = float('inf')
        closest_enemy = None
        for enemy_tank in alive_enemy_tanks:
            if not self.is_tree_in_line_of_fire(my_tank, enemy_tank, gamestate):
                dx = enemy_tank.position[0] - my_tank.position[0]
                dy = enemy_tank.position[1] - my_tank.position[1]
                distance = sqrt(dx * dx + dy * dy)
                if distance < min_distance:
                    min_distance = distance
                    closest_enemy = enemy_tank

        return closest_enemy

    def clear_shot(self, gamestate, my_tank, target):
        for tree in gamestate.trees:
            if self.line_of_collision(my_tank.position, target.position, tree.position, TREE_RADIUS):
                return False
        return True

    def line_of_collision(self, start_pos, end_pos, obstacle_pos, obstacle_radius):
        x1, y1 = start_pos
        x2, y2 = end_pos
        x3, y3 = obstacle_pos
        r = obstacle_radius

        dx, dy = x2 - x1, y2 - y1
        fx, fy = x1 - x3, y1 - y3

        a = dx * dx + dy * dy
        b = 2 * (fx * dx + fy * dy)
        c = (fx * fx + fy * fy) - r * r

        discriminant = b * b - 4 * a * c
        if discriminant >= 0:
            discriminant = sqrt(discriminant)
            t1 = (-b - discriminant) / (2 * a)
            t2 = (-b + discriminant) / (2 * a)
            if 0 <= t1 <= 1 or 0 <= t2 <= 1:
                return True
        return False

    def distance(self, pos1, pos2):
        return sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def is_collision_with_trees(self, tank, gamestate):
        for tree in gamestate.trees:
            if self.distance(tank.position, tree.position) < max(TANK_SIZE) / 2 + TREE_RADIUS:
                return True
        return False

    def is_tree_in_line_of_fire(self, my_tank, enemy_tank, gamestate):
        for tree in gamestate.trees:
            if self.line_of_collision(my_tank.position, enemy_tank.position, tree.position, TREE_RADIUS):
                return True
        return False
