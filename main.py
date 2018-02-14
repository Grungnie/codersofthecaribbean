import sys
import random
import abc
import random
import json
import copy
import time

from queue import PriorityQueue
from collections import deque
import heapq

random.seed(12345)

ME = 0
ENEMY = 1

MINE = 1
MY_SHIP = 2
ENEMY_SHIP = 3
BARREL = 4
HIGH_SHIP = 5   # High probability ship location
LOW_SHIP = 6    # Low probability ship_location
CANNONBALL = 7
SOFT_CANNONBALL = 8
SHIP_RADIUS_1 = 9
SHIP_RADIUS_2 = 10

# Lay mine
NO = 0
YES = 1
MAYBE = 2

# Set these to control the cost of each modifier
CANNONBALL_COST = 200
CANNONBALL_PARTIAL_COST = 148
MINE_COST = 150
SHIP_COST = 15
MY_SHIP_COST = 15
MINE_RADII_COST = 50
SHIP_RADII_1_COST = 2
SHIP_RADII_2_COST = 1

all_set = 40
COLLISION_FASTER_COST = all_set
COLLISION_SLOWER_COST = all_set
COLLISION_STARBOARD_COST = all_set
COLLISION_PORT_COST = all_set
COLLISION_WAIT_COST = 20
COLLISION_WAIT_NO_COOLDOWN_COST = all_set

# More speed reduces the chance of been hit
WINNING_SPEED_MULTI = 2
WINNING_STRAIGHT_MULTI = 1
WINNING_EDGE_MULTI = 1.8

# This should ensure it takes the shortest route possible
BARREL_SPEED_MULTI = 1
BARREL_STRAIGHT_MULTI = 0.9

# More chance of shooting
LOSING_SPEED_MULTI = 1
LOSING_STRAIGHT_MULTI = 1.8
LOSING_EDGE_MULTI = 1.8

PLANNED_MULTI = 0.8

CLOSE_SPEED_MULTI = 2
CLOSE_STRAIGHT_MULTI = 1
CLOSE_MINE_PENALTY = 40

# Set these to control the modifiers to search for
ENABLE_MINE_RADII = False
ENABLE_CANNONBALL_MINES = True
ENABLE_SHIP_RADII_1 = True
ENABLE_SHIP_RADII_2 = True

# This is the minumum number of solutions before the nav function returns
MINIMUM_SOLUTIONS = 3


def log(info):
    print(info, file=sys.stderr, flush=True)


class Timer:
    def __init__(self):
        self.start = time.time()

    def print(self, x):
        self.now = time.time()
        log('{}: {:0.2f}'.format(x, (self.now-self.start)*10000))
        self.start = time.time()

timer = Timer()


class Game:
    def __init__(self):
        self.inputs = {}

        self.my_ships = {}
        self.enemy_ships = {}
        self.cannonballs = []
        self.barrels = []
        self.mines = {}
        self.map = Map(23, 21)
        self.graph = Graph(self.map, self)

        self.my_ship_count = None
        self.entity_count = None

    def clear_last_turn(self):
        # self.my_ships = {}
        # self.enemy_ships = {}
        self.cannonballs = []
        self.barrels = []
        # self.mines = []

        self.my_ship_count = None
        self.entity_count = None

    def get_all_inputs(self, load=False, file='data.json'):
        if load:
            self.inputs = json.load(open(file))[load]
        else:
            self.inputs['entities'] = list()

            self.inputs['my_ship_count'] = input()  # the number of remaining ships
            self.inputs['entity_count'] = input()  # the number of entities (e.g. ships, mines or cannonballs)

            #log(self.inputs['my_ship_count'])
            #log(self.inputs['entity_count'])

            for i in range(int(self.inputs['entity_count'])):
                #log('Item: {}'.format(i))
                item = input()
                #log(' '.join([str(i), item]))

                self.inputs['entities'].append(item)

                #log(self.inputs['entities'][-1])
                #log('Added')

            log(json.dumps(self.inputs))

    def update_map(self, load=False, file='data.json'):
        self.get_all_inputs(load=load, file=file)
        timer.print('inputs')

        self.clear_last_turn()
        timer.print('clear')

        self.my_ship_count = int(self.inputs['my_ship_count'])  # the number of remaining ships
        self.entity_count = int(self.inputs['entity_count'])  # the number of entities (e.g. ships, mines or cannonballs)

        self.get_entities()
        timer.print('entities')

        self.graph.refresh()
        timer.print('graph')

        self.map.update(self)
        timer.print('update')

        self.graph.remove_nodes(self)
        timer.print('nodes removed')

        self.map.determine_waypoints(self)
        timer.print('determined waypoints')


    def print_map(self,  waypoints=False):
        for i, row in enumerate(self.map.grid):
            row = ['F' if i == MY_SHIP else i for i in row]
            row = ['E' if i == ENEMY_SHIP else i for i in row]
            row = ['B' if i == BARREL else i for i in row]
            row = ['M' if i == MINE else i for i in row]
            row = ['-' if i == 0 else str(i) for i in row]
            if waypoints:
                new_row = ''
                for j, char in enumerate(row):
                    waypoint_found = False
                    for waypoint in self.map.waypoints.values():
                        if waypoint.x == j and waypoint.y == i:
                            waypoint_found = True
                    if waypoint_found:
                        new_row += 'W'
                    else:
                        new_row += char
                row = new_row

            row = ' '.join(row)
            if i % 2:
                row = ' ' + row
            log(row)

    def get_entities(self):
        seen_entities = []

        for row in self.inputs['entities']:
            #log('entity_id: {}'.format(i))

            # row = input()
            #log('row: {}'.format(row))

            entity_id, entity_type, x, y, arg_1, arg_2, arg_3, arg_4 = row.split()

            #log(' '.join([entity_id, entity_type, x, y, arg_1, arg_2, arg_3, arg_4]))

            entity_id = int(entity_id)
            x = int(x)
            y = int(y)
            arg_1 = int(arg_1)
            arg_2 = int(arg_2)
            arg_3 = int(arg_3)
            arg_4 = int(arg_4)

            if entity_type == 'SHIP' and arg_4 == 1:
                if entity_id in self.my_ships:
                    self.my_ships[entity_id].update_ship(x, y, arg_1, arg_2, arg_3)
                    seen_entities.append(entity_id)
                else:
                    self.my_ships[entity_id] = Ship(entity_id, x, y, arg_1, arg_2, arg_3, self.graph)
                    seen_entities.append(entity_id)
            elif entity_type == 'SHIP' and arg_4 == 0:
                if entity_id in self.my_ships:
                    self.enemy_ships[entity_id].update_ship(x, y, arg_1, arg_2, arg_3)
                    seen_entities.append(entity_id)
                else:
                    self.enemy_ships[entity_id] = Ship(entity_id, x, y, arg_1, arg_2, arg_3, self.graph)
                    seen_entities.append(entity_id)
            elif entity_type == 'BARREL':
                self.barrels.append(Barrel(entity_id, x, y, arg_1))
            elif entity_type == 'CANNONBALL':
                self.cannonballs.append(Cannonball(entity_id, x, y, arg_1, arg_2))
            elif entity_type == 'MINE':
                # Add any new mines, remove any mine within 5 distance if it is not in seen entities
                if entity_id not in self.mines:
                    self.mines[entity_id] = Mine(entity_id, x, y)
                    seen_entities.append(entity_id)
                else:
                    seen_entities.append(entity_id)
            else:
                log('Invalid entity type ({})'.format(entity_type))
                raise(Exception('Invalid entity type'))

        all_entities = [id for id, ship in self.my_ships.items()]
        for ship_id in all_entities:
            if ship_id not in seen_entities:
                del self.my_ships[ship_id]

        all_entities = [id for id, ship in self.enemy_ships.items()]
        for ship_id in all_entities:
            if ship_id not in seen_entities:
                del self.enemy_ships[ship_id]

        remove_ids = []
        for id, mine in self.mines.items():
            if id not in seen_entities:
                remove = False
                for ship in self.my_ships.values():
                    if ship.calculate_distance_between(mine) <= 5:
                        remove = True
                if remove:
                    remove_ids.append(id)

        for id in remove_ids:
            del self.mines[id]

        #log('{} active mines'.format(len(self.mines)))

    def apply_collisions(self):
        moves = {}
        for ship_set in [self.my_ships, self.enemy_ships]:
            for id, ship in ship_set.items():
                moves[id] = ship.str_action
        collisions = self.graph.calculate_collisions(moves, overview=True)

        for id, speed in collisions.items():
            if id in self.enemy_ships:
                if speed == 0:
                    self.enemy_ships[id].speed = 0
                if speed == 1:
                    self.enemy_ships[id].speed = 0
                    position = self.enemy_ships[id].get_neighbour(self.enemy_ships[id].rotation)

                    self.enemy_ships[id].x = position.x
                    self.enemy_ships[id].y = position.y



