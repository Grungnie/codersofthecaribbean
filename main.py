import sys
import random
import abc
import random
import json
import copy
import time

from queue import PriorityQueue

MINE = 1
MY_SHIP = 2
ENEMY_SHIP = 3
BARREL = 4
HIGH_SHIP = 5   # High probability ship location
LOW_SHIP = 6    # Low probability ship_location
CANNONBALL = 7


def log(info):
    print(info, file=sys.stderr, flush=True)


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
        #self.my_ships = {}
        self.enemy_ships = {}
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
        #log('Getting inputs')

        self.get_all_inputs(load=load)
        #log('Got all inputs')

        self.clear_last_turn()
        #log('Cleared last turn')

        self.my_ship_count = int(self.inputs['my_ship_count'])  # the number of remaining ships
        self.entity_count = int(self.inputs['entity_count'])  # the number of entities (e.g. ships, mines or cannonballs)

        self.get_entities()
        log('Got Entities')

        self.graph.refresh()
        log('Graph refreshed')

        self.map.update(self)
        log('Map updated')

        self.remove_entities_from_graph()
        log('Entities removed from graph')

    def remove_entities_from_graph(self):
        for mine in self.mines:
            self.graph.remove_node(mine.x, mine.y, source=MINE)

        for id, ship in self.enemy_ships.items():
            self.graph.remove_ship_from_graph(ship)

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
        seen_ships = []

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
                   seen_ships.append(entity_id)
                else:
                    self.my_ships[entity_id] = Ship(entity_id, x, y, arg_1, arg_2, arg_3, self.graph)
                    seen_ships.append(entity_id)
            elif entity_type == 'SHIP' and arg_4 == 0:
                if entity_id in self.my_ships:
                   self.enemy_ships[entity_id].update_ship(x, y, arg_1, arg_2, arg_3)
                   seen_ships.append(entity_id)
                else:
                    self.enemy_ships[entity_id] = Ship(entity_id, x, y, arg_1, arg_2, arg_3, self.graph)
                    seen_ships.append(entity_id)
            elif entity_type == 'BARREL':
                self.barrels.append(Barrel(entity_id, x, y, arg_1))
            elif entity_type == 'CANNONBALL':
                self.cannonballs.append(Cannonball(entity_id, x, y, arg_1, arg_2))
            elif entity_type == 'MINE':
                self.mines.append(Mine(entity_id, x, y))
            else:
                log('Invalid entity type ({})'.format(entity_type))
                raise(Exception('Invalid entity type'))

        #log('Loaded Entities')

        all_ships = [id for id, ship in self.my_ships.items()]

        for ship_id in all_ships:
            if ship_id not in seen_ships:
                del self.my_ships[ship_id]


