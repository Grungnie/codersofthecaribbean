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
        self.mines = []
        self.map = Map(23, 21)
        self.graph = Graph(self.map)

        self.my_ship_count = None
        self.entity_count = None

    def clear_last_turn(self):
        # self.my_ships = {}
        # self.enemy_ships = {}
        self.cannonballs = []
        self.barrels = []
        self.mines = []

        self.my_ship_count = None
        self.entity_count = None

    def get_all_inputs(self, load=False):
        if load:
            self.inputs = json.load(open('data.json'))[load]
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

    def update_map(self, load=False):
        self.get_all_inputs(load=load)
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

    def print_map(self):
        for i, row in enumerate(self.map.grid):
            row = ['F' if i == MY_SHIP else i for i in row]
            row = ['E' if i == ENEMY_SHIP else i for i in row]
            row = ['B' if i == BARREL else i for i in row]
            row = ['M' if i == MINE else i for i in row]
            row = ['-' if i == 0 else str(i) for i in row]
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
                self.mines.append(Mine(entity_id, x, y))
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


class Graph:
    def __init__(self, map):
        self.x_max = map.x
        self.y_max = map.y
        self.map = map
        self.graph = {}

        self.full_cannonball_nodes = [set() for _ in range(15)]
        self.partial_cannonball_nodes = [set() for _ in range(15)]

        self.full_mine_nodes = set()
        self.partial_mine_nodes = set()

        self.full_ship_nodes = set()
        self.partial_ship_nodes = set()

        self.full_mine_radii = set()
        self.partial_mine_radii = set()

        self.full_ship_radii_1 = set()
        self.partial_ship_radii_1 = set()

        self.full_ship_radii_2 = set()
        self.partial_ship_radii_2 = set()

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
    def encode_node_key(x, y, r, s, w=0):
        # xxyyrs
        return w*1000000 + x*10000 + y*100 + r*10 + s

    @staticmethod
    def decode_node_key(key):
        w = int( key/1000000)
        x = int((key - w*1000000)/10000)
        y = int((key - w*1000000 - x*10000)/100)
        r = int((key - w*1000000 - x*10000 - y*100)/10)
        s = int( key - w*1000000 - x*10000 - y*100 - r*10)
        return w, x, y, r, s

    @staticmethod
    def get_full_key(key):
        return int(key/100)*100

    def remove_nodes(self, game):
        # Cannonball - all
        deque(map(lambda cannonball: self.remove_cannonball_node(cannonball.x, cannonball.y, cannonball.impact), game.cannonballs))
        deque(map(lambda cannonball: self.remove_partial_cannonball_nodes(cannonball.x, cannonball.y, cannonball.impact), game.cannonballs))
        timer.print('cannonballs removed')

        # Mine - all
        deque(map(lambda mines: self.remove_mine_node(mines.x, mines.y), game.mines))
        deque(map(lambda mines: self.remove_partial_mine_node(mines.x, mines.y), game.mines))
        timer.print('mines removed')

        # Ship - Only if not in mine
        ship_nodes = [self.get_ship_nodes(ship) for ship in game.enemy_ships.values()]
        deque(map(lambda node: self.remove_ship_node(node[0], node[1]), [x for y in ship_nodes for x in y]))
        deque(map(lambda node: self.remove_partial_ship_node(node[0], node[1]), [x for y in ship_nodes for x in y]))
        timer.print('ships removed')

        # Ship Radii 1 - Only if not in mine or ship (start using same decay)
        remove_radii = self.get_remove_radii(game)
        nodes = [z for y in remove_radii for x in y for z in x[0]]
        deque(map(lambda node: self.remove_full_ship_radii_1(node[0], node[1]), nodes))
        deque(map(lambda node: self.remove_partial_ship_radii_1(node[0], node[1]), nodes))
        timer.print('ship radii 1 removed')

        # This appears to decrease the result
        # Mine Radii 1 - only if not in mine
        # mine_radii = self.get_mine_radii(game.mines)
        # deque(map(lambda node: self.remove_mine_radii(node.x, node.y), mine_radii))
        # deque(map(lambda node: self.remove_partial_mine_radii(node.x, node.y), mine_radii))
        # timer.print('mine radii removed')

        # This appears to decrease the result
        # Ship Radii 2 - Only if not in mine or ship (start using same decay)
        nodes = [z for y in remove_radii for x in y for z in x[1]]
        deque(map(lambda node: self.remove_full_ship_radii_2(node[0], node[1]), nodes))
        deque(map(lambda node: self.remove_partial_ship_radii_2(node[0], node[1]), nodes))
        timer.print('ship radii 2 removed')

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
        for test_step in [t-x for x in range(-2,3) if 14 >= t-x >= 0]:
            if full_key in self.full_cannonball_nodes[test_step] or key in self.partial_cannonball_nodes[test_step]:
                return 80

        if full_key in self.full_mine_nodes or key in self.partial_mine_nodes:
            return 60

        potential_cost = 0
        if full_key in self.full_mine_radii or key in self.partial_mine_radii:
            potential_cost = 2

        if full_key in self.full_ship_nodes or key in self.partial_ship_nodes:
            cost = 40 / (1+t**2)
            return cost if cost > potential_cost else potential_cost
        elif full_key in self.full_ship_radii_1 or key in self.partial_ship_radii_1:
            cost = 20 / (1+t**2)
            return cost if cost > potential_cost else potential_cost
        elif full_key in self.full_ship_radii_2 or key in self.partial_ship_radii_2:
            cost = 10 / (1+t**2)
            return cost if cost > potential_cost else potential_cost
        else:
            return potential_cost

    def remove_cannonball_node(self, x, y, t):
        self.full_cannonball_nodes[t].add(self.encode_node_key(x, y, 0, 0))

    def remove_partial_cannonball_nodes(self, x, y, t):
        deque(map(lambda r: self.partial_cannonball_nodes[t].update(self.node_partials(x, y, r)), range(6)))

    def remove_mine_node(self, x, y):
        self.full_mine_nodes.add(self.encode_node_key(x, y, 0, 0))

    def remove_partial_mine_node(self, x, y):
        deque(map(lambda r: self.partial_mine_nodes.update(self.node_partials(x, y, r,
                    full_ignore=[self.full_mine_nodes])
                ), range(6)))

    def remove_ship_node(self, x, y):
        key = self.encode_node_key(x, y, 0, 0)
        if key not in self.full_mine_nodes:
            self.full_ship_nodes.add(key)

    def remove_partial_ship_node(self, x, y):
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

        nodes.append((ship.x, ship.y))
        nodes.append((bow.x, bow.y))
        nodes.append((stern.x, stern.y))

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

        return nodes

    def node_partials(self, x, y, r, full_ignore=None, partial_ignore=None):
        neighbour = Position(x,y).get_neighbor(r)
        far_neighbour = neighbour.get_neighbor(r)
        further_neighbour = far_neighbour.get_neighbor(r)

        partial_keys = [
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

    def remove_ship_radius(self, args):
        ship_center = args[0]
        for _ in range(args[0].speed):
            ship_center = ship_center.get_neighbor(args[0].rotation)

        remove = False
        for my_ship in args[1]:
            if my_ship.id != args[0].id:
                if ship_center.calculate_distance_between(my_ship) <= 5:
                    remove = True

        if remove:
            return [self.get_ship_radius(x) for x in [(i, ship_center) for i in range(6)]]
        else:
            return None

    def get_ship_radius(self, args):
        neighbour_position = args[1].get_neighbor(args[0])

        if 0 <= neighbour_position.y < self.map.y and 0 <= neighbour_position.x < self.map.x:
            rad_1 = [(neighbour_position.x, neighbour_position.y)]

            rad_2 = []
            for x in range(2):
                new_neighbour_position = neighbour_position.get_neighbor(self.map.abs_rotation(args[0] + x))
                if 0 <= new_neighbour_position.y < self.map.y and 0 <= new_neighbour_position.x < self.map.x:
                    rad_2.append((new_neighbour_position.x, new_neighbour_position.y))
            return rad_1, rad_2
        return [[], []]

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
            for neighbour in self.map.neighbours(point, search_range=x):
                if self.in_grid(neighbour):
                    count = 0
                    for speed in range(3):
                        for rotation in range(6):
                            count += len(self.neighbours(self.encode_node_key(neighbour.x, neighbour.y, rotation, speed)))
                    available.append([neighbour, count])
            if len(available) > 0:
                break

        return sorted(available, key=lambda x: x[1], reverse=True)[0][0]

    def check_for_goal(self, cur, pre, entity):
        # The pre-state should not have any points
        # Speed 1 adds two to the base
        # Speed 2 adds three to the base
        # Rotate on the new point
        if entity.x == cur.x and entity.y == cur.y:
            return True

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

        if cur.rotation != pre.rotation:
            bow = cur.get_neighbor(cur.rotation)
            if entity.x == bow.x and entity.y == bow.y:
                # log('Got with bow_rot')
                return True

            stern = cur.get_neighbor(self.map.abs_rotation(cur.rotation + 3))
            if entity.x == stern.x and entity.y == stern.y:
                # log('Got with stern_rot')
                return True

        return False

    def find_path(self, ship, entity, waypoints=None):
        waypoints = [entity] if waypoints is None else [entity] + waypoints

        if not self.in_grid(entity):
            return False

        frontier = []
        heapq.heappush(frontier, (0, (self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0), 0)))
        cost_so_far = {}
        came_from = {}
        came_from[self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0)] = None
        cost_so_far[self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0)] = 0

        solutions = []
        ok_solutions = []

        distance_costs = [waypoints[x].calculate_distance_between(waypoints[x+1]) for x in range(len(waypoints)-1)] + [0]

        points_checked = 0
        while len(frontier) > 0:
            priority, current_timestep = heapq.heappop(frontier)
            current = current_timestep[0]
            timestep = current_timestep[1]

            points_checked += 1
            if points_checked % 20 == 0:
                log('WARNING: path > {}'.format(points_checked))
                if points_checked % 150 == 0:
                    return False

            current_waypoint, cur_x, cur_y, cur_r, cur_s = self.decode_node_key(current)
            current_no_w = current - (current_waypoint*1000000)

            # Check if we have reached the last waypoint
            if came_from[current] is not None:
                pre_w, pre_x, pre_y, pre_r, pre_s = self.decode_node_key(came_from[current])
                final_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s), Position(pre_x, pre_y, pre_r, pre_s), waypoints[-1])
                if final_point:
                    final_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint)
                    solutions.append(final_point)
                    if len(solutions) > 3:
                        break
            else:
                if cur_x == entity.x and cur_y == entity.y and cur_r == entity.rotation and cur_s == entity.speed:
                    final_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint)
                    solutions.append(final_point)
                    if len(solutions) > 3:
                        break

            # Check if we have reached the next waypoint
            if came_from[current] is not None and current_waypoint < (len(waypoints)-1):
                pre_w, pre_x, pre_y, pre_r, pre_s = self.decode_node_key(came_from[current])
                current_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s),
                                                  Position(pre_x, pre_y, pre_r, pre_s), waypoints[current_waypoint])
                if current_waypoint == 0:
                    ok_solutions.append(current_point)
                if current_point:
                    current_waypoint += 1
            elif current_waypoint < (len(waypoints)-1):
                if cur_x == entity.x and cur_y == entity.y and cur_r == entity.rotation and cur_s == entity.speed:
                    if current_waypoint == 0:
                        current_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint)
                        ok_solutions.append(current_point)
                    current_waypoint += 1

            for next in self.neighbours(current_no_w):
                next_key = self.encode_node_key(next.x, next.y, next.rotation, next.speed, current_waypoint)
                next_key_no_w = self.encode_node_key(next.x, next.y, next.rotation, next.speed)

                straight_mod, speed_mod = 1, 1
                hex_cost = self.get_hex_cost(next_key_no_w, timestep)

                if hex_cost > 0:
                    add_cost = hex_cost
                else:
                    # Speed modifier - we prefer moving over not moving
                    speed_mod = 1.2 if cur_s > 0 else 1
                    # Can we make a non-movement action?
                    if next.speed == cur_s and next.speed > 0 and next.rotation == cur_r:
                        straight_mod = 1
                    else:
                        straight_mod = 1.6
                    add_cost = 0

                cost = (1 * speed_mod * straight_mod) + add_cost

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
            log('No path from ({},{}) to ({},{})'.format(ship.x, ship.y, entity.x, entity.y))
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
                w, x, y, r, s = self.decode_node_key(key)
                current_point = (x, y, r, s)
                path.append(current_point)
                current_key = key

        path.append((ship.x, ship.y, ship.rotation, ship.speed))

        log(str(path))

        return path