class Graph:
    def __init__(self, map, game):
        self.x_max = map.x
        self.y_max = map.y
        self.map = map
        self.game = game
        self.graph = {}

        self.full_cannonball_nodes = [set() for _ in range(15)]
        self.partial_cannonball_nodes = [set() for _ in range(15)]

        self.full_mine_nodes = set()
        self.partial_mine_nodes = set()

        self.full_ship_nodes = set()
        self.partial_ship_nodes = set()

        self.my_full_ship_nodes = set()
        self.my_partial_ship_nodes = set()

        self.full_mine_radii = set()
        self.partial_mine_radii = set()

        self.full_ship_radii_1 = set()
        self.partial_ship_radii_1 = set()

        self.full_ship_radii_2 = set()
        self.partial_ship_radii_2 = set()

        self._node_partials = {}
        self.compile_node_partials()

        # For each combination of x, y, direction and speed find neighbours
        for col, row_list in enumerate(self.map.grid):
            for row , corr_value in enumerate(row_list):
                for rot in range(6):
                    for spd in range(3):
                        self.graph[self.encode_node_key(row, col, rot, spd)] = self.find_neighbours(row, col, rot, spd)

    def refresh(self):
        self.full_mine_nodes.clear()
        self.partial_mine_nodes.clear()

        self.full_ship_nodes.clear()
        self.partial_ship_nodes.clear()

        self.full_mine_radii.clear()
        self.partial_mine_radii.clear()

        self.full_ship_radii_1.clear()
        self.partial_ship_radii_1.clear()

        self.full_ship_radii_2.clear()
        self.partial_ship_radii_2.clear()

        for x in range(15):
            self.full_cannonball_nodes[x].clear()
            self.partial_cannonball_nodes[x].clear()

    def find_neighbours(self, row, col, rot, spd):
        if spd == 0:
            neighbours = self.speed_0_neighbours(row, col, rot)
        elif spd == 1:
            neighbours = self.speed_1_neighbours(row, col, rot)
        elif spd == 2:
            neighbours = self.speed_2_neighbours(row, col, rot)
        else:
            raise(Exception('Speed {} is not possible'.format(spd)))
        return neighbours

    def speed_0_neighbours(self, row, col, rot):
        position = Position(row, col, rotation=rot)
        neighbours = []

        # Are both port and starboard turns possible
        for i in (self.map.abs_rotation(position.rotation + 1),
                  self.map.abs_rotation(position.rotation - 1)):
            neighbours.append(Position(position.x, position.y, i, 0))
        new_pos = position.get_neighbor(position.rotation)

        if not self.map.out_of_range(new_pos):
            new_position = position.get_neighbor(position.rotation)
            neighbours.append(Position(new_position.x, new_position.y, position.rotation, 1))

        neighbours.append(Position(row, col, rot, 0))

        return neighbours

    def speed_1_neighbours(self, row, col, rot):
        position = Position(row, col, rotation=rot)
        neighbours = []

        # For each speed 1 rotation option [+1, 0, -1] determine if it is possible
        for i in (self.map.abs_rotation(position.rotation + 1),
                  self.map.abs_rotation(position.rotation),
                  self.map.abs_rotation(position.rotation -1)):
            neighbour_position = position.get_neighbor(position.rotation)

            if not self.map.out_of_range(neighbour_position):
                neighbours.append(Position(neighbour_position.x, neighbour_position.y, i, 1))

        # Can the boat slow down from 1 to 0
        neighbours.append(Position(position.x, position.y, position.rotation, 0))

        fast_position = position.get_neighbor(position.rotation).get_neighbor(position.rotation)
        if not self.map.out_of_range(fast_position):
            neighbours.append(Position(fast_position.x, fast_position.y, position.rotation, 2))

        return neighbours

    def speed_2_neighbours(self, row, col, rot):
        position = Position(row, col, rotation=rot)
        neighbours = []

        # For each speed 1 rotation option [+1, 0, -1] determine if it is possible
        for i in (self.map.abs_rotation(position.rotation + 1),
                  self.map.abs_rotation(position.rotation),
                  self.map.abs_rotation(position.rotation -1)):
            neighbour_position = position.get_neighbor(position.rotation).get_neighbor(position.rotation)

            if not self.map.out_of_range(neighbour_position):
                neighbours.append(Position(neighbour_position.x, neighbour_position.y, i, 2))

        # Can the boat slow down from 1 to 0
        slow_position = position.get_neighbor(position.rotation)
        if not self.map.out_of_range(slow_position):
            neighbours.append(Position(slow_position.x, slow_position.y, position.rotation, 1))

        return neighbours

    @staticmethod
    def encode_node_key(x, y, r, s, w=0, wi=0):
        # xxyyrs
        return wi*10000000 + w*1000000 + x*10000 + y*100 + r*10 + s

    @staticmethod
    def decode_node_key(key):
        wi = int( key/10000000)
        w = int((key - wi*10000000) /1000000)
        x = int((key - wi*10000000 - w*1000000)/10000)
        y = int((key - wi*10000000 - w*1000000 - x*10000)/100)
        r = int((key - wi*10000000 - w*1000000 - x*10000 - y*100)/10)
        s = int( key - wi*10000000 - w*1000000 - x*10000 - y*100 - r*10)
        return wi, w, x, y, r, s

    @staticmethod
    def get_full_key(key):
        return int(key/100)*100

    def remove_nodes(self, game):
        # Cannonball - all
        deque(map(lambda cannonball: self.remove_cannonball_node(cannonball.x, cannonball.y, cannonball.impact), game.cannonballs))
        deque(map(lambda cannonball: self.remove_partial_cannonball_nodes(cannonball.x, cannonball.y, cannonball.impact), game.cannonballs))
        timer.print('cannonballs removed')

        # Mine - all
        deque(map(lambda mines: self.remove_mine_node(mines.x, mines.y), game.mines.values()))
        deque(map(lambda mines: self.remove_partial_mine_node(mines.x, mines.y), game.mines.values()))
        timer.print('mines removed')

        # Ship - Only if not in mine
        ship_nodes = [self.get_ship_nodes(ship) for ship in game.enemy_ships.values()]
        deque(map(lambda node: self.remove_ship_node(node[0], node[1]), [x for y in ship_nodes for x in y]))
        deque(map(lambda node: self.remove_partial_ship_node(node[0], node[1]), [x for y in ship_nodes for x in y]))
        timer.print('ships removed')

        # This appears to decrease the result
        # Mine Radii 1 - only if not in mine
        if ENABLE_MINE_RADII or ENABLE_CANNONBALL_MINES:
            if ENABLE_CANNONBALL_MINES:
                mines = [mine for mine in game.mines.values() for cannonball in game.cannonballs if mine.x == cannonball.x and mine.y == cannonball.y]
            else:
                mines = game.mines.values()
            nodes_2d = [self.map.neighbours(x.x, x.y, search_range=1) for x in mines]
            nodes = [y for x in nodes_2d for y in x]
            deque(map(lambda node: self.remove_mine_radii(node[0], node[1]), nodes))
            deque(map(lambda node: self.remove_partial_mine_radii(node[0], node[1]), nodes))
            timer.print('mine radii removed')

    def remove_ship_set(self, ships):
        self.my_full_ship_nodes.clear()
        self.my_partial_ship_nodes.clear()

        ship_nodes = [self.get_ship_nodes(ship) for ship in ships]
        deque(map(lambda node: self.remove_ship_node(node[0], node[1], my=True), [x for y in ship_nodes for x in y]))
        deque(map(lambda node: self.remove_partial_ship_node(node[0], node[1], my=True), [x for y in ship_nodes for x in y]))
        timer.print('ships removed')

        # Ship Radii 1 - Only if not in mine or ship (start using same decay)
        future_ship_positions = [self.clamp_position_within_bounds(self.future_ship_position(ship)) for ship in ships if self.check_distance_to_entities(ship, self.game.my_ships.values(), 5)]
        # enemy_ship_positions = [self.clamp_position_within_bounds(self.future_ship_position(ship)) for ship in game.enemy_ships.values() if self.check_distance_to_entities(ship, game.my_ships.values(), 5)]
        if ENABLE_SHIP_RADII_1:
            nodes_2d = [self.map.neighbours(x.x, x.y, search_range=1) for x in future_ship_positions]
            nodes = [y for x in nodes_2d for y in x]
            deque(map(lambda node: self.remove_full_ship_radii_1(node[0], node[1]), nodes))
            deque(map(lambda node: self.remove_partial_ship_radii_1(node[0], node[1]), nodes))
            timer.print('ship radii 1 removed')

        # This appears to decrease the result
        # Ship Radii 2 - Only if not in mine or ship (start using same decay)
        if ENABLE_SHIP_RADII_2:
            nodes_2d = [self.map.neighbours(x.x, x.y, search_range=2) for x in future_ship_positions]
            nodes = [y for x in nodes_2d for y in x]
            deque(map(lambda node: self.remove_full_ship_radii_2(node[0], node[1]), nodes))
            deque(map(lambda node: self.remove_partial_ship_radii_2(node[0], node[1]), nodes))
            timer.print('ship radii 2 removed')

    def clamp_coords_within_bounds(self, x, y):
        if x >= self.x_max:
            x = self.x_max-1
            #log('mod_x_max')
        if y >= self.y_max:
            y = self.y_max-1
            #log('mod_y_max')
        if x < 0:
            x = 0
            #log('mod_x_min')
        if y < 0:
            y = 0
            #log('mod_y_min')
        return x, y

    def clamp_position_within_bounds(self, position):

        if position.x >= self.x_max:
            position.x = self.x_max-1
            #log('mod_x_max')
        if position.y >= self.y_max:
            position.y = self.y_max-1
            #log('mod_y_max')
        if position.x < 0:
            position.x = 0
            #log('mod_x_min')
        if position.y < 0:
            position.y = 0
            #log('mod_y_min')

        return position

    def get_mine_radii(self, mines):
        return [mine.get_neighbor(i) for mine in mines for i in range(6)]

    def get_remove_radii(self, game):
        remove_radii = []
        for x in [(ship, game.my_ships.values()) for ship in game.my_ships.values()]:
            points = self.remove_ship_radius(x)
            if points is not None:
                remove_radii.append(points)

        # for x in [(ship, game.my_ships.values()) for ship in game.enemy_ships.values()]:
        #     points = self.remove_ship_radius(x)
        #     if points is not None:
        #         remove_radii.append(points)
        return remove_radii

    def get_hex_cost(self, key, t):
        full_key = int(key / 100)*100

        # Check for cannonball cost
        for test_step in [t-x for x in range(-1,0) if 14 >= t-x >= 0]:
            if full_key in self.full_cannonball_nodes[test_step]:
                return CANNONBALL_COST
            elif key in self.partial_cannonball_nodes[test_step]:
                return CANNONBALL_PARTIAL_COST

        if full_key in self.full_mine_nodes or key in self.partial_mine_nodes:
            return MINE_COST

        potential_cost = 0
        if full_key in self.full_mine_radii or key in self.partial_mine_radii:
            potential_cost = MINE_RADII_COST

        if full_key in self.full_ship_nodes or key in self.partial_ship_nodes:
            cost = SHIP_COST / (1 + t ** 2)
            if len(self.game.barrels) > 0:
                cost /= 2
            return cost if cost > potential_cost else potential_cost
        elif full_key in self.my_full_ship_nodes or key in self.my_partial_ship_nodes:
            cost = MY_SHIP_COST / (1+t**2)
            return cost if cost > potential_cost else potential_cost
        elif full_key in self.full_ship_radii_1 or key in self.partial_ship_radii_1:
            cost = SHIP_RADII_1_COST / (1+t**2)
            return cost if cost > potential_cost else potential_cost
        elif full_key in self.full_ship_radii_2 or key in self.partial_ship_radii_2:
            cost = SHIP_RADII_2_COST / (1+t**2)
            return cost if cost > potential_cost else potential_cost
        else:
            return potential_cost

    def remove_cannonball_node(self, x, y, t):
        self.full_cannonball_nodes[t].add(self.encode_node_key(x, y, 0, 0))

    def remove_partial_cannonball_nodes(self, x, y, t):
        deque(map(lambda r: self.partial_cannonball_nodes[t].update(self.node_partials(x, y, r, cannonball=True)), range(6)))

    def remove_mine_node(self, x, y):
        self.full_mine_nodes.add(self.encode_node_key(x, y, 0, 0))

    def remove_partial_mine_node(self, x, y):
        deque(map(lambda r: self.partial_mine_nodes.update(self.node_partials(x, y, r,
                    full_ignore=[self.full_mine_nodes])
                ), range(6)))

    def remove_ship_node(self, x, y, my=False):
        key = self.encode_node_key(x, y, 0, 0)
        if key not in self.full_mine_nodes:
            if my:
                self.my_full_ship_nodes.add(key)
            else:
                self.full_ship_nodes.add(key)

    def remove_partial_ship_node(self, x, y, my=False):
        if my:
            deque(map(lambda r: self.my_partial_ship_nodes.update(self.node_partials(x, y, r,
                        full_ignore=[self.full_mine_nodes, self.full_ship_nodes, self.my_full_ship_nodes],
                        partial_ignore=[self.partial_mine_nodes, self.partial_ship_nodes, self.my_partial_ship_nodes])
                    ), range(6)))
        else:
            deque(map(lambda r: self.partial_ship_nodes.update(self.node_partials(x, y, r,
                        full_ignore=[self.full_mine_nodes, self.full_ship_nodes],
                        partial_ignore=[self.partial_mine_nodes, self.partial_ship_nodes])
                    ), range(6)))

    def remove_mine_radii(self, x, y):
        key = self.encode_node_key(x, y, 0, 0)
        if key not in self.full_mine_nodes:
            self.full_mine_radii.add(key)

    def remove_partial_mine_radii(self, x, y):
        deque(map(lambda r: self.partial_mine_radii.update(self.node_partials(x, y, r,
                    full_ignore=[self.full_mine_nodes],
                    partial_ignore=[self.partial_mine_nodes])
                ), range(6)))

    def remove_partial_ship_radii_1(self, x, y):
        deque(map(lambda r: self.partial_ship_radii_1.update(self.node_partials(x, y, r,
                    full_ignore=[self.full_mine_nodes, self.full_ship_nodes],
                    partial_ignore=[self.partial_mine_nodes, self.partial_ship_nodes])
                ), range(6)))

    def remove_partial_ship_radii_2(self, x, y):
        deque(map(lambda r: self.partial_ship_radii_2.update(self.node_partials(x, y, r,
                    full_ignore=[self.full_mine_nodes, self.full_ship_nodes, self.full_ship_radii_1],
                    partial_ignore=[self.partial_mine_nodes, self.partial_ship_nodes, self.partial_ship_radii_1, self.partial_mine_radii])
                ), range(6)))

    def get_ship_nodes(self, ship, rem_forward=True, rem_port=True, rem_starboard=True):
        nodes = []

        bow = ship.get_neighbor(ship.rotation)
        stern = ship.get_neighbor(self.map.abs_rotation(ship.rotation + 3))
        mine = stern.get_neighbor(self.map.abs_rotation(ship.rotation + 3))

        nodes.append((ship.x, ship.y))
        nodes.append((bow.x, bow.y))
        nodes.append((stern.x, stern.y))

        if not self.map.out_of_range(Position(mine.x, mine.y)) and ship.id in self.game.enemy_ships:
            self.remove_mine_node(mine.x, mine.y)
            self.remove_partial_mine_node(mine.x, mine.y)

        forward_move = bow.get_neighbor(ship.rotation)
        if rem_forward:
            nodes.append((forward_move.x, forward_move.y))
            if ship.speed == 2:
                fast_move = forward_move.get_neighbor(ship.rotation)
                nodes.append((fast_move.x, fast_move.y))

        if ship.speed == 0:
            rotation_point = ship
        elif ship.speed == 1:
            rotation_point = bow
        else:
            rotation_point = forward_move

        if rem_port:
            port_bow = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation + 1))
            nodes.append((port_bow.x, port_bow.y))
            port_stern = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation + 4))
            nodes.append((port_stern.x, port_stern.y))

        if rem_starboard:
            port_bow = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation - 1))
            nodes.append((port_bow.x, port_bow.y))
            port_stern = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation - 4))
            nodes.append((port_stern.x, port_stern.y))

        return [node for node in nodes if 0 <= node[0] < self.x_max and 0 <= node[1] < self.y_max]

    def compile_node_partials(self):
        for x in range(self.x_max):
            for y in range(self.y_max):
                for r in range(6):
                    key = self.encode_node_key(x, y, r, 0)

                    neighbour = Position(x,y).get_neighbor(r)
                    far_neighbour = neighbour.get_neighbor(r)
                    further_neighbour = far_neighbour.get_neighbor(r)

                    self._node_partials[key] = [
                        self.encode_node_key(neighbour.x, neighbour.y, self.map.abs_rotation(r+3), 0),
                        self.encode_node_key(neighbour.x, neighbour.y, self.map.abs_rotation(r+3), 1),
                        self.encode_node_key(neighbour.x, neighbour.y, self.map.abs_rotation(r+3), 2),
                        self.encode_node_key(neighbour.x, neighbour.y, r, 0),
                        self.encode_node_key(neighbour.x, neighbour.y, r, 1),
                        self.encode_node_key(neighbour.x, neighbour.y, r, 2),

                        self.encode_node_key(far_neighbour.x, far_neighbour.y, self.map.abs_rotation(r+3), 1),
                        self.encode_node_key(far_neighbour.x, far_neighbour.y, self.map.abs_rotation(r+3), 2),

                        self.encode_node_key(further_neighbour.x, further_neighbour.y, self.map.abs_rotation(r+3), 2)
                    ]

    def node_partials(self, x, y, r, full_ignore=None, partial_ignore=None, cannonball=False):
        partial_keys = self._node_partials[self.encode_node_key(x, y, r, 0)]

        if cannonball:
            partial_keys = partial_keys[:6]

        keys_1 = []
        if full_ignore is not None:
            for node_key in partial_keys:
                found = False
                for key_set in full_ignore:
                    if node_key in key_set:
                        found = True
                        break
                if not found:
                    keys_1.append(node_key)
        else:
            keys_1 = partial_keys

        keys_2 = []
        if partial_ignore is not None:
            for node_key in keys_1:
                found = False
                for key_set in partial_ignore:
                    if node_key in key_set:
                        found = True
                        break
                if not found:
                    keys_2.append(node_key)
        else:
            keys_2 = keys_1

        return keys_2

    def remove_full_ship_radii_1(self, x, y):
        key = self.encode_node_key(x, y, 0, 0)
        if key not in self.full_ship_nodes and key not in self.full_mine_nodes:
            self.full_ship_radii_1.add(key)

    def remove_full_ship_radii_2(self, x, y):
            key = self.encode_node_key(x, y, 0, 0)
            if key not in self.full_mine_nodes and key not in self.full_ship_nodes and key not in self.full_ship_radii_1 and key not in self.full_mine_radii:
                self.full_ship_radii_2.add(key)

    def future_ship_position(self, ship):
        ship_center = ship
        for _ in range(ship.speed):
            ship_center = ship_center.get_neighbor(ship.rotation)
        return ship_center

    def check_distance_to_entities(self, ship, entities, distance):
        for my_ship in entities:
            if my_ship.id != ship.id:
                if ship.calculate_distance_between(my_ship) <= distance:
                    return True
        return False

    def neighbours(self, key):
        if key in self.graph:
            return self.graph[key]
        else:
            return []

    def in_grid(self, entity):
        for rot in range(6):
            for spd in range(2):
                key = self.encode_node_key(entity.x, entity.y, rot, spd)
                full_key = self.get_full_key(key)
                if full_key not in self.full_mine_nodes and \
                    full_key not in self.full_ship_nodes and \
                    full_key not in self.full_cannonball_nodes and \
                    key not in self.partial_mine_nodes and \
                    key not in self.partial_ship_nodes and \
                    key not in self.partial_cannonball_nodes:
                    return True
        return False

    def find_closest(self, point):
        available = []
        for x in range(1, 10):
            if x > 2:
                neighbours = self.map.old_neighbours(point.x, point.y, search_range=x)
                neighbours = [(x.x, x.y) for x in neighbours]
            else:
                neighbours = self.map.neighbours(point.x, point.y, search_range=x)
            for neighbour in neighbours:
                neighbour = Position(neighbour[0], neighbour[1])
                if self.in_grid(neighbour):
                    count = 0
                    for speed in range(3):
                        for rotation in range(6):
                            count += len(self.neighbours(self.encode_node_key(neighbour.x, neighbour.y, rotation, speed)))
                    available.append([neighbour, count])
            if len(available) > 0:
                break

        return sorted(available, key=lambda x: x[1], reverse=True)[0][0]

    def check_for_goal(self, cur, pre=None, entity=None):
        # The pre-state should not have any points
        # Speed 1 adds two to the base
        # Speed 2 adds three to the base
        # Rotate on the new point
        if entity.x == cur.x and entity.y == cur.y:
            return True

        if pre is not None:
            if cur.speed > 0:
                speed_1 = pre.get_neighbor(self.map.abs_rotation(pre.rotation)).get_neighbor(self.map.abs_rotation(pre.rotation))
                if entity.x == speed_1.x and entity.y == speed_1.y:
                    # log('Got with speed_1')
                    return True

                if cur.speed > 1:
                    speed_2 = speed_1.get_neighbor(self.map.abs_rotation(pre.rotation))
                    if entity.x == speed_2.x and entity.y == speed_2.y:
                        # log('Got with speed_2')
                        return True

        if pre is None or cur.rotation != pre.rotation:
            bow = cur.get_neighbor(cur.rotation)
            if entity.x == bow.x and entity.y == bow.y:
                # log('Got with bow_rot')
                return True

            stern = cur.get_neighbor(self.map.abs_rotation(cur.rotation + 3))
            if entity.x == stern.x and entity.y == stern.y:
                # log('Got with stern_rot')
                return True

        return False

    def get_closest_bow(self, ship):
        closest = 10000
        for enemy_ship in self.game.enemy_ships.values():
            bow = enemy_ship.get_neighbor(enemy_ship.rotation)
            distance = bow.calculate_distance_between(ship)
            if distance < closest:
                closest = distance
        return closest

    def find_path(self, ship, entity, waypoints=None, something=False):
        timer.print('finding path')
        distance_to_entity = ship.calculate_distance_between(entity)
        waypoints = [entity] if waypoints is None else [entity] + waypoints

        winning_team = None
        highest_health = 0
        for owner, ship_set in [(ME, self.game.my_ships.values()), (ENEMY, self.game.enemy_ships.values())]:
            for _ship in ship_set:
                if _ship.rum > highest_health:
                    winning_team = owner
                    highest_health = _ship.rum

        if winning_team == ME:
            base_speed_mod = WINNING_SPEED_MULTI
            base_straight_mod = WINNING_STRAIGHT_MULTI
            base_edge_mod = WINNING_EDGE_MULTI
        else:
            base_speed_mod = LOSING_SPEED_MULTI
            base_straight_mod = LOSING_STRAIGHT_MULTI
            base_edge_mod = LOSING_EDGE_MULTI

        if len(self.game.barrels) > 0:
            base_speed_mod = BARREL_SPEED_MULTI
            base_straight_mod = BARREL_STRAIGHT_MULTI

        # if not self.in_grid(entity):
        #     return False

        frontier = []
        heapq.heappush(frontier, (0, (self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0), 0)))
        cost_so_far = {}
        came_from = {}
        came_from[self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0)] = None
        cost_so_far[self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0)] = 0

        solutions = []
        ok_solutions = []

        distance_costs = [waypoints[x].calculate_distance_between(waypoints[x+1]) for x in range(len(waypoints)-1)] + [0]

        # Get collisions
        check_ships = {}
        moves = {}
        for ships_set in [self.game.enemy_ships.items(), self.game.my_ships.items()]:
            for id, col_ship in ships_set:
                if ship.id == col_ship.id:
                    check_ships[id] = col_ship
                    moves[id] = [col_ship.str_action]
                elif ship.calculate_distance_between(col_ship) < 6:
                    check_ships[id] = col_ship
                    moves[id] = [col_ship.str_action]

        collision_move = {
            'WAIT': False,
            'FASTER': False,
            'SLOWER': False,
            'STARBOARD': False,
            'PORT': False
        }

        for move in collision_move:
            moves[ship.id] = [move]
            collision_move[move] = self.calculate_collisions(moves, check_id=ship.id, ships=check_ships)

        log('collision result for {}, {}'.format(ship.id, collision_move))
        timer.print('got collisions')

        # There was no possible option found to avoid crashing
        found_option = False
        for type, move in collision_move.items():
            if not move and type != 'SLOWER':
                found_option = True
                break

        if not found_option:
            ship.ignore_mine = True
            log('no option found')
            return False


        points_checked = 0
        while len(frontier) > 0:
            priority, current_timestep = heapq.heappop(frontier)
            current = current_timestep[0]
            timestep = current_timestep[1]

            points_checked += 1
            if points_checked % 20 == 0:
                log('WARNING: path > {}'.format(points_checked))
                if points_checked > 150 and len(ok_solutions) > 0:
                    #log('ok solution found')
                    break
                if points_checked > 200:
                    #log('ok solution found')
                    return False

            wait, current_waypoint, cur_x, cur_y, cur_r, cur_s = self.decode_node_key(current)
            current_no_w = current - (current_waypoint*1000000 + wait*10000000)

            # Check if we have reached the last waypoint
            if came_from[current] is not None and current_waypoint == (len(waypoints)-1):
                pre_wi, pre_w, pre_x, pre_y, pre_r, pre_s = self.decode_node_key(came_from[current])
                final_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s), Position(pre_x, pre_y, pre_r, pre_s), waypoints[-1])
                if final_point:
                    final_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint, wait)
                    solutions.append(final_point)
                    if len(solutions) > MINIMUM_SOLUTIONS:
                        break
            elif current_waypoint == (len(waypoints)-1):
                final_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s), entity=waypoints[-1])
                if final_point:
                    final_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint, wait)
                    solutions.append(final_point)
                    if len(solutions) > MINIMUM_SOLUTIONS:
                        break

            # Check if we have reached the next waypoint
            if came_from[current] is not None and current_waypoint < (len(waypoints)-1):
                pre_wi, pre_w, pre_x, pre_y, pre_r, pre_s = self.decode_node_key(came_from[current])
                current_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s),
                                                  Position(pre_x, pre_y, pre_r, pre_s), waypoints[current_waypoint])
                if current_point:
                    if current_waypoint == 0:
                        current_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint, wait)
                        ok_solutions.append(current_point)
                    current_waypoint += 1

            elif current_waypoint < (len(waypoints)-1):
                current_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s), entity=waypoints[current_waypoint])
                if current_point:
                    current_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint, wait)
                    ok_solutions.append(current_point)
                    current_waypoint += 1

            if something:
                if timestep > 5:
                    current_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint, wait)
                    ok_solutions.append(current_point)
                    break


            for next in self.neighbours(current_no_w):
                # It is waiting
                if next.x == cur_x and next.y == cur_y and next.rotation == cur_r and next.speed == cur_s:
                    next_wait = wait + 1
                else:
                    next_wait = wait

                next_key = self.encode_node_key(next.x, next.y, next.rotation, next.speed, current_waypoint, next_wait)
                next_key_no_w = self.encode_node_key(next.x, next.y, next.rotation, next.speed)

                planned_mod, straight_mod, speed_mod, edge_mod = 1, 1, 1, 1

                distance_to_next = ship.calculate_distance_between(next)
                if distance_to_next <= 6 or distance_to_next <= distance_to_entity:
                # if ship.calculate_distance_between(next) <= 6:
                    hex_cost = self.get_hex_cost(next_key_no_w, timestep)
                else:
                    hex_cost = 0

                speed_mod_value = base_speed_mod
                straight_mod_value = base_straight_mod
                close_mine_penalty = 0
                collision_penalty = 0

                if timestep == 0:
                    # distance < 4 : Apply increased penalty if not moving with ships withing short distance, possibly negate straight move bonus
                    closest_distance = self.get_closest_bow(ship)
                    if closest_distance < 4:
                        speed_mod_value = CLOSE_SPEED_MULTI
                        straight_mod_value = CLOSE_STRAIGHT_MULTI

                        # This is to negate the ship penalties but keep the mine penalties
                        # If we check for valid moves it should for the most part remove the need to ship penalties
                        if hex_cost > 0:
                            if hex_cost < 40:
                                hex_cost = 1
                            else:
                                hex_cost -= 39

                    # This seems to reduce performance... need to test - it will become better when
                    if closest_distance < 6 and next.speed == 0:
                        # distance < 6 : not allowed to move to a position that would not allow the ship to move forward if required
                        bow = next.get_neighbor(next.rotation)
                        first_possible_forward = bow.get_neighbor(next.rotation)
                        second_possible_forward = bow.get_neighbor(next.rotation)

                        if (not self.map.out_of_range(first_possible_forward) and  self.map.grid[first_possible_forward.y][first_possible_forward.x] == MINE) or \
                            (not self.map.out_of_range(second_possible_forward) and self.map.grid[second_possible_forward.y][second_possible_forward.x] == MINE):
                            close_mine_penalty = CLOSE_MINE_PENALTY


                    # Check if the last move was possible - make that move invalid (just make the cost high (not quite as high as a mine))
                    # Is the move possible

                    if next.speed > cur_s and collision_move['FASTER']:
                        collision_penalty = COLLISION_FASTER_COST
                    elif next.speed < cur_s and collision_move['SLOWER']:
                        collision_penalty = COLLISION_SLOWER_COST
                    elif next.rotation == self.map.abs_rotation(cur_r + 1) and collision_move['PORT']:
                        collision_penalty = COLLISION_PORT_COST
                    elif next.rotation == self.map.abs_rotation(cur_r - 1) and collision_move['STARBOARD']:
                        collision_penalty = COLLISION_STARBOARD_COST
                    elif next.rotation == cur_r and next.speed == cur_s and collision_move['WAIT']:
                        if ship.can_lay_mine() or ship.can_fire():
                            collision_penalty = COLLISION_WAIT_COST
                        else:
                            collision_penalty = COLLISION_WAIT_NO_COOLDOWN_COST

                # Speed modifier - we prefer moving over not moving
                speed_mod = speed_mod_value if next.speed > 0 else 1
                edge_mod = base_edge_mod if self.map.edge(Position(next.x, next.y)) else 1
                # Can we make a non-movement action?
                if next.speed == cur_s and next.speed > 0 and next.rotation == cur_r:
                    straight_mod = 1
                else:
                    if timestep == 0 and not (ship.can_fire() or ship.can_lay_mine()):
                        straight_mod = 1
                    else:
                        straight_mod = straight_mod_value

                if ship.planned_next_target is not None and \
                                next.x ==  ship.planned_next_target.x and \
                                next.y == ship.planned_next_target.y and \
                                next.rotation == ship.planned_next_target.rotation and \
                                next.speed == ship.planned_next_target.speed:
                    planned_mod = PLANNED_MULTI
                    #log('planned_mod')




                cost = ((1 * speed_mod * straight_mod) + hex_cost + close_mine_penalty + collision_penalty) * planned_mod  * edge_mod

                new_cost = cost_so_far[current] + cost
                if next_key not in cost_so_far or new_cost < cost_so_far[next_key]:
                    cost_so_far[next_key] = new_cost
                    distance_cost = sum(distance_costs[current_waypoint:]) * 1.7
                    target_cost = waypoints[current_waypoint].calculate_distance_between(next) * 1.7
                    priority = new_cost + target_cost + distance_cost
                    heapq.heappush(frontier, (priority, (next_key, timestep+1)))
                    came_from[next_key] = current

        if len(solutions) == 0:
            solutions = ok_solutions

        lowest_cost = 100000
        final_point = None
        for solution in solutions:
            if cost_so_far[solution] < lowest_cost:
                lowest_cost = cost_so_far[solution]
                final_point = solution

        log('points checked: {}'.format(points_checked))

        if final_point is None or final_point == False:
            #log('No path from ({},{}) to ({},{})'.format(ship.x, ship.y, entity.x, entity.y))
            return False

        current_key = final_point
        current_point = self.decode_node_key(current_key)

        ship_key = self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed)
        path = [current_point]

        while True:
            if came_from[current_key] is None or came_from[current_key] == ship_key:
                break
            else:
                key = came_from[current_key]
                wi, w, x, y, r, s = self.decode_node_key(key)
                current_point = (x, y, r, s)
                path.append(current_point)
                current_key = key

        path.append((ship.x, ship.y, ship.rotation, ship.speed))

        log(str(path))
        timer.print('path found')

        return path

    def calculate_collisions(self, raw_moves, ships=None, check_id=None, overview=False):
        moves = {}
        overview_set = {}

        #log('check_id: {}'.format(check_id))

        if ships is None:
            for id, ship in self.game.my_ships.items():
                moves[id] = {
                    'current_position': Position(ship.x, ship.y, ship.rotation, ship.speed),
                    'future_bow': None,
                    'future_mid': None,
                    'future_stern': None,
                    'future_rotation': None,
                    'owner': ME,
                    'move': raw_moves[id][0],
                    'detail': [] if len(raw_moves[id]) < 2 else [raw_moves[id][1], raw_moves[id][1]]
                }
            for id, ship in self.game.enemy_ships.items():
                moves[id] = {
                    'current_position': Position(ship.x, ship.y, ship.rotation, ship.speed),
                    'future_bow': None,
                    'future_mid': None,
                    'future_stern': None,
                    'future_rotation': None,
                    'owner': ENEMY,
                    'move': raw_moves[id][0],
                    'detail': [] if len(raw_moves[id]) < 2 else [raw_moves[id][1], raw_moves[id][1]]
                }
        else:
            for id, ship in ships.items():
                moves[id] = {
                    'current_position': Position(ship.x, ship.y, ship.rotation, ship.speed),
                    'future_bow': None,
                    'future_mid': None,
                    'future_stern': None,
                    'future_rotation': None,
                    'owner': ME,
                    'move': raw_moves[id][0],
                    'detail': [] if len(raw_moves[id]) < 2 else [raw_moves[id][1], raw_moves[id][1]]
                }

        # Apply move speed changes
        for move in moves.values():
            if move['move'] == 'FASTER' and move['current_position'].speed != 2:
                move['current_position'].speed += 1
            elif move['move'] == 'SLOWER' and move['current_position'].speed != 0:
                move['current_position'].speed -= 1

        for speed in range(2):
            for move in moves.values():
                if move['current_position'].speed > speed:
                    move['future_stern'] = Position(move['current_position'].x, move['current_position'].y)
                    move['future_mid'] = move['current_position'].get_neighbour(move['current_position'].rotation)
                    move['future_bow'] = move['future_mid'].get_neighbour(move['current_position'].rotation)

                    move['future_mid'].rotation = move['current_position'].rotation
                    move['future_mid'].speed = move['current_position'].speed
                else:
                    move['future_mid'] = Position(move['current_position'].x, move['current_position'].y, move['current_position'].rotation, move['current_position'].speed)
                    move['future_stern'] = move['future_mid'].get_neighbour(self.map.abs_rotation(move['current_position'].rotation-3))
                    move['future_bow'] = move['future_mid'].get_neighbour(move['current_position'].rotation)

            # Check for speed 1 collisions
            collision = True
            while collision:
                reset_ids = []
                collision = False
                for id, move in moves.items():
                    if move['current_position'].speed < speed+1:
                        continue
                    for id_opposing, move_opposing in moves.items():
                        if id == id_opposing:
                            continue
                        if move['future_bow'].x == move_opposing['future_bow'].x and move['future_bow'].y == move_opposing['future_bow'].y or \
                                move['future_bow'].x == move_opposing['future_mid'].x and move['future_bow'].y == move_opposing['future_mid'].y or \
                                move['future_bow'].x == move_opposing['future_stern'].x and move['future_bow'].y == move_opposing['future_stern'].y:
                            reset_ids.append(id)
                            collision = True
                            #log('id: {} crashed into id:{}'.format(id, id_opposing))
                            overview_set[id] = speed
                            if check_id == id:
                                return True
                            break

                for id in reset_ids:
                    moves[id]['current_position'].speed = 0

                    moves[id]['future_bow'] = moves[id]['future_mid']
                    moves[id]['future_mid'] = moves[id]['current_position']
                    moves[id]['future_stern'] = moves[id]['future_mid'].get_neighbour(self.map.abs_rotation(moves[id]['current_position'].rotation - 3))

                    moves[id]['move'] = 'WAIT' if moves[id]['move'] in ['STARBOARD', 'PORT'] else moves[id]['move']

            # For all the ships that have a speed > 0 update their current position to the future position
            for move in moves.values():
                if move['current_position'].speed > speed:
                    move['current_position'] = move['future_mid']

        for move in moves.values():
            if move['move'] == 'STARBOARD':
                move['future_rotation'] = self.map.abs_rotation(move['current_position'].rotation + 1)
            elif move['move'] == 'PORT':
                move['future_rotation'] = self.map.abs_rotation(move['current_position'].rotation - 1)
            else:
                move['future_rotation'] = move['current_position'].rotation

            move['future_mid'] = Position(move['current_position'].x, move['current_position'].y, move['future_rotation'], move['current_position'].speed)
            move['future_stern'] = move['future_mid'].get_neighbour(self.map.abs_rotation(move['future_rotation'] - 3))
            move['future_bow'] = move['future_mid'].get_neighbour(move['future_rotation'])

        # Check for speed 1 collisions
        collision = True
        while collision:
            reset_ids = []
            collision = False
            for id, move in moves.items():
                if move['move'] not in ['STARBOARD', 'PORT']:
                    continue

                for id_opposing, move_opposing in moves.items():
                    if id == id_opposing:
                        continue
                    if move['future_bow'].x == move_opposing['future_bow'].x and move['future_bow'].y == move_opposing['future_bow'].y or \
                            move['future_bow'].x == move_opposing['future_mid'].x and move['future_bow'].y == move_opposing['future_mid'].y or \
                            move['future_bow'].x == move_opposing['future_stern'].x and move['future_bow'].y == move_opposing['future_stern'].y or \
                            move['future_stern'].x == move_opposing['future_bow'].x and move['future_stern'].y == move_opposing['future_bow'].y or \
                            move['future_stern'].x == move_opposing['future_mid'].x and move['future_stern'].y == move_opposing['future_mid'].y or \
                            move['future_stern'].x == move_opposing['future_stern'].x and move['future_stern'].y == move_opposing['future_stern'].y:
                        reset_ids.append(id)

                        #log('id: {} crashed into id:{}'.format(id, id_opposing))
                        overview_set[id] = move['current_position'].speed
                        if check_id == id:
                            return True
                        collision = True
                        break

            for id in reset_ids:
                moves[id]['current_position'].speed = 0
                moves[id]['move'] = 'WAIT'
                moves[id]['future_rotation'] = moves[id]['current_position'].rotation

                moves[id]['future_mid'] = Position(moves[id]['current_position'].x, moves[id]['current_position'].y, moves[id]['future_rotation'], moves[id]['current_position'].speed)
                moves[id]['future_stern'] = moves[id]['future_mid'].get_neighbour(self.map.abs_rotation(moves[id]['future_rotation'] - 3))
                moves[id]['future_bow'] = moves[id]['future_mid'].get_neighbour(moves[id]['future_rotation'])


        # for all ships that still have a rotation update it
        for move in moves.values():
            if move['move'] in ['STARBOARD', 'PORT']:
                move['current_position'].rotation = move['future_rotation']

        if check_id is not None:
            # Perform another set of tests forward incase we screw ourselves over
            for speed in range(2):
                for move in moves.values():
                    if move['current_position'].speed > speed:
                        move['future_stern'] = Position(move['current_position'].x, move['current_position'].y)
                        move['future_mid'] = move['current_position'].get_neighbour(move['current_position'].rotation)
                        move['future_bow'] = move['future_mid'].get_neighbour(move['current_position'].rotation)

                        move['future_mid'].rotation = move['current_position'].rotation
                        move['future_mid'].speed = move['current_position'].speed
                    else:
                        move['future_mid'] = Position(move['current_position'].x, move['current_position'].y, move['current_position'].rotation, move['current_position'].speed)
                        move['future_stern'] = move['future_mid'].get_neighbour(self.map.abs_rotation(move['current_position'].rotation-3))
                        move['future_bow'] = move['future_mid'].get_neighbour(move['current_position'].rotation)

                # Check for speed 1 collisions
                collision = True
                while collision:
                    reset_ids = []
                    collision = False
                    for id, move in moves.items():
                        if move['current_position'].speed < speed+1:
                            continue
                        for id_opposing, move_opposing in moves.items():
                            if id == id_opposing:
                                continue
                            if move['future_bow'].x == move_opposing['future_bow'].x and move['future_bow'].y == move_opposing['future_bow'].y or \
                                    move['future_bow'].x == move_opposing['future_mid'].x and move['future_bow'].y == move_opposing['future_mid'].y or \
                                    move['future_bow'].x == move_opposing['future_stern'].x and move['future_bow'].y == move_opposing['future_stern'].y:
                                reset_ids.append(id)
                                collision = True
                                #log('id: {} crashed into id:{}'.format(id, id_opposing))
                                if check_id == id:
                                    return True
                                break

                    for id in reset_ids:
                        moves[id]['current_position'].speed = 0

                        moves[id]['future_bow'] = moves[id]['future_mid']
                        moves[id]['future_mid'] = moves[id]['current_position']
                        moves[id]['future_stern'] = moves[id]['future_mid'].get_neighbour(self.map.abs_rotation(moves[id]['current_position'].rotation - 3))

                        moves[id]['move'] = 'WAIT' if moves[id]['move'] in ['STARBOARD', 'PORT'] else moves[id]['move']

                # For all the ships that have a speed > 0 update their current position to the future position
                for move in moves.values():
                    if move['current_position'].speed > speed:
                        move['current_position'] = move['future_mid']

        if check_id is not None:
            return False
        elif overview:
            return overview_set


