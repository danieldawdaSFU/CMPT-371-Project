import socket
from threading import Thread
from threading import Lock
import time
import random
import math

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM)

#Number of bytes for a message header. ex "PLYRMOVE"
MESSAGE_HEADER_LENGTH = 8

# 10x10 grid (each tile is 80 pixels)
GRID_WIDTH = GRID_HEIGHT = 10

MAX_SCORE = 36

SERVER_LOOP_SLEEP_TIME = 0.5

#server's IP/port. Change as needed, should be part of client UI to choose right port/IP.
sock.bind(("localhost", 53333))

mutex = Lock() #general mutex lock for player state changes (new inputs, changing connectionsList, etc)
#### Mutex locked variables
connectionList = []
clientThreads = []
gameStarted = False
currentScore = 0
prevLevel = -1
currentLevel = -1

#North, South, West, East movement vectors for each player.
#   2 = down, already processed at least once (release = stop)
#   1 = down (not processed, ie. if up received got to 0)
#   0 = just released between frames (process as true once),
#   -1 = up
playerInputs = [[-1, -1, -1, -1],
                [-1, -1, -1, -1],
                [-1, -1, -1, -1],
                [-1, -1, -1, -1]]

# playerPos: [[x, y]]
playerPos = [[4, 4],
             [5, 4],
             [4, 5],
             [5, 5]]

# goals: [[x, y, player number, time remaining (seconds)]]
goals = []

### end Mutex locked variables

# list of wall positions
WALLS_POS = [[0, 2],
         [1, 2],
         [1, 5],
         [1, 6],
         [1, 8],
         [2, 1],
         [2, 4],
         [2, 9],
         [3, 1],
         [3, 7],
         [4, 3],
         [4, 7],
         [5, 2],
         [5, 6],
         [5, 8],
         [6, 8],
         [7, 5],
         [7, 6],
         [8, 0],
         [8, 3],
         [8, 7],
         [9, 0],
         [9, 1],
         [9, 6]]

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
            # check if connection is still alive
            if connectionList[index] == None:
                #error, block thread.
                while 1:
                    pass

            #general receive logic
            data = connection.recv(MESSAGE_HEADER_LENGTH).decode()
            if data == "PLYRMOVE":
                #read <N/S/E/W><1/0>
                data = connection.recv(2).decode()
                with mutex:
                    if data[1] == "0":
                        #process key up request
                        if "N" in data:
                            if playerInputs[index][0] == 1:
                                playerInputs[index][0] = 0
                            elif playerInputs[index][0] == 2:
                                playerInputs[index][0] = -1
                        elif "S" in data:
                            if playerInputs[index][1] == 1:
                                playerInputs[index][1] = 0
                            elif playerInputs[index][1] == 2:
                                playerInputs[index][1] = -1
                        elif "W" in data:
                            if playerInputs[index][2] == 1:
                                playerInputs[index][2] = 0
                            elif playerInputs[index][2] == 2:
                                playerInputs[index][2] = -1
                        elif "E" in data:
                            if playerInputs[index][3] == 1:
                                playerInputs[index][3] = 0
                            elif playerInputs[index][3] == 2:
                                playerInputs[index][3] = -1

                    elif data[1] == "1":
                        #process key down request

                        for dirr in range(len(playerInputs[index])):
                            playerInputs[index][dirr] = -1
                        if "N" in data:
                            playerInputs[index][0] = 1
                        elif "S" in data:
                            playerInputs[index][1] = 1
                        elif "W" in data:
                            playerInputs[index][2] = 1
                        elif "E" in data:
                            playerInputs[index][3] = 1
            print(data)
        except:
            #close socket on error #todo
            #terminate connection
            with mutex:
                connection.close()
            #end this thread
            return


#function to send the current game state to all players
def broadcastGameUpdates():
    with mutex:
        # format data ("PLYRUPDTXXYYXXYYXXYYXXYY")
        playerUpdateData = ("PLYRUPDT"+str(playerPos[0][0]).zfill(2)+
                        str(playerPos[0][1]).zfill(2)+
                        str(playerPos[1][0]).zfill(2)+
                        str(playerPos[1][1]).zfill(2)+
                        str(playerPos[2][0]).zfill(2)+
                        str(playerPos[2][1]).zfill(2)+
                        str(playerPos[3][0]).zfill(2)+
                        str(playerPos[3][1]).zfill(2))
    broadcastToClients(playerUpdateData)

    with mutex:
        # format data ("GOALUPDTNGCSCLXXYYPNTLXXYYPNTL...")
        # where NG = number of goals, CS = current score (number of goals reached), CL = current level, XX = x pos of the ith goal, YY = y pos of the ith goal, PN = player number the goal belongs to, TL = time left on goal
        goalUpdateData = "GOALUPDT" + str(len(goals)).zfill(2) + str(currentScore).zfill(2) + str(currentLevel).zfill(2)
        for goal in goals:
            goalUpdateData += (str(goal[0]).zfill(2)+
                str(goal[1]).zfill(2)+
                str(goal[2]).zfill(2)+
                str(math.ceil(goal[3])).zfill(2))
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
            connection, _ = sock.accept()
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
            if playerInputs[player][0] > -1:
                newY = positions[player][1] - 1
                newY %= GRID_HEIGHT
                if checkForNoCollision(positions[player][0], newY):
                    positions[player][1] = newY
                    # check if the player moved onto a goal tile
                    checkForGoal(positions[player][0], positions[player][1], player)
                if playerInputs[player][0] == 0:
                    playerInputs[player][0] = -1
                elif playerInputs[player][0] == 1:
                    playerInputs[player][0] = 2
            #S
            elif playerInputs[player][1] > -1:
                newY = positions[player][1] + 1
                newY %= GRID_HEIGHT
                if checkForNoCollision(positions[player][0], newY):
                    positions[player][1] = newY
                    checkForGoal(positions[player][0], positions[player][1], player)
                if playerInputs[player][1] == 0:
                    playerInputs[player][1] = -1
                elif playerInputs[player][1] == 1:
                    playerInputs[player][1] = 2
            #W
            elif playerInputs[player][2] > -1:
                newX = positions[player][0] - 1
                newX %= GRID_HEIGHT
                if checkForNoCollision(newX, positions[player][1]):
                    positions[player][0] = newX
                    checkForGoal(positions[player][0], positions[player][1], player)
                if playerInputs[player][2] == 0:
                    playerInputs[player][2] = -1
                elif playerInputs[player][2] == 1:
                    playerInputs[player][2] = 2
            #E
            elif playerInputs[player][3] > -1:
                newX = positions[player][0] + 1
                newX %= GRID_HEIGHT
                if checkForNoCollision(newX, positions[player][1]):
                    positions[player][0] = newX
                    checkForGoal(positions[player][0], positions[player][1], player)
                if playerInputs[player][3] == 0:
                    playerInputs[player][3] = -1
                elif playerInputs[player][3] == 1:
                    playerInputs[player][3] = 2

