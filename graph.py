from main import Game, Graph, Ship, Position

game = Game()
game.update_map(load='3')

game.print_map()

graph = Graph(game.map)
#graph.remove_node(11, 7)

#path = graph.find_path(Ship(1,13,7,4,1,100,graph), Position(12,7))

print()