class Map:
    def __init__(self, x, y):
        self.x = x
        self.y = y

        self.grid = [[0 for _ in range(x)] for _ in range(y)]

        self._neighbours = {}
        self._far_neighbours = {}

        self.waypoints = []

        self.compile_neighbours()

    def update(self, game):
        self.grid = [[0 for _ in range(self.x)] for _ in range(self.y)]

        self.add_ships(game.my_ships)
        self.add_ships(game.enemy_ships, enemy=True)
        self.add_barrels(game.barrels)
        self.add_cannonballs(game.cannonballs)
        self.add_mines(game.mines)

    def add_barrels(self, barrels):
        for barrel in barrels:
            self.grid[barrel.y][barrel.x] = BARREL

    def add_mines(self, mines):
        for mine in mines.values():
            self.grid[mine.y][mine.x] = MINE

    def add_cannonballs(self, cannonballs):
        for cannonball in cannonballs:
            self.grid[cannonball.y][cannonball.x] = CANNONBALL

    def add_ships(self, ships, enemy=False):
        ship_number = ENEMY_SHIP if enemy else MY_SHIP

        for i, ship in ships.items():
            bow = ship.get_neighbor(ship.rotation)
            stern = ship.get_neighbor((ship.rotation + 3)%6)
            move = bow.get_neighbor(ship.rotation)

            if not self.out_of_range(ship):
                self.grid[ship.y][ship.x] = ship_number
            if not self.out_of_range(bow):
                self.grid[bow.y][bow.x] = ship_number
            if not self.out_of_range(stern):
                self.grid[stern.y][stern.x] = ship_number
            # if not self.out_of_range(move):
            #     self.grid[move.y][move.x] = ship_number

    def neighbours(self, x, y, safe=True, search_range=1, all=False):
        key = x+y*self.x

        if search_range == 1:
            return self._neighbours[key]
        elif search_range == 2 and not all:
            return self._far_neighbours[key]
        else:
            return self._neighbours[key] + self._far_neighbours[key]

    def old_neighbours(self, x, y, safe=True, search_range=1):
        position = Position(x,y)
        position_neighbours = []
        for i in range(6):
            neighbour_position = position.get_neighbor(i)
            for _ in range(search_range-1):
                neighbour_position = neighbour_position.get_neighbor(i)
            if safe:
                if 0 <= neighbour_position.y < self.y and 0 <= neighbour_position.x < self.x:
                    if self.grid[neighbour_position.y][neighbour_position.x] != MINE or \
                                    self.grid[neighbour_position.y][neighbour_position.x] != CANNONBALL:
                        position_neighbours.append(neighbour_position.get_neighbor(i))
            else:
                if 0 <= neighbour_position.y < self.x and 0 <= neighbour_position.x < self.x:
                    position_neighbours.append(neighbour_position.get_neighbor(i))
        return position_neighbours

    def compile_neighbours(self):
        for x in range(self.x):
            for y in range(self.y):
                position = Position(x,y)
                position_neighbours = []
                position_far_neighbours = []
                for i in range(6):
                    neighbour_position = position.get_neighbor(i)
                    if 0 <= neighbour_position.y < self.y and 0 <= neighbour_position.x < self.x:
                        position_neighbours.append((neighbour_position.x, neighbour_position.y))
                        for j in range(2):
                            far_neighbour_position = neighbour_position.get_neighbor(i)
                            if 0 <= far_neighbour_position.y < self.y and 0 <= far_neighbour_position.x < self.x:
                                position_far_neighbours.append((far_neighbour_position.x, far_neighbour_position.y))

                self._neighbours[x+y*self.x] = position_neighbours
                self._far_neighbours[x+y*self.x] = position_far_neighbours

    @staticmethod
    def abs_rotation(rotation):
        return (12 + rotation) % 6

    def out_of_range(self, position):
        return position.x >= self.x or position.y >= self.y or position.x < 0 or position.y < 0

    def edge(self, position):
        return position.x >= (self.x-1) or position.y >= (self.y-1) or position.x < 1 or position.y < 1

    def distances_to_mines_exp(self, point, mines):
        distances = [(mine, 1/point.calculate_distance_between(mine)) for mine in mines.values()]
        sorted_distances = sorted((distance for distance in distances if distance[1] < 6), key=lambda x: x[1], reverse=True)
        return sorted_distances

    def smallest_distance(self, point, points):
        if len(points) == 0:
            return 10000000
        distances = [test_point.calculate_distance_between(point) for test_point in points]
        sorted_distances = sorted(distances)
        return sorted_distances[0]

    def determine_waypoints(self, game):
        self.waypoints = {}
        all_waypoints = []
        index = -1
        #timer.print('start')
        # for x in range(5, 20, 4):
        #     for y in range(4, 18, 4):
        #
        #         index += 1
        #         # Find the optimal position
        #         grid_costs = []
        #         for neighbour in self.neighbours(x, y, search_range=1, all=True) + [(x,y)]:
        #             distance_cost = 100
        #             if self.grid[neighbour[1]][neighbour[0]] != MINE:
        #                 distance_cost = 0
        #                 count = 0
        #                 for mine, distance in self.distances_to_mines_exp(Position(neighbour[0],neighbour[1]), game.mines)[:4]:
        #                     distance_cost += distance
        #                     count += 1
        #                 if count != 0:
        #                     distance_cost /= count
        #             grid_costs.append({'index': index,
        #                                'position': Position(neighbour[0], neighbour[1]),
        #                                'mine_cost': distance_cost})
        #
        #         all_waypoints.append(sorted(grid_costs, key=lambda x: x['mine_cost'], reverse=True))
        #         #timer.print('{} {} complete'.format(x,y))
        #
        # all_waypoints.sort(key=lambda x: x[0]['mine_cost'], reverse=True)
        # #timer.print('sorted')
        #
        # for waypoint_set in all_waypoints:
        #     for waypoint in waypoint_set:
        #         if self.smallest_distance(waypoint['position'], self.waypoints.values()) > 1:
        #             self.waypoints[waypoint['index']] = waypoint['position']

        index = -1
        for x in range(5, 20, 4):
            for y in range(4, 18, 4):
                index += 1
                if index not in self.waypoints:
                    self.waypoints[index] = Position(x,y)

        #log(self.waypoints)