# Checks all the list of entities given an x y coordinate to see if there is something there that player can't move into (ex. a player or wall)
def checkForNoCollision(x, y):
    if not [x, y] in playerPos:
        if not [x, y] in WALLS_POS:
            return True
    return False

# check if the player moved onto a goal tile
def checkForGoal(x, y, playerNumber):
    global currentScore, gameStarted

    toRemove = []
    # if the player did move onto a goal, add the goal tile to a list so it can be removed later
    for goal in goals:
        if goal[0] == x and goal[1] == y and goal[2] == playerNumber:
            toRemove.append(goal)

    # remove all the goal tiles that a player moved onto
    for goal in toRemove:
        goals.remove(goal)
        # increment the current score
        currentScore += 1
        print(f"Team Score: {currentScore}/{MAX_SCORE}")

    # if current score is equal to max score, then the players won the game
    if currentScore >= MAX_SCORE:
        print("Game Win")
        gameStarted = False
        broadcastToClients("GAMEWINN")

# Returns the number of goals per player and time limit on goal tiles, based on the current score
# Level 1: 2 goals per player, 20s time limit. Once all these goals are reached (currentScore = 8 points), next level
# Level 2: 3 goals per player, 15s time limit. Once all these goals are reached (currentScore = 20 points), next level
# Level 3: 4 goals per player, 10s time limit. Once all these goals are reached (currentScore = 36 points), game win
def getDifficulty():
    global currentScore

    if currentScore >= 20:
        # return the level, goals per player, and time limit
        return 3, 4, 20
    elif currentScore >= 8:
        return 2, 3, 30
    else:
        return 1, 2, 40

# Generates new goals with a specific number per player and time limit based on current score
def generateGoals():
    _, goalsPerPlayer, timeLimit = getDifficulty()

    takenTiles = [wall for wall in WALLS_POS]
    takenTiles.extend(goals)
    takenTiles.extend(playerPos)

    for _ in range(goalsPerPlayer):
        for playerNum in range(len(connectionList)):
            # Arbitrarily limit the amount of goals that can be on the board to prevent infinite loop here
            if len(takenTiles) < GRID_WIDTH * GRID_HEIGHT - (GRID_WIDTH + GRID_HEIGHT):
                while True:
                    x = random.randint(0, GRID_WIDTH - 1)
                    y = random.randint(0, GRID_HEIGHT - 1)
                    if [x, y] not in takenTiles:
                        takenTiles.append([x, y])
                        goals.append([x, y, playerNum, timeLimit])
                        break

# Decreases the timers on all existing goals, and creates new goals if there currently aren't enough on the board
def updateGoalStates():
    global gameStarted, currentScore, prevLevel, currentLevel

    with mutex:
        # Determine current level/round
        currentLevel, _, _ = getDifficulty()

        # only generate goals when the level changes
        if currentLevel != prevLevel:
            goals.clear()
            generateGoals()
            prevLevel = currentLevel
        gameEnd = False
        for goal in goals:
            goal[3] -= SERVER_LOOP_SLEEP_TIME
            if goal[3] <= 0:
                gameEnd = True
    if gameEnd:
        print("Game Over")
        gameStarted = False
        broadcastToClients("GAMEOVER")

def updateGameState():
    updatePositions(playerInputs, playerPos)
    updateGoalStates()

def main():
    #loop so we can start new games afterwards
    global gameStarted, currentScore, prevLevel, goals, playerPos
    while True:
        # reset values for new game
        with mutex:
            prevLevel = -1
            currentScore = 0
            goals.clear()
            playerPos = [[4, 4],
                        [5, 4],
                        [4, 5],
                        [5, 5]]

        #start game
        getInitPlayers()


        #run game logic
        while gameStarted:
            #send new game state
            updateGameState()
            broadcastGameUpdates()
            time.sleep(SERVER_LOOP_SLEEP_TIME)

        #game end
        with mutex:
            gameStarted = False

        #make sure all threads close and sockets close
        for thread in range(len(clientThreads)):
            removeConnection(thread)

main()