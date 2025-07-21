
def updatePositions(dirs, pos):

    #velocity
    vel = 10
    for i in range(len(dirs)):

        # moving up
        if dirs[i][0] == True:
            pos[i][1] = clamp_num(pos[i][1] - vel)

        # moving left
        if dirs[i][1] == True:
            pos[i][0] = clamp_num(pos[i][0] - vel)

         # moving down
        if dirs[i][2] == True:
            pos[i][1] = clamp_num(pos[i][1] + vel)

         # moving right
        if dirs[i][3] == True:
            pos[i][0] = clamp_num(pos[i][0] + vel)

    return pos

# keeps number in range and rounds to max/min if over/under
def clamp_num(num):
    return max(min(num, 800), 0)