class Cube:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Entity:
    __metaclass__ = abc.ABCMeta

    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y

    def get_neighbour(self, direction):
        return self.get_neighbor(direction)

    def get_neighbor(self, direction):
        oddr_directions = [
            [Position(+1, 0), Position(0, -1), Position(-1, -1),
             Position(-1, 0), Position(-1, +1), Position(0, +1)],
            [Position(+1, 0), Position(+1, -1), Position(0, -1),
             Position(-1, 0), Position(0, +1), Position(+1, +1)]
        ]

        parity = self.y & 1
        dir = oddr_directions[parity][direction]
        return Position(self.x + dir.x, self.y + dir.y)

    def calculate_distance_between(self, entity):
        ac = self.oddr_to_cube(self)
        bc = self.oddr_to_cube(entity)
        return self.cube_distance(ac, bc)

    def __str__(self):
        return "Entity {} (id: {}) at position: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.id, self.x, self.y)

    @staticmethod
    def cube_to_oddr(cube):
        y = cube.x + (cube.z - (cube.z & 1)) / 2
        x = cube.z
        return Position(x, y)

    @staticmethod
    def oddr_to_cube(hex):
        x = hex.x - (hex.y - (hex.y & 1)) / 2
        z = hex.y
        y = -x - z
        return Cube(x, y, z)

    @staticmethod
    def cube_distance(a, b):
        return (abs(a.x - b.x) + abs(a.y - b.y) + abs(a.z - b.z)) / 2

    @staticmethod
    def abs_rotation(rotation):
        return (12 + rotation) % 6


