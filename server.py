import socket
from threading import Thread
from threading import Lock
import time
import random

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

#Number of bytes for a message header. ex "PLYRMOVE"
MESSAGE_HEADER_LENGTH = 8

# 10x10 grid (each tile is 80 pixels)
GRID_WIDTH = GRID_HEIGHT = 10

currentScore = 0
# may change this
maxScore = 20

#server's IP/port. Change as needed, should be part of client UI to choose right port/IP.
sock.bind(("localhost", 53333))

mutex = Lock() #general mutex lock for player state changes (new inputs, changing connectionsList, etc)
#### Mutex locked variables
connectionList = []
clientThreads = []
gameStarted = False

#North, West, South, East movement vectors for each player
playerInputs = [[False, False, False, False],
                [False, False, False, False],
                [False, False, False, False],
                [False, False, False, False]]

# initial game state dict
# pos: [[x, y]]
# goals: [[x, y, player number, time remaining (seconds)]]
# players start at the center of the grid
gameState = {'pos': [[4, 4],
                     [5, 4],
                     [4, 5],
                     [5, 5]],
             'walls': [[0, 0],
                       [0, 9],
                       [9, 0],
                       [9, 9]],
             'goals': []}

# Since the game updates every 0.5 sec, and the timers need to update every 1 sec, this variable flips every update
updateGoalTimers = False

### end Mutex locked variables

#remove a client/thread (dont call from a thread when possible)
def removeConnection(index):
    #do not get mutex before calling
    try:
        if clientThreads[index] != None:
            with mutex:
                clientThreads[index] = None
                connectionList[index] = None
    except:
        print("Failed to join thread when removing connection.")

#handle all inputs from players, outputs will be handled in bulk via the broadcastGame() function
def handleConnection(connection, index):
    global gameStarted
    while True:
        with mutex:
            if gameStarted == False:
                #terminate connection
                connection.close()
                #end this thread
                return
        try:
            #general receive logic
            if connectionList[index] == None:
                #error, block thread.

                gameState['goals'].remove
                while 1:
                    pass

            data = connection.recv(MESSAGE_HEADER_LENGTH).decode()
            if data == "PLYRMOVE":
                #read <N/S/E/W><1/0>
                data = connection.recv(2).decode()
                with mutex:
                    # if recv PLYRMOVE data then move based on dir
                    for dirr in range(len(playerInputs[index])):
                        playerInputs[index][dirr] = False
                    if "N" in data:
                        playerInputs[index][0] = (data[1] == "1")
                    elif "S" in data:
                        playerInputs[index][1] = (data[1] == "1")
                    elif "W" in data:
                        playerInputs[index][2] = (data[1] == "1")
                    elif "E" in data:
                        playerInputs[index][3] = (data[1] == "1")
        except:
            #close socket on error #todo
            pass


#function to send the current game state to all players
def broadcastGameUpdates():
    with mutex:
        # format data ("PLYRUPDTXXYYXXYYXXYYXXYY")
        playerUpdateData = ("PLYRUPDT"+str(gameState["pos"][0][0]).zfill(2)+
                        str(gameState["pos"][0][1]).zfill(2)+
                        str(gameState["pos"][1][0]).zfill(2)+
                        str(gameState["pos"][1][1]).zfill(2)+
                        str(gameState["pos"][2][0]).zfill(2)+
                        str(gameState["pos"][2][1]).zfill(2)+
                        str(gameState["pos"][3][0]).zfill(2)+
                        str(gameState["pos"][3][1]).zfill(2))
        broadcastToClients(playerUpdateData)

        # format data ("GOALUPDTNGXXYYPNTLXXYYPNTL...")
        # where NG = number of goals, XX = x pos of the ith goal, YY = y pos of the ith goal, PN = player number the goal belongs to, TL = time left on goal
        goalUpdateData = "GOALUPDT" + str(len(gameState['goals'])).zfill(2)
        for goal in gameState['goals']:
            goalUpdateData += (str(goal[0]).zfill(2)+
                str(goal[1]).zfill(2)+
                str(goal[2]).zfill(2)+
                str(goal[3]).zfill(2))
        broadcastToClients(goalUpdateData)

def broadcastToClients(data):
    for conn in range(len(connectionList)):
        try:
            if connectionList[conn] != None:
                connectionList[conn].send(data.encode())
        except Exception as e:
            print(f"An unexpected error occurred during broadcast: {e}")
            #they left, close socket and join thread
            removeConnection(conn)