class Graph:
    def __init__(self, map):
        self.x_max = map.x
        self.y_max = map.y
        self.map = map
        self.graph = {}

        self.mine_nodes = []
        self.high_ship_nodes = []
        self.low_ship_nodes = []
        self.cannonball_nodes = []

        # For each combination of x, y, direction and speed find neighbours
        for col, row_list in enumerate(self.map.grid):
            for row , corr_value in enumerate(row_list):
                for rot in range(6):
                    for spd in range(3):
                        self.graph[(row, col, rot, spd)] = self.find_neighbours(row, col, rot, spd)

        self.original_graph = copy.deepcopy(self.graph)

    def refresh(self):
        #self.graph.clear()

        # For each combination of x, y, direction and speed find neighbours
        for col, row_list in enumerate(self.map.grid):
            for row , corr_value in enumerate(row_list):
                for rot in range(6):
                    for spd in range(3):
                        self.graph[(row, col, rot, spd)] = self.original_graph[(row, col, rot, spd)]

        #self.graph = copy.deepcopy(self.original_graph)

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
            # # Bow hit after rotate
            # bow_pos = position.get_neighbor(self.map.abs_rotation(position.rotation + i))
            # # Stern hit after rotate
            # stern_pos = position.get_neighbor(self.map.abs_rotation(position.rotation + i + 3))

            #There are actually valid locations
            # if not self.map.out_of_range(bow_pos) and \
            #         not self.map.out_of_range(stern_pos):

            neighbours.append((position.x, position.y, i, 0))

        #if (row, col, rot) == (20,17,1,0)

        new_pos = position.get_neighbor(position.rotation)#.get_neighbor(position.rotation)

        if not self.map.out_of_range(new_pos):
            new_position = position.get_neighbor(position.rotation)
            neighbours.append((new_position.x, new_position.y, position.rotation, 1))

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
                neighbours.append((neighbour_position.x, neighbour_position.y, i, 1))

        # Can the boat slow down from 1 to 0
        neighbours.append((position.x, position.y, position.rotation, 0))

        fast_position = position.get_neighbor(position.rotation).get_neighbor(position.rotation)
        if not self.map.out_of_range(fast_position):
            neighbours.append((fast_position.x, fast_position.y, position.rotation, 2))

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
                neighbours.append((neighbour_position.x, neighbour_position.y, i, 2))

        # Can the boat slow down from 1 to 0
        neighbours.append((position.x, position.y, position.rotation, 1))

        return neighbours

    def remove_node(self, row, col, dir=None, spd=None, ship=True, source=None):
        dir = list(range(6)) if dir is None else dir
        spd = list(range(3)) if spd is None else spd

        # remove the node and all paths to the node from the index
        for _dir in dir:
            for _spd in spd:
                if (row, col, _dir, _spd) in self.graph:
                    #if source is None or source is not None:        # This feature was removed due to time constraints
                    del self.graph[(row, col, _dir, _spd)]
                    # elif source == MINE:
                    #     self.mine_nodes.append((row, col, _dir, _spd))
                    # elif source == HIGH_SHIP:
                    #     self.high_ship_nodes.append((row, col, _dir, _spd))
                    # elif source == LOW_SHIP:
                    #     self.low_ship_nodes.append((row, col, _dir, _spd))
                    # elif source == CANNONBALL:
                    #     self.cannonball_nodes.append((row, col, _dir, _spd))
                    # else:
                    #     raise(Exception('{} is not a valid type'))

        # If we are removing the node for a ship we need to remove all possible ship positions
        # Every neighbour with a angle pointing directly at the point or directly away from the point
        if ship:
            point = Position(row, col)
            for i in range(6):
                neighbour = point.get_neighbor(i)
                self.remove_node(neighbour.x, neighbour.y, dir=[i, self.map.abs_rotation(i+3)], ship=False, source=source)

                far_neighbour = neighbour.get_neighbor(i)
                self.remove_node(far_neighbour.x, far_neighbour.y, dir=[self.map.abs_rotation(i+3)], spd=[1,2], ship=False, source=source)

                further_neighbour = far_neighbour.get_neighbor(i)
                self.remove_node(further_neighbour.x, further_neighbour.y, dir=[self.map.abs_rotation(i + 3)], spd=[2], ship=False, source=source)

    def remove_ship_from_graph(self, ship, rem_forward=True, rem_port=True, rem_starboard=True):
        #start_remove = time.time()
        #log('removing ship {}'.format(ship.id))
        bow = ship.get_neighbor(ship.rotation)
        stern = ship.get_neighbor(self.map.abs_rotation(ship.rotation + 3))

        #log('remove ({},{})'.format(ship.x, ship.y))
        self.remove_node(ship.x, ship.y, source=HIGH_SHIP)

        #log('remove ({},{})'.format(stern.x, stern.y))
        self.remove_node(stern.x, stern.y, source=HIGH_SHIP)

        if rem_forward:
            forward_move = bow.get_neighbor(ship.rotation)
            #log('remove ({},{})'.format(forward_move.x, forward_move.y))
            self.remove_node(forward_move.x, forward_move.y, source=HIGH_SHIP)

        if ship.speed == 0:
            rotation_point = ship
        else:
            rotation_point = bow

        if rem_port:
            port = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation + 1))
            #log('remove ({},{})'.format(port.x, port.y))
            self.remove_node(port.x, port.y, source=HIGH_SHIP)

        if rem_starboard:
            starboard = rotation_point.get_neighbor(self.map.abs_rotation(ship.rotation - 1))
            #log('remove time ({})'.format(time.time() - start_remove))
            #log('remove ({},{})'.format(starboard.x, starboard.y))
            self.remove_node(starboard.x, starboard.y, source=HIGH_SHIP)
            #log('remove time ({})'.format(time.time() - start_remove))

        #log('Ship removed')
        #log('end remove ({})'.format(time.time()-start_remove))

    def neighbours(self, row, col, rot, spd):
        pos_neighbours = []
        if (row, col, rot, spd) in self.graph:
            neighbours = self.graph[(row, col, rot, spd)]
        else:
            return []
        for neighbour in neighbours:
            pos_neighbours.append(Position(neighbour[0], neighbour[1], neighbour[2], neighbour[3]))
        return pos_neighbours

    def in_grid(self, entity):
        for rot in range(6):
            for spd in range(2):
                if (entity.x, entity.y, rot, spd) in self.graph:
                    return True
        return False

    def find_closest(self, point):
        available = []
        for neighbour in self.map.neighbours(point):
            if self.in_grid(neighbour):
                count = 0
                for speed in range(3):
                    for rotation in range(6):
                        count += len(self.neighbours(neighbour.x, neighbour.y, rotation, speed))
                available.append([neighbour, count])
        return sorted(available, key=lambda x: x[1], reverse=True)[0][0]

    def find_path(self, ship, entity):
        log('Finding path')
        #log(str(self.high_ship_nodes))
        #log(str(self.mine_nodes))

        if not self.in_grid(entity):
            return False

        frontier = PriorityQueue()
        frontier.put((0, (ship.x, ship.y, ship.rotation, ship.speed)))
        cost_so_far = {}
        came_from = {}
        came_from[(ship.x, ship.y, ship.rotation, ship.speed)] = None
        cost_so_far[(ship.x, ship.y, ship.rotation, ship.speed)] = 0

        # If the node the ship is currently on has been removed we need to replace it.
        if (ship.x, ship.y, ship.rotation, ship.speed) not in self.graph:
            self.graph[(ship.x, ship.y, ship.rotation, ship.speed)] = self.find_neighbours(ship.x, ship.y, ship.rotation, ship.speed)

        points_checked = 0
        while not frontier.empty():
            priority, current = frontier.get()
            #log('current: {}'.format(current))

            points_checked += 1
            if points_checked % 20 == 0:
                log('WARNING: path > {}'.format(points_checked))

                if points_checked % 400 == 0:
                    return False

            if current[0] == entity.x and current[1] == entity.y:
                # log('break')
                break

            for next in self.neighbours(current[0], current[1], current[2], current[3]):
                # log('next: ({},{}) {} {}'.format(next.x, next.y, next.rotation, next.speed))

                # Speed modifier - we prefer moving over not moving
                speed_mod = 1 if current[3] > 0 else 1.2

                # Prefer straight moving moves over non-straight
                if next.speed == current[3] and next.speed > 0 and next.rotation == current[2]:
                    straight_mod = 1
                else:
                    straight_mod = 1.2

                # if next in self.mine_nodes or next in self.high_ship_nodes:
                #     add_cost = 20
                #     log('Added')
                # else:
                #     add_cost = 0

                cost = (1 * speed_mod * straight_mod)# + add_cost

                new_cost = cost_so_far[(current[0], current[1], current[2], current[3])] + cost
                # log('cost_so_far: {}, new_cost: {}'.format(cost_so_far[(current[0], current[1])], new_cost))
                if (next.x, next.y, next.rotation, next.speed) not in cost_so_far or new_cost < cost_so_far[(next.x, next.y, next.rotation, next.speed)]:
                    if (next.x, next.y, next.rotation, next.speed) not in self.graph:
                        continue

                    cost_so_far[(next.x, next.y, next.rotation, next.speed)] = new_cost
                    # log('cost_so_far: {}'.format(new_cost))
                    priority = new_cost + entity.calculate_distance_between(Position(next.x, next.y))
                    # log('priority: {}'.format(priority))
                    # log('{} {} {} {}'.format(current[0], current[1], current[2], current[3]))
                    # log('{} {} {} {}'.format(next.x, next.y, next.rotation, next.speed))
                    frontier.put((priority, (next.x, next.y, next.rotation, next.speed)))
                    # log('frontier.put({}, ({}, {}))'.format(priority, next.x, next.y))
                    came_from[(next.x, next.y, next.rotation, next.speed)] = current
                    # log('came_from: {} {} = {}'.format(next.x, next.y, current))

        log('points checked: {}'.format(points_checked))

        searching = True
        current_point = ()
        for angle in range(6):
            for speed in range(2):
                if (entity.x, entity.y, angle, speed) in came_from:
                    current_point = (entity.x, entity.y, angle, speed)
                    break

                if current_point != ():
                    break
            if current_point != ():
                break

        if current_point == ():
            return False

        path = [current_point]
        while searching:
            if came_from[current_point] is None or came_from[current_point] == (ship.x, ship.y, ship.rotation, ship.speed):
                searching = False
            else:
                path.append(came_from[current_point])
                current_point = path[-1]

        path.append((ship.x, ship.y, ship.rotation, ship.speed))

        return path