class Ship(Entity):
    def __init__(self, id, x, y, rotation, speed, rum, graph):
        self.id = id
        self.x = x
        self.y = y

        self.prev_x = self.x
        self.prev_y = self.y

        self.rotation = rotation
        self.speed = speed
        self.rum = rum
        self.graph = graph
        self.navigate_action = None
        self.next_waypoint = None
        self.planned_next_target = None

        self.waypoint = None

        self.cannonball = 10
        self.mine = 10

        self.action = None
        self.str_action = 'WAIT'
        self.ignore_mine = False

        # Fire Action
        self.fire_x, self.fire_y = 0, 0

        # Move Action
        self.move_x, self.move_y = 0, 0

    def __str__(self):
        return "Entity {} (id: {}) at position: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.id, self.x, self.y)

    def update_ship(self, x, y, rotation, speed, rum):
        self.prev_x = self.x
        self.prev_y = self.y

        self.x = x
        self.y = y
        self.rotation = rotation
        self.speed = speed
        self.rum = rum

        self.cannonball += 1
        self.mine += 1

        self.action = None
        self.str_action = 'WAIT'
        self.ignore_mine = False

    def fire(self, entity):
        #log('firing on ship({}) ({},{})'.format(entity.id, entity.x, entity.y))

        fire_location_found = False
        fire_time = 0
        distance = 0

        bow = self.get_neighbor(self.rotation)

        if isinstance(entity, Ship) and entity.speed != 0:
            estimated_location = Position(entity.x, entity.y)
            #log('starting_location: ({},{})'.format(estimated_location.x, estimated_location.y))

            for t in range(1, 10):
                for _ in range(entity.speed):
                    estimated_location = estimated_location.get_neighbor(entity.rotation)

                #log('t: {}, estimated_location: ({},{})'.format(t, estimated_location.x, estimated_location.y))

                if estimated_location.x >= self.graph.x_max:
                    estimated_location.x = self.graph.x_max-1
                    #log('mod_x_max')
                if estimated_location.y >= self.graph.y_max:
                    estimated_location.y = self.graph.y_max-1
                    #log('mod_y_max')
                if estimated_location.x < 0:
                    estimated_location.x = 0
                    #log('mod_x_min')
                if estimated_location.y < 0:
                    estimated_location.y = 0
                    #log('mod_y_min')

                distance = bow.calculate_distance_between(estimated_location)
                fire_time = (int(round(1 + (distance / 3)))) + 1    # This is the number of turns

                # log('fire_time: {}'.format(fire_time))

                if fire_time <= t:
                    # log('fire_time: {} time: {}'.format(fire_time, t))
                    self.fire_x, self.fire_y = estimated_location.x, estimated_location.y
                    fire_location_found = True
                    break
        else:
            self.fire_x, self.fire_y = entity.x, entity.y
            #log('static_fire: ({},{})'.format(self.fire_x, self.fire_y))
            fire_location_found = True

        if not fire_location_found:
            #log('no fire location found')
            return False

        if Position(self.fire_x, self.fire_y).calculate_distance_between(bow) > 10:
            #log('out of range')
            return False

        if self.will_likely_hit_ship(self.fire_x, self.fire_y):
            fire_position = Position(self.fire_x, self.fire_y)
            while True:
                fire_position = fire_position.get_neighbor(self.graph.map.abs_rotation(entity.rotation-3))
                if not self.will_likely_hit_ship(fire_position.x, fire_position.y):
                    self.fire_x, self.fire_y = fire_position.x, fire_position.y
                    break


        self.cannonball = 0
        self.action = self._print_fire

        if self.speed > 0:
            rem_forward = True
        else:
            rem_forward = False

        if isinstance(entity, Ship) and entity.speed == 0:
            self.ignore_mine = True

        firing_on_mine = False
        if not self.ignore_mine:
            for neighbour in self.graph.map.neighbours(self.fire_x, self.fire_y):
                if 0 <= neighbour[1] < self.graph.map.y and 0 <= neighbour[0] < self.graph.map.x:
                    if self.graph.map.grid[neighbour[1]][neighbour[0]] == MINE:
                        self.fire_x, self.fire_y = neighbour[0], neighbour[1]
                        #log('Firing on mine')
                        break

        if not self.ignore_mine and not firing_on_mine:
            for neighbour in self.graph.map.neighbours(self.fire_x, self.fire_y):
                if 0 <= neighbour[1] < self.graph.map.y and 0 <= neighbour[0] < self.graph.map.x:
                    if self.graph.map.grid[neighbour[1]][neighbour[0]] == BARREL:
                        point = Position(neighbour[0], neighbour[1])
                        entity_distance = entity.calculate_distance_between(point)
                        closest_ship = 10000
                        for ship in self.graph.game.my_ships.values():
                            distance = ship.calculate_distance_between(point)
                            if distance < closest_ship:
                                closest_ship = distance

                        if (closest_ship + 3) > entity_distance:
                            self.fire_x, self.fire_y = neighbour[0], neighbour[1]
                            log('Firing on barrel')
                            break

        #log('FIRE : estimated_time:{} : target_point:({},{}) : distance:{}'.format(fire_time, self.fire_x, self.fire_y, distance))

        deque(map(lambda node: self.graph.remove_ship_node(node[0], node[1]),
                  self.graph.get_ship_nodes(self, rem_forward=rem_forward)))

        self.str_action = 'FIRE {} {}'.format(self.fire_x, self.fire_y)

        return True

    def will_likely_hit_ship(self, x, y):
        if self.speed == 0:
            stern = self.get_neighbor(self.graph.map.abs_rotation(self.rotation+3))
            center = self
            bow = self.get_neighbor(self.rotation)
        elif self.speed == 1:
            stern = self
            center = self.get_neighbor(self.rotation)
            bow = center.get_neighbor(self.rotation)
        else:
            stern = self.get_neighbor(self.rotation)
            center = stern.get_neighbor(self.rotation)
            bow = center.get_neighbor(self.rotation)
            future_center = bow.get_neighbor(self.rotation)
            if future_center.x == x and future_center.y == y:
                return True

        if (stern.x == x and stern.y == y) or \
            (center.x == x and center.y == y) or \
            (bow.x == x and bow.y == y):
            return True
        return False

    def _print_fire(self):
        print('FIRE {0} {1} FIRE {0} {1}'.format(self.fire_x, self.fire_y))

    def can_fire(self):
        return self.cannonball > 1

    def lay_mine(self):
        self.mine = 0
        self.action = self._print_mine

        if self.speed > 0:
            rem_forward = True
        else:
            rem_forward = False

        deque(map(lambda node: self.graph.remove_ship_node(node[0], node[1]),
          self.graph.get_ship_nodes(self, rem_forward=rem_forward)))

        self.str_action = 'MINE'

    def _print_mine(self):
        print('MINE MINE')

    def no_action(self):
        self.navigate_action = 'WAIT'
        self.action = self._print_no_action

        if self.speed > 0:
            rem_forward = True
        else:
            rem_forward = False

        deque(map(lambda node: self.graph.remove_ship_node(node[0], node[1]),
                  self.graph.get_ship_nodes(self, rem_forward=rem_forward)))

        self.str_action = 'WAIT'

    def _print_no_action(self):
        print('WAIT WAIT')

    def can_lay_mine(self):
        return self.mine > 3

    def move(self, entity):
        self.move_x, self.move_y = entity.x, entity.y
        self.action = self._print_move

    def _print_navigate(self):
        print('{0} {0}'.format(self.navigate_action))

    def _print_move(self):
        #print(['STARBOARD', 'FASTER'][random.randint(0,1)])
        print('MOVE {0} {1} MOVE {0} {1}'.format(self.move_x, self.move_y))

    def print_action(self):
        self.action()

    def navigate(self, entity, waypoints=None):
        waypoints = [] if waypoints is None else waypoints
        if not self.graph.in_grid(entity):
            entity = self.graph.find_closest(entity)
        new_waypoints = []
        for waypoint in waypoints:
            if not self.graph.in_grid(waypoint):
                new_waypoints.append(self.graph.find_closest(waypoint))
            else:
                new_waypoints.append(waypoint)

        path = self.graph.find_path(self, entity, waypoints=new_waypoints)
        if path == False:
            log('try to find something')
            path = self.graph.find_path(self, entity, waypoints=new_waypoints, something=True)
            if path == False:
                return False
        self.navigate_action = self.determine_move(path[-2:])

        # Store the next move that was planned and make it a
        # little cheaper so it is based towards it next turn to help with navigation
        if len(path) > 2:
            self.planned_next_target = Position(path[-3][0], path[-3][1], path[-3][2], path[-3][3])
        else:
            self.planned_next_target = None

        self.action = self._print_navigate

        #log('navigate_action: {}'.format(self.navigate_action))
        self.str_action = self.navigate_action
        return True

    def get_closest_enemy_ship(self, ship, enemy_ships):
        closest_enemy_ship = None
        closest_distance = 10000
        for id, enemy_ship in enemy_ships.items():
            distance = ship.calculate_distance_between(enemy_ship)
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy_ship = enemy_ship
        return closest_enemy_ship, closest_distance

    def should_avoid(self, enemy_ships):
        highest_health_enemy = max([[x.rum, x] for i, x in enemy_ships.items()], key=lambda x: x[0])
        if self.rum > highest_health_enemy[0]:
            return True, highest_health_enemy[1]
        return False, highest_health_enemy[1]

    def ordered_waypoints(self, enemy_ships):
        avoid, enemy_ship = self.should_avoid(enemy_ships)
        return sorted(range(len(self.graph.map.waypoints)),
                      key=lambda x: Position(self.graph.map.waypoints[x].x, self.graph.map.waypoints[x].y).calculate_distance_between(enemy_ship),
                      reverse=avoid)

    def waypoint_move(self, enemy_ships, my_ships):
        #log(enemy_ships)
        if self.waypoint is None or self.calculate_distance_between(self.graph.map.waypoints[self.waypoint]) <= 3:
            ordered_waypoints = self.ordered_waypoints(enemy_ships)
            current_waypoints = [[ship.waypoint, ship.next_waypoint] for ship in my_ships.values() if ship.id != self.id]
            flattend_current_waypoints = [x for y in current_waypoints for x in y]
            #log('flattened waypoints: {}'.format(flattend_current_waypoints))
            reduced_set = [waypoint for waypoint in ordered_waypoints if waypoint not in flattend_current_waypoints]
            ordered_waypoints = [waypoint for waypoint in reduced_set if self.calculate_distance_between(self.graph.map.waypoints[waypoint]) > 3][:2]

            if self.next_waypoint in ordered_waypoints:
                self.waypoint = self.next_waypoint
                different2 = False
                while not different2:
                    next_waypoint = random.choice(ordered_waypoints)
                    if next_waypoint != self.waypoint:
                        self.next_waypoint = next_waypoint
                        different2 = True
            else:
                different = False
                while not different:
                    new_waypoint = random.choice(ordered_waypoints)
                    if new_waypoint != self.waypoint:
                        self.waypoint = new_waypoint
                        different2 = False
                        while not different2:
                            next_waypoint = random.choice(ordered_waypoints)
                            if next_waypoint != self.waypoint:
                                self.next_waypoint = next_waypoint
                                different2 = True
                        different = True

        point = self.get_reachable_point(self.waypoint)
        point_2 = self.get_reachable_point(self.next_waypoint)

        return point, point_2

    def get_reachable_point(self, point):
        if self.graph.in_grid(Position(self.graph.map.waypoints[point].x, self.graph.map.waypoints[point].y)):
            nav = Position(self.graph.map.waypoints[point].x, self.graph.map.waypoints[point].y)
        else:
            nav = self.graph.find_closest(Position(self.graph.map.waypoints[point].x, self.graph.map.waypoints[point].y))

        return nav

    def guaranteed_mine_hit(self, ships):
        mine_position = self.get_neighbor(self.graph.map.abs_rotation(self.rotation+3)).get_neighbor(self.graph.map.abs_rotation(self.rotation+3))

        for ship in ships.values():
            if ship.calculate_distance_between(mine_position) > 6 or ship.id == self.id:
                continue

            key = self.graph.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed)
            neighbours = self.graph.neighbours(key)
            all_neighbours = [self.graph.neighbours(self.graph.encode_node_key(neighbour.x, neighbour.y, neighbour.rotation, neighbour.speed)) for neighbour in neighbours]

            for neighbour_set in all_neighbours:
                for neighbour in neighbour_set:
                    if neighbour.x == mine_position.x and neighbour.y == mine_position.y:
                        return True
        return False

    def determine_move(self, moves):
        #log(str(moves))
        action = None

        moves = [moves[0][-4:], moves[1][-4:]]

        if moves[1][3] == moves[0][3]:
            if moves[1][2] == moves[0][2]:
                action = 'WAIT'
            elif (moves[1][2] + 1) % 6 == moves[0][2]:
                action = 'PORT'
            else:
                action = 'STARBOARD'
        elif moves[1][3] > moves[0][3]:
            action = 'SLOWER'
        elif moves[1][3] < moves[0][3]:
            action = 'FASTER'

        if self.speed == 0 or self.action == 'SLOWER':
            rem_forward = False
        else:
            rem_forward = True

        if action  == 'STARBOARD':
            rem_port = False
        else:
            rem_port = True

        if action == 'PORT':
            rem_starboard = False
        else:
            rem_starboard = True

        deque(map(lambda node: self.graph.remove_ship_node(node[0], node[1]),
                  self.graph.get_ship_nodes(self, rem_forward=rem_forward, rem_port=rem_port, rem_starboard=rem_starboard)))

        return action


