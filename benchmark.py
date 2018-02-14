from main import Game, Graph, Ship, Position, AI, Timer, log

import time, math

times = []

for _ in range(1):
    ai = AI()
    for data in range(1, 108):
        log('turn: {}'.format(data))
        now = time.time()
        ai.turn('{}'.format(data), file='steps.json')
        ai.game.print_map()
        taken = time.time() - now
        times.append(round(taken * 100, 2))

time.sleep(0.5)

times.sort()
log('\n-- DETAILS --')
log('average: {}'.format(sum(times)/len(times)))
log('min: {}'.format(min(times)))
log('max: {}'.format(max(times)))
log('median: {}'.format(times[int(len(times)/2)]))