class Map:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.grid = [[0 for _ in range(x)] for _ in range(y)]

    def update(self, game):
        self.grid = [[0 for _ in range(self.x)] for _ in range(self.y)]

        self.add_mines(game.mines)
        self.add_ships(game.my_ships)
        self.add_ships(game.enemy_ships, enemy=True)
        self.add_barrels(game.barrels)

    def add_barrels(self, barrels):
        for barrel in barrels:
            self.grid[barrel.y][barrel.x] = BARREL

    def add_mines(self, mines):
        for mine in mines:
            self.grid[mine.y][mine.x] = MINE

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

    def neighbours(self, position, safe=True):
        position_neighbours = []
        for i in range(6):
            neighbour_position = position.get_neighbor(i)
            if safe:
                if 0 <= neighbour_position.y < self.x and 0 <= neighbour_position.x < self.x:
                    if self.grid[neighbour_position.y][neighbour_position.x] == 0:
                        position_neighbours.append(position.get_neighbor(i))
            else:
                if 0 <= neighbour_position.y < self.x and 0 <= neighbour_position.x < self.x:
                    position_neighbours.append(position.get_neighbor(i))
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
        self.rotation = rotation
        self.speed = speed
        self.rum = rum
        self.graph = graph

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
        self.x = x
        self.y = y
        self.rotation = rotation
        self.speed = speed
        self.rum = rum

        self.cannonball += 1
        self.mine += 1

        self.action = None

    def fire(self, entity):
        if isinstance(entity, Ship) or entity.speed == 0:
            current_speed = entity.speed
            estimated_location = Position(entity.x, entity.y).get_neighbor(entity.rotation)
            for t in range(1, 10):
                for _ in range(current_speed):
                    estimated_location = estimated_location.get_neighbor(entity.rotation)

                fire_time = int(round(1 + (self.calculate_distance_between(estimated_location) / 3)))

                if fire_time <= t:
                    self.fire_x, self.fire_y = estimated_location.x, estimated_location.y
                    break
        else:
            self.fire_x, self.fire_y = entity.x, entity.y

        if self.graph.x_max < self.fire_x:
            self.fire_x = self.graph.x_max
        if self.graph.y_max < self.fire_y:
            self.fire_y = self.graph.y_max
        if 0 > self.fire_x:
            self.fire_x = 0
        if 0 > self.fire_y:
            self.fire_y = 0

        if Position(self.fire_x, self.fire_y).calculate_distance_between(self) > 10:
            return False

        self.cannonball = 0
        self.action = self._print_fire

        if self.speed > 0:
            rem_forward = True
        else:
            rem_forward = False

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

    def navigate(self, entity):
        if self.graph.in_grid(entity):
            entity = self.graph.find_closest(entity)

        path = self.graph.find_path(self, entity)
        if path == False:
            return False
        self.navigate_action = self.determine_move(path[-2:])
        self.action = self._print_navigate
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
        log(enemy_ships)
        if self.waypoint is None or self.calculate_distance_between(self.waypoints[self.waypoint]) <= 3:
            ordered_waypoints = self.ordered_waypoints(enemy_ships)[:3]
            log('ordered_waypoints: ' + str(ordered_waypoints))
            different = False
            while not different:
                new_waypoint = random.choice(ordered_waypoints)
                if new_waypoint != self.waypoint:
                    self.waypoint = new_waypoint
                    different = True

        if self.graph.in_grid(Position(self.waypoints[self.waypoint].x, self.waypoints[self.waypoint].y)):
            nav = Position(self.waypoints[self.waypoint].x, self.waypoints[self.waypoint].y)
        else:
            nav = self.graph.find_closest(Position(self.waypoints[self.waypoint].x, self.waypoints[self.waypoint].y))

        return self.navigate(nav)

    def determine_move(self, moves):
        log(str(moves))
        action = None

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

    def get_closest_entity(self, ship, entities):
        closest_entity = None
        closest_distance = 10000
        for entity in entities:
            distance = ship.calculate_distance_between(entity)
            if distance < closest_distance:
                closest_distance = distance
                closest_entity = entity
        return closest_entity, closest_distance

    def get_closest_enemy_ship(self, ship, enemy_ships):
        closest_enemy_ship = None
        closest_distance = 10000
        for id, enemy_ship in enemy_ships.items():
            distance = ship.calculate_distance_between(enemy_ship)
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy_ship = enemy_ship
        return closest_enemy_ship, closest_distance

    def run(self):
        while True:
            time_a = time.time()

            self.game.update_map(load=False)

            for id, ship in self.game.my_ships.items():
                closest_ship, distance_to_closest_ship = self.get_closest_enemy_ship(ship, self.game.enemy_ships)
                closest_barrel, distance_to_closest_barrel = self.get_closest_entity(ship, self.game.barrels)

                if len(self.game.barrels) > 0:
                    log('ship ({}) navigating to barrel'.format(id))
                    result = ship.navigate(closest_barrel)
                    if not result:
                        x = closest_ship.x - 4 if closest_ship.x > 10 else closest_ship.x + 4
                        y = closest_ship.y - 4 if closest_ship.y > 10 else closest_ship.y + 4
                        result = ship.navigate(Position(x, y))
                        if not result:
                            ship.no_action()
                else:
                    # Start a grid based movement pattern
                    log('ship ({}) grid based movement'.format(id))

                    x = closest_ship.x - 4 if closest_ship.x > 10 else closest_ship.x + 4
                    y = closest_ship.y - 4 if closest_ship.y > 10 else closest_ship.y + 4
                    result = ship.waypoint_move(self.game.enemy_ships)
                    if not result:
                        ship.no_action()

                if ship.navigate_action == 'WAIT' or ship.navigate_action is None:
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
                ship.print_action()

            time_b = time.time()
            dif = time_b - time_a
            log('Loop took {}ms'.format(round(dif*1000,2)))


if __name__ == "__main__":
    ai = AI()
    ai.run()