#Fill the connectionsList, and create threads for them
def getInitPlayers():
    #Start with no connections. Clients can reconnect on their own after a game
    connectionsList = []
    while True:
        # while true since we cannot check the len of connectionsList without mutex
        if len(connectionsList) == 4:
            # send everyone their player number. If it fails then they left, and we try again
            index = 1
            toRemove = []
            for connection in connectionsList:
                try:
                    #send player number
                    connection.send(("PLYRJOIN" + str(index)).encode())

                    #player should echo their player number
                    data = connection.recv(MESSAGE_HEADER_LENGTH + 1)
                    if data == b'':
                        toRemove.append(connection)
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")
                    #sending failed, so remove that client.
                    toRemove.append(connection)

                index += 1
            for conn in toRemove:
                connectionsList.remove(conn)

            if len(connectionsList) == 4:
                # everyone is still ready
                break
        else:

            # get new client
            # buffer as many as we need
            sock.listen(4-len(connectionsList))
            connection, address = sock.accept()
            print("New Connection")

            #update list
            connectionsList.append(connection)

    #send startGame message (since all players have received their number)
    #   If players leave from this point, then we will just play with less players
    #update global list, and start threads
    global gameStarted
    global connectionList
    global clientThreads
    dropList = []
    with mutex:
        connectionList = connectionsList
        for conn in range(len(connectionList)):
            #send all clients the "GO" message. They should already have their player number
            try:
                connectionList[conn].send("GAMESTRT".encode())
            except:
                dropList.append(conn)
                #failed to send to client, we will just ignore them then. Remove socket/thread
                print("Failed to send game start to some players. removing them")

            t = Thread(target = handleConnection, args=(connectionList[conn], conn))
            t.start()
            clientThreads.append(t)
        gameStarted = True
    for i in dropList:
        removeConnection(i)

    return

def updatePositions(playerInputs, positions):
    with mutex:
        for player in range(len(positions)):
            #N
            if playerInputs[player][0]:
                newY = positions[player][1] - 1
                newY %= GRID_HEIGHT
                if checkForNoCollision(positions[player][0], newY):
                    positions[player][1] = newY
                    # check if the player moved onto a goal tile
                    checkForGoal(positions[player][0], positions[player][1], player)

            #S
            elif playerInputs[player][1]:
                newY = positions[player][1] + 1
                newY %= GRID_HEIGHT
                if checkForNoCollision(positions[player][0], newY):
                    positions[player][1] = newY
                    checkForGoal(positions[player][0], positions[player][1], player)

            #W
            elif playerInputs[player][2]:
                newX = positions[player][0] - 1
                newX %= GRID_HEIGHT
                if checkForNoCollision(newX, positions[player][1]):
                    positions[player][0] = newX
                    checkForGoal(positions[player][0], positions[player][1], player)

            #E
            elif playerInputs[player][3]:
                newX = positions[player][0] + 1
                newX %= GRID_HEIGHT
                if checkForNoCollision(newX, positions[player][1]):
                    positions[player][0] = newX
                    checkForGoal(positions[player][0], positions[player][1], player)

# Checks all the list of entities given an x y coordinate to see if there is something there that player can't move into (ex. a player or wall)
def checkForNoCollision(x, y):
    if not [x, y] in gameState['pos']:
        if not [x, y] in gameState['walls']:
            return True
    return False

# check if the player moved onto a goal tile
def checkForGoal(x, y, playerNumber):
    global currentScore, gameStarted

    toRemove = []
    # if the player did move onto a goal, add the goal tile to a list so it can be removed later
    for goal in gameState['goals']:
        if goal[0] == x and goal[1] == y and goal[2] == playerNumber:
            toRemove.append(goal)

    # remove all the goal tiles that a player moved onto
    for goal in toRemove:
        # increment the current score
        currentScore += 1
        gameState['goals'].remove(goal)
        print(f"Score: {currentScore}/{maxScore}")

        # if current score is equal to max score, then the players won the game
        if currentScore >= maxScore:
            print("Game Win")
            gameStarted = False
            broadcastToClients("GAMEWINN")

# Creates the given number of goals for each player which start with the given time limit
def generateGoals(goalsPerPlayer, timeLimit):
    takenTiles = [wall for wall in gameState['walls']]
    takenTiles.extend(gameState['goals'])

    for _ in range(goalsPerPlayer):
        for playerNum in range(len(connectionList)):
            # Arbitrarily limit the amount of goals that can be on the board to prevent infinite loop here
            if len(takenTiles) < GRID_WIDTH * GRID_HEIGHT - (GRID_WIDTH + GRID_HEIGHT):
                while True:
                    x = random.randint(0, GRID_WIDTH - 1)
                    y = random.randint(0, GRID_HEIGHT - 1)
                    if [x, y] not in takenTiles:
                        takenTiles.append([x, y])
                        gameState['goals'].append([x, y, playerNum, timeLimit])
                        break

# Decreases the timers on all existing goals, and creates new goals if there currently aren't enough on the board
# TODO: could have varying degrees of difficulty which changes the time limit of goals and how much are generated
def updateGoalStates():
    global updateGoalTimers, gameStarted

    with mutex:
        if (len(gameState['goals']) <= len(connectionList)):
            generateGoals(1, 20)

        if (updateGoalTimers):
            for goal in gameState['goals']:
                goal[3] -= 1
                if goal[3] == 0:
                    print("Game Over")
                    gameStarted = False
                    broadcastToClients("GAMEOVER")
            updateGoalTimers = False
        else:
            updateGoalTimers = True

def updateGameState():
    updatePositions(playerInputs, gameState['pos'])
    updateGoalStates()

def main():
    #loop so we can start new games afterwards
    global gameStarted
    while True:
        #start game
        getInitPlayers()


        #run game logic
        while gameStarted:
            #send new game state
            updateGameState()
            broadcastGameUpdates()
            time.sleep(0.5)

        #game end
        with mutex:
            gameStarted = False

        #make sure all threads close and sockets close
        for thread in range(len(clientThreads)):
            removeConnection(thread)

main()