class Map:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.grid = [[0 for _ in range(x)] for _ in range(y)]

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
        for mine in mines:
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

    def neighbours(self, position, safe=True, search_range=1):
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

    @staticmethod
    def abs_rotation(rotation):
        return (12 + rotation) % 6

    def out_of_range(self, position):
        return position.x >= self.x or position.y >= self.y or position.x < 0 or position.y < 0


class Cube:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Entity:
    __metaclass__ = abc.ABCMeta

    def __init__(self, id, x, y):
        self.id = id
        self.x = x
        self.y = y

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

        self.waypoints = [Position(5,5),
                          Position(11, 4),
                          Position(17,5),
                          Position(18, 10),
                          Position(17,15),
                          Position(11, 16),
                          Position(5,15),
                          Position(4,10)
                          ]
        self.waypoint = None

        self.cannonball = 10
        self.mine = 10

        self.action = None

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

                if self.graph.x_max < estimated_location.x:
                    estimated_location.x = self.graph.x_max-1
                    #log('mod_x_max')
                if self.graph.y_max < estimated_location.y:
                    estimated_location.y = self.graph.y_max-1
                    #log('mod_y_max')
                if 0 > estimated_location.x:
                    estimated_location.x = 0
                    #log('mod_x_min')
                if 0 > estimated_location.y:
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

        self.cannonball = 0
        self.action = self._print_fire

        if self.speed > 0:
            rem_forward = True
        else:
            rem_forward = False

        for neighbour in self.graph.map.neighbours(Position(self.fire_x, self.fire_y)):
            if 0 <= neighbour.y < self.graph.map.y and 0 <= neighbour.x < self.graph.map.x and self.graph.map.grid[neighbour.y][neighbour.x] == MINE:
                self.fire_x, self.fire_y = neighbour.x, neighbour.y
                #log('Firing on mine')
                break

        #log('FIRE : estimated_time:{} : target_point:({},{}) : distance:{}'.format(fire_time, self.fire_x, self.fire_y, distance))

        deque(map(lambda node: self.graph.remove_ship_node(node[0], node[1]),
                  self.graph.get_ship_nodes(self, rem_forward=rem_forward)))

        return True

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
            return False
        self.navigate_action = self.determine_move(path[-2:])
        self.action = self._print_navigate

        log('navigate_action: {}'.format(self.navigate_action))
        return True

    def should_avoid(self, enemy_ships):
        highest_health_enemy = max([[x.rum, x] for i, x in enemy_ships.items()], key=lambda x: x[0])
        if self.rum > highest_health_enemy[0]:
            return True, highest_health_enemy[1]
        return False, highest_health_enemy[1]

    def ordered_waypoints(self, enemy_ships):
        avoid, enemy_ship = self.should_avoid(enemy_ships)
        return sorted(range(len(self.waypoints)),
                      key=lambda x: Position(self.waypoints[x].x, self.waypoints[x].y).calculate_distance_between(enemy_ship),
                      reverse=avoid)

    def waypoint_move(self, enemy_ships):
        #log(enemy_ships)
        if self.waypoint is None or self.calculate_distance_between(self.waypoints[self.waypoint]) <= 3:
            ordered_waypoints = self.ordered_waypoints(enemy_ships)[:3]

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

        if self.graph.in_grid(Position(self.waypoints[self.waypoint].x, self.waypoints[self.waypoint].y)):
            nav = Position(self.waypoints[self.waypoint].x, self.waypoints[self.waypoint].y)
        else:
            nav = self.graph.find_closest(Position(self.waypoints[self.waypoint].x, self.waypoints[self.waypoint].y))

        return self.navigate(nav)

    def guaranteed_mine_hit(self, ships):
        mine_position = self.get_neighbor(self.graph.map.abs_rotation(self.rotation+3)).get_neighbor(self.graph.map.abs_rotation(self.rotation+3))

        for ship in ships.values():
            if ship.calculate_distance_between(mine_position) > 5:
                continue

            rotation_point = ship

            speed_1 = ship.get_neighbor(ship.graph.map.abs_rotation(ship.rotation)).get_neighbor(ship.graph.map.abs_rotation(ship.rotation))
            if mine_position.x == speed_1.x and mine_position.y == speed_1.y:
                # log('Got with speed_1')
                return True

            if ship.speed > 0:
                rotation_point = ship.get_neighbor(ship.graph.map.abs_rotation(ship.rotation))
                speed_2 = speed_1.get_neighbor(ship.graph.map.abs_rotation(ship.rotation))
                if mine_position.x == speed_2.x and mine_position.y == speed_2.y:
                    # log('Got with speed_2')
                    return True

                if ship.speed > 1:
                    rotation_point = speed_1

            for rotation in [-1, 1]:
                bow_stern = rotation_point.get_neighbor(ship.graph.map.abs_rotation(ship.rotation + rotation))
                if mine_position.x == bow_stern.x and mine_position.y == bow_stern.y:
                    # log('Got with bow_rot')
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

    def run(self, load=False):
        while True:
            time_a = time.time()

            self.game.update_map(load=load)

            # Assign barrels
            taken_barrels = set()
            assigned_ships = set()
            if len(self.game.barrels) > 0:
                barrel_barrel_distances = self.barrel_barrel_distances(self.game.barrels)
                barrel_ship_distances = self.barrel_ship_distances(self.game.my_ships, self.game.barrels)
                for i, barrel_ship in enumerate(barrel_ship_distances):
                    if len(taken_barrels) >= len(self.game.barrels) or len(assigned_ships) >= len(self.game.my_ships):
                        break
                    if barrel_ship[0].id in taken_barrels or barrel_ship[1].id in assigned_ships:
                        continue

                    log('ship ({}) navigating to barrel ({})'.format(barrel_ship[1].id, barrel_ship[0].id))

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

                        next_barrel = barrel_ship[1].waypoints[barrel_ship[1].next_waypoint]

                    result = barrel_ship[1].navigate(barrel_ship[0], [next_barrel])
                    if result:
                        assigned_ships.add(barrel_ship[1].id)
                        taken_barrels.add(barrel_ship[0].id)

                        log(str(barrel_ship[0].id))
                        log(str(barrel_barrel_distances[barrel_ship[0].id]))

                        for dist_barrel in barrel_barrel_distances[barrel_ship[0].id]:
                            if dist_barrel[1] <= 2:
                                taken_barrels.add(dist_barrel[0].id)
                                log('taken: {}'.format(dist_barrel[0].id))
                            else:
                                break

            for id, ship in self.game.my_ships.items():
                timer.print('ship {}'.format(id))
                closest_ship, distance_to_closest_ship = self.get_closest_enemy_ship(ship, self.game.enemy_ships)

                if ship.navigate_action is None or ship.action is None:
                    # Start a grid based movement pattern
                    log('ship ({}) grid based movement'.format(id))
                    result = ship.waypoint_move(self.game.enemy_ships)
                    if not result:
                        ship.no_action()

                if ship.navigate_action == 'WAIT' or ship.navigate_action is None or ship.action is None:
                    lay_mine=MAYBE
                    if ship.can_lay_mine():
                        if not ship.guaranteed_mine_hit(self.game.my_ships):
                            if ship.guaranteed_mine_hit(self.game.enemy_ships):
                                log('Guaranteed Enemy')
                                lay_mine = YES
                        else:
                            log('Guaranteed Me')
                            lay_mine = NO

                    if ship.can_fire() and lay_mine != YES:
                        log('ship ({}) firing'.format(id))
                        result = ship.fire(closest_ship)
                        if result:
                            continue

                    if lay_mine != NO:
                        log('ship ({}) laying mine'.format(id))
                        ship.lay_mine()
                    else:
                        log('ship ({}) no_action'.format(id))
                        ship.no_action()

            for id, ship in self.game.my_ships.items():
                log(str(ship.action))
                ship.print_action()

            time_b = time.time()
            dif = time_b - time_a
            timer.print('done')
            log('Loop took {}ms'.format(round(dif*1000,2)))


if __name__ == "__main__":
    ai = AI()
    ai.run()