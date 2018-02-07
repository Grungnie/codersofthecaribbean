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

    def update_map(self, load='3'):
        #log('Getting inputs')

        self.get_all_inputs(load=load)
        #log('Got all inputs')
        timer.print('inputs')

        self.clear_last_turn()
        #log('Cleared last turn')
        timer.print('clear')

        self.my_ship_count = int(self.inputs['my_ship_count'])  # the number of remaining ships
        self.entity_count = int(self.inputs['entity_count'])  # the number of entities (e.g. ships, mines or cannonballs)

        self.get_entities()
        #log('Got Entities')

        timer.print('entities')

        self.graph.refresh()
        #log('Graph refreshed')

        timer.print('graph')

        self.map.update(self)
        #log('Map updated')

        timer.print('update')

        self.remove_entities_from_graph()
        #log('Entities removed from graph')

        timer.print('remove')

    def remove_entities_from_graph(self):
        # for mine in self.mines:
        #     self.graph.remove_node(mine.x, mine.y, source=MINE)
        # timer.print('mine')
        # for id, ship in self.enemy_ships.items():
        #     self.graph.remove_ship_from_graph(ship)
        # timer.print('ship')
        # for cannonball in self.cannonballs:
        #     self.graph.remove_node(cannonball.x, cannonball.y, source=CANNONBALL, timestep=cannonball.impact)
        # timer.print('cannonball')

        deque(map(lambda mine: self.graph.remove_node(mine.x, mine.y, source=MINE), self.mines))
        timer.print('mine')
        deque(map(lambda ship: self.graph.remove_ship_from_graph(ship), self.enemy_ships.values()))
        timer.print('ship')
        deque(map(lambda cannonball: self.graph.remove_node(cannonball.x, cannonball.y, source=CANNONBALL, timestep=cannonball.impact), self.cannonballs))
        timer.print('cannonball')

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

        self.mine_nodes = set()
        self.high_ship_nodes = set()
        self.low_ship_nodes = set()
        self.cannonball_nodes = [set() for _ in range(15)]
        self.cannonball_soft_nodes = [set() for _ in range(15)]

        # For each combination of x, y, direction and speed find neighbours
        for col, row_list in enumerate(self.map.grid):
            for row , corr_value in enumerate(row_list):
                for rot in range(6):
                    for spd in range(3):
                        self.graph[self.encode_node_key(row, col, rot, spd)] = self.find_neighbours(row, col, rot, spd)

    def refresh(self):
        self.mine_nodes.clear()
        self.high_ship_nodes.clear()
        self.low_ship_nodes.clear()

        for x in range(15):
            self.cannonball_nodes[x].clear()
            self.cannonball_soft_nodes[x].clear()

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

    def remove_node(self, row, col, dir=None, spd=None, ship=True, source=None, timestep=None):
        dir = list(range(6)) if dir is None else dir
        spd = list(range(3)) if spd is None else spd

        # remove the node and all paths to the node from the index
        for _dir in dir:
            for _spd in spd:
                if source == MINE:
                    self.mine_nodes.add(self.encode_node_key(row, col, _dir, _spd))
                elif source == HIGH_SHIP:
                    self.high_ship_nodes.add(self.encode_node_key(row, col, _dir, _spd))
                elif source == LOW_SHIP:
                    self.low_ship_nodes.add(self.encode_node_key(row, col, _dir, _spd))
                elif source == CANNONBALL:
                    self.cannonball_nodes[timestep].add(self.encode_node_key(row, col, _dir, _spd))
                    #if 0 <= row < self.map.y and 0 <= col < self.map.x and self.map.grid[row][col] == MINE:
                        #log('Adding soft cannonball')
                        #for neighbour in self.map.neighbours(Position(row, col)):
                        #    self.remove_node(neighbour.x, neighbour.y, source=SOFT_CANNONBALL, timestep=timestep)
                elif source == SOFT_CANNONBALL:
                    self.cannonball_soft_nodes[timestep].add(self.encode_node_key(row, col, _dir, _spd))
                else:
                    raise(Exception('Invalid type'))


        # If we are removing the node for a ship we need to remove all possible ship positions
        # Every neighbour with a angle pointing directly at the point or directly away from the point
        if ship:
            point = Position(row, col)
            for i in range(6):
                neighbour = point.get_neighbor(i)
                self.remove_node(neighbour.x, neighbour.y, dir=[i, self.map.abs_rotation(i+3)], ship=False, source=source, timestep=timestep)

                far_neighbour = neighbour.get_neighbor(i)
                self.remove_node(far_neighbour.x, far_neighbour.y, dir=[self.map.abs_rotation(i+3)], spd=[1,2], ship=False, source=source, timestep=timestep)

                further_neighbour = far_neighbour.get_neighbor(i)
                self.remove_node(further_neighbour.x, further_neighbour.y, dir=[self.map.abs_rotation(i+3)], spd=[2], ship=False, source=source, timestep=timestep)

    def remove_ship_from_graph(self, ship, rem_forward=True, rem_port=True, rem_starboard=True):
        bow = ship.get_neighbor(ship.rotation)
        stern = ship.get_neighbor(self.map.abs_rotation(ship.rotation + 3))

        self.remove_node(ship.x, ship.y, source=HIGH_SHIP)
        self.remove_node(stern.x, stern.y, source=HIGH_SHIP)

        if rem_forward:
            forward_move = bow.get_neighbor(ship.rotation)
            self.remove_node(forward_move.x, forward_move.y, source=HIGH_SHIP)
            if ship.speed == 2:
                fast_move = forward_move.get_neighbor(ship.rotation)
                self.remove_node(fast_move.x, fast_move.y, source=HIGH_SHIP)

        if ship.speed == 0:
            rotation_point = ship
        elif ship.speed == 1:
            rotation_point = bow
        else:
            rotation_point = forward_move

        if rem_port:
            port_bow = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation + 1))
            self.remove_node(port_bow.x, port_bow.y, source=HIGH_SHIP)
            port_stern = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation + 4))
            self.remove_node(port_stern.x, port_stern.y, source=HIGH_SHIP)

        if rem_starboard:
            port_bow = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation - 1))
            self.remove_node(port_bow.x, port_bow.y, source=HIGH_SHIP)
            port_stern = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation - 4))
            self.remove_node(port_stern.x, port_stern.y, source=HIGH_SHIP)

    def neighbours(self, key):
        if key in self.graph:
            return self.graph[key]
        else:
            return []

    def in_grid(self, entity):
        for rot in range(6):
            for spd in range(2):
                key = self.encode_node_key(entity.x, entity.y, rot, spd)
                if key not in self.mine_nodes and key not in self.high_ship_nodes and key not in self.cannonball_nodes:
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

        start_time = time.time()
        if not self.in_grid(entity):
            return False

        frontier = []
        heapq.heappush(frontier, (0, (self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0), 0)))
        cost_so_far = {}
        came_from = {}
        came_from[self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0)] = None
        cost_so_far[self.encode_node_key(ship.x, ship.y, ship.rotation, ship.speed, 0)] = 0

        distance_costs = [waypoints[x].calculate_distance_between(waypoints[x+1]) for x in range(len(waypoints)-1)] + [0]

        final_point = None

        # If the node the ship is currently on has been removed we need to replace it.
        # if (ship.x, ship.y, ship.rotation, ship.speed) not in self.graph:
        #     self.graph[(ship.x, ship.y, ship.rotation, ship.speed)] = self.find_neighbours(ship.x, ship.y, ship.rotation, ship.speed)

        points_checked = 0
        while len(frontier) > 0:
            #log('time 1: {:0.2f}'.format((time.time() - start_time)*10000, 2))
            #start_time = time.time()
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

            log('{} {} {} {} {}'.format(current_waypoint, cur_x, cur_y, cur_r, cur_s))

            # Check if we have reached the last waypoint
            if came_from[current] is not None:
                pre_w, pre_x, pre_y, pre_r, pre_s = self.decode_node_key(came_from[current])
                final_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s), Position(pre_x, pre_y, pre_r, pre_s), waypoints[-1])
                if final_point:
                    final_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint)
                    break
            else:
                if cur_x == entity.x and cur_y == entity.y and cur_r == entity.rotation and cur_s == entity.speed:
                    final_point = self.encode_node_key(cur_x, cur_y, cur_r, cur_s, current_waypoint)
                    break

            # Check if we have reached the next waypoint
            if came_from[current] is not None:
                pre_w, pre_x, pre_y, pre_r, pre_s = self.decode_node_key(came_from[current])

                current_point = self.check_for_goal(Position(cur_x, cur_y, cur_r, cur_s),
                                                  Position(pre_x, pre_y, pre_r, pre_s), waypoints[current_waypoint])
                if current_point:
                    current_waypoint += 1
            else:
                if cur_x == entity.x and cur_y == entity.y and cur_r == entity.rotation and cur_s == entity.speed:
                    current_waypoint += 1

            #log('time 2: {:0.2f}'.format((time.time() - start_time)*10000, 2))

            for next in self.neighbours(current_no_w):
                #start_time = time.time()
                # log('next: ({},{}) {} {}'.format(next.x, next.y, next.rotation, next.speed))
                next_key = self.encode_node_key(next.x, next.y, next.rotation, next.speed, current_waypoint)
                next_key_no_w = self.encode_node_key(next.x, next.y, next.rotation, next.speed)


                straight_mod, speed_mod = 1, 1

                #log('time 3: {:0.2f}'.format((time.time() - start_time)*10000, 4))
                #start_time = time.time()

                time_cost = False
                for test_step in [timestep-x for x in range(-2,3) if 14 >= timestep-x >= 0 ]:
                    if next_key_no_w in self.cannonball_nodes[test_step]:
                        time_cost = True
                        break

                #log('time 4: {:0.2f}'.format((time.time() - start_time)*10000, 4))
                #start_time = time.time()

                if time_cost:
                    add_cost = 80
                elif next_key_no_w in self.mine_nodes:
                    add_cost = 60       # This is a little more than a full back out of a hole and moving round
                elif next_key_no_w in self.high_ship_nodes:
                    add_cost = 40 / (1 + timestep**2)
                else:
                    soft_time_cost = False
                    for test_step in [timestep - x for x in range(-2, 3) if 14 >= timestep - x >= 0]:
                        if next_key_no_w in self.cannonball_soft_nodes[test_step]:
                            soft_time_cost = True
                            break

                    if soft_time_cost:
                        add_cost = 2
                    else:
                        # Speed modifier - we prefer moving over not moving
                        speed_mod = 1.2 if cur_s > 0 else 1

                        # Can we make a non-movement action?
                        if next.speed == cur_s and next.speed > 0 and next.rotation == cur_r:
                            straight_mod = 1
                        else:
                            straight_mod = 1.3

                        add_cost = 0

                #log('time 5: {:0.2f}'.format((time.time() - start_time)*10000, 4))
                #start_time = time.time()

                cost = (1 * speed_mod * straight_mod) + add_cost

                new_cost = cost_so_far[current] + cost
                # log('cost_so_far: {}, new_cost: {}'.format(cost_so_far[(current[0], current[1])], new_cost))
                if next_key not in cost_so_far or new_cost < cost_so_far[next_key]:
                    cost_so_far[next_key] = new_cost
                    # log('cost_so_far: {}'.format(new_cost))
                    distance_cost = sum(distance_costs[current_waypoint:]) * 1.4
                    target_cost = waypoints[current_waypoint].calculate_distance_between(next) * 1.4
                    priority = new_cost + target_cost + distance_cost
                    # log('priority: {}'.format(priority))

                    # log('{} {} {} {}'.format(current[0], current[1], current[2], current[3]))
                    # log('{} {} {} {}'.format(next.x, next.y, next.rotation, next.speed))
                    heapq.heappush(frontier, (priority, (next_key, timestep+1)))
                    # log('frontier.put({}, ({}, {}))'.format(priority, next.x, next.y))
                    came_from[next_key] = current
                    # log('came_from: {} {} = {}'.format(next.x, next.y, current))



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

        self.graph.remove_ship_from_graph(self, rem_forward=rem_forward)
        return True

    def _print_fire(self):
        print('FIRE {} {}'.format(self.fire_x, self.fire_y))

    def can_fire(self):
        return self.cannonball > 1

    def lay_mine(self):
        self.mine = 0
        self.action = self._print_mine

        if self.speed > 0:
            rem_forward = True
        else:
            rem_forward = False

        self.graph.remove_ship_from_graph(self, rem_forward=rem_forward)

    def _print_mine(self):
        print('MINE')

    def no_action(self):
        self.navigate_action = 'WAIT'
        self.action = self._print_no_action

        if self.speed > 0:
            rem_forward = True
        else:
            rem_forward = False

        self.graph.remove_ship_from_graph(self, rem_forward=rem_forward)

    def _print_no_action(self):
        print('WAIT')

    def can_lay_mine(self):
        return self.mine > 3

    def move(self, entity):
        self.move_x, self.move_y = entity.x, entity.y
        self.action = self._print_move

    def _print_navigate(self):
        print(self.navigate_action)

    def _print_move(self):
        #print(['STARBOARD', 'FASTER'][random.randint(0,1)])
        print('MOVE {} {}'.format(self.move_x, self.move_y))

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
        return sorted(range(len(self.waypoints)), key=lambda x: Position(self.waypoints[x].x, self.waypoints[x].y).calculate_distance_between(enemy_ship), reverse=avoid)

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

        self.graph.remove_ship_from_graph(self, rem_forward=rem_forward, rem_port=rem_port, rem_starboard=rem_starboard)

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
        return "Entity {} (id: {}) at position: (x = {}, y = {})"\
            .format(self.__class__.__name__, self.id, self.x, self.y)


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

    def run(self):
        while True:
            time_a = time.time()

            self.game.update_map(load=False)

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
                    if ship.can_fire():
                        log('ship ({}) firing'.format(id))
                        result = ship.fire(closest_ship)
                        if result:
                            continue
                    if ship.can_lay_mine():
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