class Barrel(Entity):
    def __init__(self, id, x, y, rum):
        self.id = id
        self.x = x
        self.y = y
        self.rum = rum

    def __str__(self):
        return "Entity {} (id: {}) at position: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.id, self.x, self.y)


class Cannonball(Entity):
    def __init__(self, id, x, y, shot_id, impact):
        self.id = id
        self.x = x
        self.y = y
        self.shot_id = shot_id
        self.impact = impact

    def __str__(self):
        return "Entity {} (id: {}) at position: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.id, self.x, self.y)


class Mine(Entity):
    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y

    def __str__(self):
        return "Entity {} (id: {}) at position: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.id, self.x, self.y)


class Position(Entity):
    def __init__(self, x, y, rotation=None, speed=None):
        self.x = x
        self.y = y
        self.rotation = rotation
        self.speed = speed

    def __str__(self):
        return "Entity {} at position: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.x, self.y)


class AI:
    def __init__(self):
        self.game = Game()
        self.targeted_barrels = []

    def get_closest_entity(self, ship, entities, ignore=None):
        ignore = ignore if ignore is not None else []
        closest_entity = None
        closest_distance = 10000
        for entity in entities:
            if entity.id not in ignore:
                distance = ship.calculate_distance_between(entity)
                if distance < closest_distance:
                    closest_distance = distance
                    closest_entity = entity
        return closest_entity, closest_distance

    def get_closest_entitys(self, ship, entities):
        return sorted([(ship.calculate_distance_between(entity), entity) for entity in entities], key=lambda x: x[0])

    def get_closest_enemy_ship(self, ship, enemy_ships):
        closest_enemy_ship = None
        closest_distance = 10000
        for id, enemy_ship in enemy_ships.items():
            distance = ship.calculate_distance_between(enemy_ship)
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy_ship = enemy_ship
        return closest_enemy_ship, closest_distance

    def barrel_ship_distances(self, ships, barrels):
        distances = [(barrel, ship, ship.calculate_distance_between(barrel)) for ship in ships.values() for barrel in barrels]
        sorted_distances = sorted(distances, key=lambda x: x[2])
        return sorted_distances

    def barrel_barrel_distances(self, barrels):
        barrel_distances = {}
        for barrel1 in barrels:
            barrel_distances[barrel1.id] = sorted([(barrel2, barrel1.calculate_distance_between(barrel2)) for barrel2 in barrels if barrel2.id != barrel1.id], key=lambda x: x[1])
        return barrel_distances

    def assign_barrels(self):
        taken_barrels = set()
        if len(self.game.barrels) > 0:
            barrel_barrel_distances = self.barrel_barrel_distances(self.game.barrels)
            barrel_ship_distances = self.barrel_ship_distances(self.game.my_ships, self.game.barrels)
            for i, barrel_ship in enumerate(barrel_ship_distances):
                if len(taken_barrels) >= len(self.game.barrels) or len(self.assigned_ships) >= len(self.game.my_ships):
                    break
                if barrel_ship[0].id in taken_barrels or barrel_ship[1].id in self.assigned_ships:
                    continue

                #log('ship ({}) navigating to barrel ({})'.format(barrel_ship[1].id, barrel_ship[0].id))

                # Get possible next barrel
                next_barrel = None
                for barrel in barrel_barrel_distances[barrel_ship[0].id]:
                    if barrel[0].id not in taken_barrels and barrel[0].id != barrel_ship[0].id:
                        next_barrel = barrel[0]
                        break

                if next_barrel is None:
                    if barrel_ship[1].next_waypoint is None:
                        ordered_waypoints = barrel_ship[1].ordered_waypoints(self.game.enemy_ships)[:3]
                        next_barrel_id = random.choice(ordered_waypoints)
                        barrel_ship[1].next_waypoint = next_barrel_id

                    next_barrel = self.game.map.waypoints[barrel_ship[1].next_waypoint]

                barrel_id = barrel_ship[0].id
                if not self.game.graph.in_grid(barrel_ship[0]):
                    barrel_ship = list(barrel_ship)
                    barrel_ship[0] = self.game.graph.find_closest(barrel_ship[0])
                if not self.game.graph.in_grid(next_barrel):
                    next_barrel = self.game.graph.find_closest(next_barrel)


                self.assigned_ships[barrel_ship[1].id] = {'action': 'barrel',
                                                  'target_nav': barrel_ship[0],
                                                  'waypoints': [next_barrel]
                                                  }

                taken_barrels.add(barrel_id)

                for dist_barrel in barrel_barrel_distances[barrel_id]:
                    if dist_barrel[1] <= 2:
                        taken_barrels.add(dist_barrel[0].id)
                        #log('taken: {}'.format(dist_barrel[0].id))
                    else:
                        break

    def assign_waypoints(self):
        for id, ship in self.game.my_ships.items():
            if id not in self.assigned_ships:
                point, point_2 = ship.waypoint_move(self.game.enemy_ships, self.game.my_ships)

                self.assigned_ships[id] = {'action': 'waypoint',
                                          'target_nav': point,
                                          'waypoints': [point_2]
                                          }

    def run(self, load=False):
        while True:
            self.turn(load)

    def turn(self, load=False, file='data.json'):
        self.assigned_ships = {}

        time_a = time.time()

        self.game.update_map(load=load, file=file)

        self.assign_barrels()
        #log('assigned barrels')
        self.assign_waypoints()
        #log('assigned waypoints')

        for ship_id, navigation in self.assigned_ships.items():
            self.game.graph.remove_ship_set([ship for ship in self.game.my_ships.values() if ship.id != ship_id])
            result = self.game.my_ships[ship_id].navigate(navigation['target_nav'], waypoints=navigation['waypoints'])
            if result:
                success = 'success'
            else:
                success = 'failed'
                self.game.my_ships[ship_id].no_action()

            log('{} - ship_id: {}, action: {}, target_nav: {}, waypoint: {}'.format(success,
                                                                                    ship_id,
                                                                                    navigation['action'],
                                                                                    navigation['target_nav'],
                                                                                    navigation['waypoints'][0]))


        self.game.apply_collisions()
        timer.print('apply collisions')

        for id, ship in self.game.my_ships.items():
            closest_ship, distance_to_closest_ship = self.get_closest_enemy_ship(ship, self.game.enemy_ships)
            if ship.navigate_action == 'WAIT' or ship.navigate_action is None or ship.action is None:
                lay_mine=MAYBE
                if ship.can_lay_mine():
                    if not ship.guaranteed_mine_hit(self.game.my_ships):
                        if ship.guaranteed_mine_hit(self.game.enemy_ships):
                            #log('Guaranteed Enemy')
                            lay_mine = YES
                    else:
                        #log('Guaranteed Me')
                        lay_mine = NO

                if ship.can_fire() and lay_mine != YES:
                    result = ship.fire(closest_ship)
                    if result:
                        #log('ship ({}) firing'.format(id))
                        continue

                if lay_mine != NO:
                    #log('ship ({}) laying mine'.format(id))
                    ship.lay_mine()
                else:
                    #log('ship ({}) no_action'.format(id))
                    ship.no_action()

        moves = {}
        for id, ship in self.game.my_ships.items():
            moves[id] = ship.str_action

        for id in self.game.enemy_ships:
            moves[id] = 'WAIT'

        # timer.print('Start collisions')
        # self.game.graph.calculate_collisions(moves)
        # timer.print('End collisions')

        for id, ship in self.game.my_ships.items():
            #log(str(ship.action))
            ship.print_action()

        time_b = time.time()
        dif = time_b - time_a
        timer.print('done')
        log('Loop took {}ms'.format(round(dif*100,2)))


if __name__ == "__main__":
    ai = AI()
    ai.run(False)