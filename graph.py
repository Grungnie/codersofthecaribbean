from main import Game, Graph, Ship, Position

game = Game()
game.update_map(load='3')

game.graph.calculate_collisions({
    0: 'WAIT',
    1: 'WAIT',
    2: 'STARBOARD',
    3: 'WAIT',
    4: 'WAIT',
    5: 'WAIT'
})

#game.print_map(waypoints=True)

#graph = Graph(game.map)
#game.update_map(load='3')
ship = game.my_ships[0]
ship.planned_next_target = Position(12, 8, 5, 0)
game.graph.find_path(ship, Position(16,9), [Position(17,11)])
#graph.remove_node(11, 7)

#path = graph.find_path(Ship(1,13,7,4,1,100,graph), Position(12,7))

print()


