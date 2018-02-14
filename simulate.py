import json
import time
from main import Game, log, Graph, Position, ME, ENEMY
import itertools


class NewGraph(Graph):
    def __init__(self, map, game):
        self.move_sets = None
        self.ships = {}

        super(NewGraph, self).__init__(map, game)

    def check_valid(self, moves):
        for id, move in moves.items():
            if self.ships[id].speed == 2 and move == 'FASTER':
                return False
            if self.ships[id].speed == 0 and move == 'SLOWER':
                return False
        return True

    def compile_ships(self):
        self.ships = {}
        for ship_set in [game.my_ships.values(), game.enemy_ships.values()]:
            for ship in ship_set:
                self.ships[ship.id] = ship

    def compile_move_sets(self):
        self.move_sets = {}
        for ship in self.ships.values():
            self.move_sets[ship.id] = self.compile_moves(ship)

    def compile_moves(self, ship):
        if ship.speed == 0:
            moves = ['WAIT', 'FASTER', 'PORT', 'STARBOARD']
        elif ship.speed == 2:
            moves = ['WAIT', 'SLOWER', 'PORT', 'STARBOARD']
        else:
            moves = ['WAIT', 'FASTER', 'SLOWER', 'PORT', 'STARBOARD']

        # Stay still
        # Forward 1
        # Forward 2
        # rotate port
        # rotate startboard

        move_set = {
            'id': ship.id,
            'forward_0': {},
            'forward_1': {},
            'forward_2': {},
            'port': {},
            'starboard': {}
        }

        # Stay still
        move_set['forward_0']['stern'] = ship.get_neighbour(self.map.abs_rotation(ship.rotation-3))
        move_set['forward_0']['mid'] = Position(ship.x, ship.y)
        move_set['forward_0']['bow'] = ship.get_neighbour(ship.rotation)

        # Forward 1
        move_set['forward_1']['stern'] = Position(ship.x, ship.y)
        move_set['forward_1']['mid'] = ship.get_neighbour(ship.rotation)
        move_set['forward_1']['bow'] = move_set['forward_1']['mid'].get_neighbour(ship.rotation)

        # Forward 2
        move_set['forward_2']['stern'] = Position(move_set['forward_1']['mid'].x, move_set['forward_1']['mid'].y)
        move_set['forward_2']['mid'] = Position(move_set['forward_1']['bow'].x, move_set['forward_1']['bow'].y)
        move_set['forward_2']['bow'] = move_set['forward_2']['mid'].get_neighbour(ship.rotation)

        if ship.speed == 0:
            rotation_point = move_set['forward_0']['mid']
        elif ship.speed == 1:
            rotation_point = move_set['forward_1']['mid']
        else:
            rotation_point = move_set['forward_2']['mid']

        # Port
        move_set['port']['stern'] = rotation_point.get_neighbour(self.map.abs_rotation(ship.rotation+1))
        move_set['port']['mid'] = Position(rotation_point.x, rotation_point.y, rotation=self.map.abs_rotation(ship.rotation-1))
        move_set['port']['bow'] = rotation_point.get_neighbour(self.map.abs_rotation(ship.rotation-1))

        # Starboard
        move_set['starboard']['stern'] = rotation_point.get_neighbour(self.map.abs_rotation(ship.rotation-1))
        move_set['starboard']['mid'] = Position(rotation_point.x, rotation_point.y, rotation=self.map.abs_rotation(ship.rotation+1))
        move_set['starboard']['bow'] = rotation_point.get_neighbour(self.map.abs_rotation(ship.rotation+1))

        move_set['bow_aoe'] = [
            (move_set['forward_0']['bow'].x * 100) + move_set['forward_0']['bow'].y,
            (move_set['forward_1']['bow'].x * 100) + move_set['forward_1']['bow'].y,
            (move_set['port']['stern'].x * 100) + move_set['port']['stern'].y,
            (move_set['port']['bow'].x * 100) + move_set['port']['bow'].y,
            (move_set['starboard']['stern'].x * 100) + move_set['starboard']['stern'].y,
            (move_set['starboard']['bow'].x * 100) + move_set['starboard']['bow'].y
        ]

        if ship.speed != 0:
            move_set['bow_aoe'].append((move_set['forward_2']['bow'].x * 100) + move_set['forward_2']['bow'].y)

        move_set['aoe'] = [
            (move_set['forward_0']['stern'].x * 100) + move_set['forward_0']['stern'].y,
            (move_set['forward_0']['mid'].x * 100) + move_set['forward_0']['mid'].y,
        ] + move_set['bow_aoe']

        return move_set

    def sim_collisions(self, moves):
        current_position = {}
        collision_moves = []

        if not self.check_valid(moves):
            return False,  False

        # Apply speed changes to ships
        for id, move in moves.items():
            if move == 'SLOWER':
                self.ships[id].speed -= 1
            elif move == 'FASTER':
                self.ships[id].speed += 1

        # Apply speed 1 moves
        for id, move in moves.items():
            if self.ships[id].speed > 0:
                current_position[id] = self.move_sets[id]['forward_1']
            else:
                current_position[id] = self.move_sets[id]['forward_0']

        # Check if out of bounds
        for id, move in moves.items():
            if self.ships[id].speed == 0:
                if self.map.out_of_range(current_position[id]['mid']):
                    collision_move = '{} {} out'.format(id, move)
                    if collision_move not in collision_moves:
                        collision_moves.append(collision_move)
                    self.ships[id].speed = 0
                    moves[id] = 'WAIT'
                    current_position[id] = self.move_sets[id]['forward_0']

        # Check for collisions
        collision = True
        while collision:
            collision = False
            for ship_ids in itertools.product(moves, repeat=2):
                if self.ships[ship_ids[0]].speed == 0 or ship_ids[0] == ship_ids[1]:
                    continue

                for part in ['bow', 'mid', 'stern']:
                    if current_position[ship_ids[0]]['bow'].x == current_position[ship_ids[1]][part].x and \
                            current_position[ship_ids[0]]['bow'].y == current_position[ship_ids[1]][part].y:
                        #log('id: {} ran into id: {}\'s {} during s1'.format(ship_ids[0], ship_ids[1], part))
                        #log(str(moves))

                        collision_move = '{} {} {} {} {}'.format(ship_ids[0], ship_ids[1], moves[ship_ids[0]], moves[ship_ids[1]], part)
                        if collision_move not in collision_moves:
                            collision_moves.append(collision_move)

                        self.ships[ship_ids[0]].speed = 0
                        moves[ship_ids[0]] = 'WAIT'
                        current_position[ship_ids[0]] = self.move_sets[ship_ids[0]]['forward_0']
                        collision = True

        # Apply speed 2 moves
        for id, move in moves.items():
            if self.ships[id].speed > 1:
                current_position[id] = self.move_sets[id]['forward_2']

        # Check if out of bounds
        for id, move in moves.items():
            if self.ships[id].speed == 0:
                if self.map.out_of_range(current_position[id]['mid']):
                    collision_move = '{} {} out'.format(id, move)
                    if collision_move not in collision_moves:
                        collision_moves.append(collision_move)
                    self.ships[id].speed = 0
                    moves[id] = 'WAIT'
                    current_position[id] = self.move_sets[id]['forward_1']

        # Check for collisions
        collision = True
        while collision:
            collision = False
            for ship_ids in itertools.product(moves, repeat=2):
                if self.ships[ship_ids[0]].speed < 2 or ship_ids[0] == ship_ids[1]:
                    continue

                for part in ['bow', 'mid', 'stern']:
                    if current_position[ship_ids[0]]['bow'].x == current_position[ship_ids[1]][part].x and \
                                    current_position[ship_ids[0]]['bow'].y == current_position[ship_ids[1]][part].y:
                        # log('id: {} ran into id: {}\'s {} during s1'.format(ship_ids[0], ship_ids[1], part))
                        # log(str(moves))

                        collision_move = '{} {} {} {} {}'.format(ship_ids[0], ship_ids[1], moves[ship_ids[0]],
                                                                 moves[ship_ids[1]], part)
                        if collision_move not in collision_moves:
                            collision_moves.append(collision_move)

                        self.ships[ship_ids[0]].speed = 0
                        moves[ship_ids[0]] = 'WAIT'
                        current_position[ship_ids[0]] = self.move_sets[ship_ids[0]]['forward_1']
                        collision = True

        # Apply rotations
        for id, move in moves.items():
            if move == 'STARBOARD':
                current_position[id] = self.move_sets[id]['starboard']
            elif move == 'PORT':
                current_position[id] = self.move_sets[id]['port']

        # Check for collisions
        collision = True
        while collision:
            collision = False
            for ship_ids in itertools.product(moves, repeat=2):
                if moves[ship_ids[0]] not in ['STARBOARD', 'PORT'] or ship_ids[0] == ship_ids[1]:
                    continue

                for part in ['bow', 'mid', 'stern']:
                    if (current_position[ship_ids[0]]['bow'].x == current_position[ship_ids[1]][part].x and
                                    current_position[ship_ids[0]]['bow'].y == current_position[ship_ids[1]][part].y) or \
                                    (current_position[ship_ids[0]]['stern'].x == current_position[ship_ids[1]][part].x and
                                    current_position[ship_ids[0]]['stern'].y == current_position[ship_ids[1]][part].y):
                        #log('id: {} ran into id: {}\'s {} during {} turn'.format(ship_ids[0], ship_ids[1], part, moves[ship_ids[0]]))
                        # log(str(moves))

                        collision_move = '{} {} {} {} {}'.format(ship_ids[0], ship_ids[1], moves[ship_ids[0]],
                                                                 moves[ship_ids[1]], part)
                        if collision_move not in collision_moves:
                            collision_moves.append(collision_move)

                        current_position[ship_ids[0]] = self.move_sets[ship_ids[0]]['forward_{}'.format(self.ships[ship_ids[0]].speed)]
                        self.ships[ship_ids[0]].speed = 0
                        collision = True

        result = {}
        for id, move in moves.items():
            position = current_position[id]['mid']
            position.speed = self.ships[id].speed
            result[id] = position

        return collision_moves, result

    def sim_all_moves(self):
        commands = ['WAIT', 'FASTER', 'SLOWER', 'PORT', 'STARBOARD']
        groups = self.calculate_aoe_groups()

        count = 0
        collision_moves = []
        for group in groups:
            for combo in itertools.product(range(5), repeat=len(group)):
                moves = {}
                for index, id in enumerate(group):
                    moves[id] = commands[combo[index]]

                collision_result, ship_result = game.graph.sim_collisions(moves)

                if collision_result:
                    for collision_move in collision_result:
                        if collision_move not in collision_moves:
                            collision_moves.append(collision_move)

                            # log(result)

        for collision_move in collision_moves:
            log(collision_move)

    def calculate_aoe_groups(self):
        sets = {}
        for ship in self.ships.values():
            sets[ship.id] = [ship.id]

        for move_set_1 in self.move_sets.values():
            for move_set_2 in self.move_sets.values():
                if move_set_1['id'] != move_set_2['id']:
                    if [i for i in move_set_1['bow_aoe'] if i in move_set_2['aoe']]:
                        log('test {} vs {}'.format(move_set_1['id'], move_set_2['id']))
                        sets[move_set_1['id']].append(move_set_2['id'])

        log(sets)
        groups = []
        # Flatten
        for i, i_hits in sets.items():
            if not self.in_group(i, groups=groups):
                groups.append(i_hits)
            else:
                continue

            for j, j_hits in sets.items():
                if not self.in_group(j, groups=groups):
                    if i in j_hits:
                        for x in j_hits:
                            if x not in groups[-1]:
                                groups[-1].append(x)

        log(groups)
        return groups

    def in_group(self, i, groups):
        for group in groups:
            if i in group:
                return True
        return False


# TODO: Need to add mines and cannonballs
# TODO: Add future iterations
# TODO: Add a cost function to each step (monti carlo)

starting_state = json.load(open('steps.json'))["30"]

times = []

game = Game()
game.graph = NewGraph(game.map, game)

for i in range(1, 108):
    log(i)

    game.update_map(load=str(i), file='steps.json')

    game.graph.compile_ships()
    game.graph.compile_move_sets()

    game.print_map()

    now = time.time()
    game.graph.sim_all_moves()
    taken = time.time() - now
    times.append(round(taken * 100, 3))

time.sleep(0.5)

times.sort()
log('\n-- DETAILS --')
log('average: {:.3f}'.format(round(sum(times)*100 / len(times), 3)/100))
log('min: {}'.format(min(times)))
log('max: {}'.format(max(times)))
log('median: {}'.format(times[int(len(times) / 2)]))