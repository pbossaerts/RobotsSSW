# -*- coding: utf-8 -*-
"""
Created on Fri March  26 2021
Amended from Probot_E1.py on Wed 3/5/2023 to record number of orders per bot type (maker vs RE (taker))
and saving data

@author: Peter Bossaerts (based on new_robot_E1.py of author Tingxuan Huang)

GOAL:
- Read robot logs (after import into xls spreadsheets) for an experimental session
- Compute robot use (quantity, duration, type, ...)
- Time synchronization with trading data
    - Need to first execute part of Pbaspread.py that computes being_end_sessions (beginning and ending time of sessions)
      (This will save being_end_sessions in array format to npy file 'B_E_sessions.py' which this program reads)



"""
 
import numpy as np
import csv
from xlrd import open_workbook
from matplotlib import pyplot as plt
import pandas as pd


### Read data from Nplayer robot logbooks, combined into one list ###
# By setting Nplayer = 1, you can try out things; only robot for first player is read
# Note: except for Session 4 (Oct 6), there are 8 players; For Session 4, there are 9 players
Nplayer = 8

robotlogbooks = []
for i in range(1, Nplayer+1):
    name = 'r' + str(i) + ' robot.xls'
    wb = open_workbook(name)
    print("1")
    for s in wb.sheets():
        #print 'Sheet:',s.name
        print(s)
        values = []
        for row in range(s.nrows):
            col_value = []
            for col in range(s.ncols):
                value  = (s.cell(row,col).value)
                try : value = str(int(value))
                except : pass
                col_value.append(value)
            values.append(col_value)
        robotlogbooks.append(values)
# print(values)

for i in range(Nplayer):
    print(len(robotlogbooks[i]))
    
### clean the data, elinimate all the useless rows (with N/A or empty) ###

robotlogbooks[0][0]

cleanbooks = []

for i in range(Nplayer):
    temp = []
    for j in range(len(robotlogbooks[i])):
        if not (robotlogbooks[i][j][0] == '' or robotlogbooks[i][j][0] == '==========='): # This is different from experiment 1
            temp.append(robotlogbooks[i][j])
    cleanbooks.append(temp)    
         
book1 = cleanbooks

# calculate adjustment for timezone difference of algohost (Aussie time) and flex-e-markets (UTC)
# in seconds

import datetime
import time

timeadjustment = '10:00:00'
x = time.strptime(timeadjustment, '%H:%M:%S')
difsec = datetime.timedelta(hours=x.tm_hour, minutes=x.tm_min,seconds=x.tm_sec).total_seconds()

difsec     # adjust for the ten hours difference, in seconds (Careful, 10 hours if experiment ran during Winter)

# create adjusted time stamp in seconds 

# cleanbooks[0][5][2]     # inspect raw time data, ready to be converted to seconds

### define a function that takes time from robot logbooks and return time in
### seconds adjusting for the difference with market logbooks (10 hours)

def adjustedtimeinsecond(t):
    x = time.strptime(t, '%H:%M:%S')
    originalsec = datetime.timedelta(hours=x.tm_hour, minutes=x.tm_min,seconds=x.tm_sec).total_seconds()
    correctedtime = originalsec - difsec
    return correctedtime

adjustedtimeinsecond(cleanbooks[0][0][2])      # test this function, it works

### replace time with adjusted time in seconds

for i in range(len(book1)):
    for j in range(len(book1[i])):
        #print(i,j)
        book1[i][j][2] = adjustedtimeinsecond(cleanbooks[i][j][2])

book1     # now this book has raw time data converted into seconds

## Find some of the records that we don't need, and could only confuse (i.e., introduce errors)
## Eliminate those records

# book1[0][0][7]

# First find all the POSSIBLE statements (distinguished byy 6 first characters only)
unique_entries = []

for i in range(len(book1)):
    for j in range(len(book1[i])):
        if not (book1[i][j][7][0:5] in unique_entries):
            unique_entries.append(book1[i][j][7][0:5])
            print(book1[i][j][7])
                
unique_entries    

# Two of those entries: to be identified and eliminated
# E2 does not always appear

E1 = "The session status has changed. Is it open?False"
E2 = "I cannot send orders to an inactive session."

# now eliminate the above two entries from the book
# Active_book is the input file for the analysis

active_book = []

count = 0     # see how many will be eliminate

for i in range(len(book1)):
    temp = []
    for j in range(len(book1[i])):
        if not (book1[i][j][7] == E1 or book1[i][j][7] == E2):
            temp.append(book1[i][j])
        else:
            count += 1
    active_book.append(temp)

# count

# active_book

# Now coordinate time between logs and trading data
# use begin/end times of sessions as computed in Pbaspread_E1.py
# (Need to run Pbaspread_E1 first!!)
# Then convert time to seconds

Abegin_end_sessions = np.load('B_E_sessions.npy')
intervaltime = Abegin_end_sessions.tolist()
# find the time length of each period from "intervaltime"
# First convert from hrmnse to seconds

import copy

intervaltime_s = copy.deepcopy(intervaltime)  # intervaltime in seconds (*_s) will be created, DIFFERENT so need deepcopy

for i in range(15):
    for j in range(2):
        time_t = intervaltime[i][j]
        convert_time = (60 * 60) * int(time_t / 10000) + 60 * int((time_t % 10000) / 100) + int(time_t % 100)
        intervaltime_s[i][j] = convert_time

intervaltime_s

# Compute period durations

period_length = []

for i in range(15):
    start_time = intervaltime_s[i][0]
    end_time = intervaltime_s[i][1]
    dif = end_time - start_time
    period_length.append(dif/60)

period_length

# Compute total trading time (excluding pauses!)
# Will be used to compute % time robots are used
total_minutes = sum(period_length)  # Should be ~50 minutes


################### BEGIN ANALYSIS ##############################

################# Robot features extracting #######################
# Gather features of the bots, such as type, time started, time stopped (or if absent, when subsequent bot started),
# reference value (fv), etc.
# Note: bots can remain deployed across periods!

robot_info = []

for i in range(len(active_book)):    
    temp = []
    start_switch = 0
    end_switch = 0
    start_time = 0
    end_time = 0
    robot_submit = 0
    robot_type = []
    robot_side = []
    robot_fv = np.nan
    for j in range(len(active_book[i])):
        # check for signal of end, record info
        if active_book[i][j][7][0:3] == 'DES' and j > 2:
            end_switch = 1
            end_time = active_book[i][j-3][2]
            robot_type = active_book[i][j][7].split(":")[3]
            robot_side = active_book[i][j][7].split(":")[2]
            robot_fv = int(active_book[i][j][7].split(":")[4][3:])
        # consider the last ending, record info
        if j == (len(active_book[i]) - 1):
            end_switch = 1
            end_time = active_book[i][j][2]      
            robot_type = active_book[index[0]][index[1]][7].split(":")[3]  # Extract from DES record: MARKET/REACTIVE
            robot_side = active_book[index[0]][index[1]][7].split(":")[2]  # Extract from DES record: BUY/SELL
            robot_fv = int(active_book[index[0]][index[1]][7].split(":")[4][3:])  # Extract from DES record: Reference Value
        # record
        if start_switch == 1:
            if active_book[i][j][7][0:8] == 'An order':
                robot_submit += 1
        if start_switch == 1 and end_switch == 1:
            dif = end_time - start_time
            temp.append([start_time, end_time, dif, robot_side, robot_type, robot_fv, robot_submit, i])
            # switch off switches and empty containers 
            start_switch = 0
            end_switch = 0
            robot_submit = 0
            robot_type = []
            robot_side = []
            robot_fv = np.nan
        # check for signal of start
        if active_book[i][j][7][0:3] == 'DES':
            start_switch = 1
            start_time = active_book[i][j-2][2] 
            index = [i, j]
    robot_info.append(temp)

# Output:
# robot_info
# This is a list is 3D: [1] player, [2] robot, [3] start time, stop time, duration, type, side,
# reference value, number of orders (added 3/5/2023)

# Save output
df_empty = pd.DataFrame(
    {
            "participant": [],
            "start_time": [],
            "end_time": [],
            "duration": [],
            "robot_side": [],
            "robot_type": [],
            "robot_fv": [],
            "robot_submit": []
    }
)
df = df_empty
for n in range(8):
    t_robot_info0 = list(zip(*robot_info[n]))
    tt_robot_info0 = [list(sublist) for sublist in t_robot_info0]
    if not tt_robot_info0:
        df0 = df_empty
    else:
        df0 = pd.DataFrame(
            {
                "participant": tt_robot_info0[7],
                "start_time": tt_robot_info0[0],
                "end_time": tt_robot_info0[1],
                "duration": tt_robot_info0[2],
                "robot_side": tt_robot_info0[3],
                "robot_type": tt_robot_info0[4],
                "robot_fv": tt_robot_info0[5],
                "robot_submit": tt_robot_info0[6]
            }
        )
    df = pd.concat([df,df0])
df.to_csv('save_robot_use.csv')

######################### Usage Analysis ##########################
## Now analyze usage of bots PER PERIOD (makes sure that bots that are active across 2 periods are counted twice!!)

classified_robot_info = []

count = 0

for i in range(len(robot_info)):
    temp_player = []
    for j in range(15):
        temp_period = []
        for k in range(len(robot_info[i])):
            if j == 0:
                a = robot_info[i][k][0] < intervaltime_s[j][1]
                # b = robot_info[i][k][1] < intervaltime_s[j][1]  COMMENTED OUT SINCE WE SHOULD ALLOW BOTS TO GO ACROSS PERIODS
                if a:
                    temp_period.append(robot_info[i][k])
                    count += 1
            if j > 0 and j < 14:
                # create boolean values
                # a = robot_info[i][k][0] > intervaltime_s[j][0]  COMMENTED OUT SINCE WE SHOULD ALLOW BOTS TO GO ACROSS PERIODS
                b = robot_info[i][k][1] > intervaltime_s[j][0]
                # c = robot_info[i][k][0] < intervaltime_s[j][1]  # This is superfluous since robot...[1] > robot...[0]
                d = robot_info[i][k][1] < intervaltime_s[j][1]
                if b and d:
                    temp_period.append(robot_info[i][k])
                    count += 1
            if j == 14:
                if robot_info[i][k][1] > intervaltime_s[j][0]:
                    temp_period.append(robot_info[i][k])
                    count += 1
        temp_player.append(temp_period)
    classified_robot_info.append(temp_player)

# inspect how many robots were active in each period

total_robot_period = []

for i in range(15):
    temp_period = 0
    for j in range(Nplayer):
        temp_period += len(classified_robot_info[j][i])
    total_robot_period.append(temp_period)    

total_robot_period  # This lists how many robots were active in each period for the Nplayers

plt.figure()
plt.plot(range(1,16), total_robot_period, "ko")
plt.title("Total Number of Robots ACTIVE in each Period")
plt.ylabel("number of robots")
plt.xlabel("period number")
plt.grid()

# Analyze bot usage (per period, across all players) by side and type
# One can easily change the code to analyze bot usage per player
# 2023: Order submission number added ("orderct")

R_RE_BUY_period = []
R_RE_SELL_period = []
R_RE_BUYSELL_period = []

R_MM_BUY_period = []
R_MM_SELL_period = []
R_MM_BUYSELL_period = []

R_RE_BUY_orderct_period = []
R_RE_SELL_orderct_period = []
R_RE_BUYSELL_orderct_period = []

R_MM_BUY_orderct_period = []
R_MM_SELL_orderct_period = []
R_MM_BUYSELL_orderct_period = []

for i in range(15):
    temp_RE_BUY = 0
    temp_RE_SELL = 0
    temp_RE_BUYSELL = 0
    temp_RE_BUY_orderct = 0
    temp_RE_SELL_orderct = 0
    temp_RE_BUYSELL_orderct = 0
    temp_MM_BUY = 0
    temp_MM_SELL = 0
    temp_MM_BUYSELL = 0
    temp_MM_BUY_orderct = 0
    temp_MM_SELL_orderct = 0
    temp_MM_BUYSELL_orderct = 0
    for j in range(Nplayer):
        for k in range(len(classified_robot_info[j][i])):
            a = classified_robot_info[j][i][k][3] == "BUY"
            b = classified_robot_info[j][i][k][3] == "SELL"
            c = classified_robot_info[j][i][k][3] == "BUY,SELL"
            d = classified_robot_info[j][i][k][4] == "REACTIVE"
            e = classified_robot_info[j][i][k][4] == "MARKET_MAKER"
            if a and d:
                temp_RE_BUY += 1
                temp_RE_BUY_orderct += classified_robot_info[j][i][k][6]
            if a and e:
                temp_MM_BUY += 1
                temp_MM_BUY_orderct += classified_robot_info[j][i][k][6]
            if b and d:
                temp_RE_SELL += 1
                temp_RE_SELL_orderct += classified_robot_info[j][i][k][6]
            if b and e:
                temp_MM_SELL += 1
                temp_MM_SELL_orderct += classified_robot_info[j][i][k][6]
            if c and d:
                temp_RE_BUYSELL += 1
                temp_RE_BUYSELL_orderct += classified_robot_info[j][i][k][6]
            if c and e:
                temp_MM_BUYSELL += 1
                temp_MM_BUYSELL_orderct += classified_robot_info[j][i][k][6]
    R_RE_BUY_period.append(temp_RE_BUY)
    R_RE_SELL_period.append(temp_RE_SELL)
    R_RE_BUYSELL_period.append(temp_RE_BUYSELL)
    R_MM_BUY_period.append(temp_MM_BUY)
    R_MM_SELL_period.append(temp_MM_SELL)
    R_MM_BUYSELL_period.append(temp_MM_BUYSELL)

    R_RE_BUY_orderct_period.append(temp_RE_BUY_orderct)
    R_RE_SELL_orderct_period.append(temp_RE_SELL_orderct)
    R_RE_BUYSELL_orderct_period.append(temp_RE_BUYSELL_orderct)
    R_MM_BUY_orderct_period.append(temp_MM_BUY_orderct)
    R_MM_SELL_orderct_period.append(temp_MM_SELL_orderct)
    R_MM_BUYSELL_orderct_period.append(temp_MM_BUYSELL_orderct)

#  Save
df = pd.DataFrame({
    "RE_BUY": R_RE_BUY_period,
    "RE_SELL": R_RE_SELL_period,
    "RE_BUYSELL": R_RE_BUYSELL_period,
    "MM_BUY": R_MM_BUY_period,
    "MM_SELL": R_MM_SELL_period,
    "MM_BUYSELL": R_MM_BUYSELL_period,
}
)
df.to_csv('robottypes_per_period.csv')

# plot a sample of the results: Use of MM and RE

total_RE_period = []

for i in range(15):
    temp = R_RE_BUY_period[i]+R_RE_SELL_period[i]+R_RE_BUYSELL_period[i]
    total_RE_period.append(temp)

total_RE_period # [14, 17, 10, 12, 4, 6, 6, 7, 2, 6, 3, 4, 3, 2, 6]


total_MM_period = []

for i in range(15):
    temp = R_MM_BUY_period[i]+R_MM_SELL_period[i]+R_MM_BUYSELL_period[i]
    total_MM_period.append(temp)

total_MM_period  # [21, 15, 14, 10, 15, 11, 11, 10, 13, 5, 7, 11, 14, 5, 5]

plt.figure()
plt.plot(range(1,16), total_MM_period, "k", range(1,16), total_RE_period, "k--")    
plt.title("Number of Robots ACTIVE in each Period BY TYPE")
plt.ylabel("number of robots")
plt.xlabel("period number")
plt.legend(('Market Maker', 'Reactive'))
plt.grid()

# plot another sample of the results: Order Submission of MM and RE

total_RE_orderct_period = []

for i in range(15):
    temp = R_RE_BUY_orderct_period[i]+R_RE_SELL_orderct_period[i]+R_RE_BUYSELL_orderct_period[i]
    total_RE_orderct_period.append(temp)

total_RE_orderct_period # []


total_MM_orderct_period = []

for i in range(15):
    temp = R_MM_BUY_orderct_period[i]+R_MM_SELL_orderct_period[i]+R_MM_BUYSELL_orderct_period[i]
    total_MM_orderct_period.append(temp)

total_MM_orderct_period  # []

plt.figure()
plt.plot(range(1,16), total_MM_orderct_period, "k", range(1,16), total_RE_orderct_period, "k--")
plt.title("Number of Robot Orders in each Period BY TYPE")
plt.ylabel("number of Orders")
plt.xlabel("period number")
plt.legend(('Market Maker', 'Reactive'))
plt.grid()

# plot another sample: side usage (BUY SELL BUYSELL)

total_BUY_period = []
total_SELL_period = []
total_BUYSELL_period = []

for i in range(15):
    temp_BUY = R_RE_BUY_period[i]+R_MM_BUY_period[i]
    temp_SELL = R_RE_SELL_period[i]+R_MM_SELL_period[i] 
    temp_BUYSELL = R_RE_BUYSELL_period[i]+R_MM_BUYSELL_period[i]
    total_BUY_period.append(temp_BUY)
    total_SELL_period.append(temp_SELL)
    total_BUYSELL_period.append(temp_BUYSELL)

total_BUY_period     # [13, 25, 14, 12, 5, 4, 5, 1, 6, 3, 3, 1, 3, 1, 4]
total_SELL_period    # [12, 5, 4, 8, 11, 10, 11, 12, 9, 8, 7, 13, 10, 4, 4]
total_BUYSELL_period # [10, 2, 6, 2, 3, 3, 1, 4, 0, 0, 0, 1, 4, 2, 3]

plt.figure()
plt.plot(range(1,16), total_BUY_period, "b", range(1,16), total_SELL_period,\
    "r", range(1,16), total_BUYSELL_period, "k")    
plt.title("Number of Robots ACTIVE in each Period BY SIDE")
plt.ylabel("number of robots")
plt.xlabel("period number")
plt.legend(('BUY', 'SELL', 'BUY&SELL'))
plt.grid()

################ Start Analysis Merging Robot Log and Market Data ##################
# Information needed besides time
# name = 'Extract_FM_CSV.xls'
name = 'output15ADD.xls' # FM csv file converted to xls
market = 173 #  market
begin_session = 1673  # Round 1 (PB changed first session id to 1673 to have continguus sessions IDs)
end_session = 1687  # Round 15
min_time = 052142.280  # min createDate (hours:min:sec.ms without ":")
max_time = 0673540.803  # max lastModifiedDate

### first load order data from csv file (converted to xls file; see Pbaspread_E1.py)

wb = open_workbook(name)
for s in wb.sheets():
    # print 'Sheet:',s.name
    market_book = []
    for row in range(s.nrows):
        col_value = []
        for col in range(s.ncols):
            value = (s.cell(row, col).value)
            try:
                value = str(int(value))
            except:
                pass
            col_value.append(value)
        market_book.append(col_value)

# now categorize orders submitted per player (whether manual and robot):
# (python column index for the following: email=1  period=4  order ID=6 original ID=7 supplier ID = 8 side = 11)
# Identification of player by ID: all IDs are emails, of the form r#@bmm, so second character is player number

# Total orders submitted by each player
order_each_player = []
order_list_each_player = []
temp = 0
for i in range(1, Nplayer + 1):
    for j in range(len(market_book)):
        tempOrder = []
        if market_book[j][1] != '':
            if market_book[j][1][0] == 'r':  # All (email) IDs for players start with "r"
                a = int(market_book[j][1][1]) == i  # Is order initiated by player i?
                b = market_book[j][6] == market_book[j][7] == market_book[j][8]  # Is this the original order record?
                c = market_book[j][10] == 'LIMIT'
                if a and b and c:
                    temp += 1
                    tempOrder.append(market_book[j][6])
                    tempOrder.append(i - 1)
                    tempOrder.append('Manual')  # Temporarily assigned as manual, to be changed later
                    tempOrder.append(-1)  # Period placeholder, to be identified later
                    order_list_each_player.append(tempOrder)
    order_each_player.append(temp)
    order_list_each_player_length = temp

order_each_player  # [100, 237, 56, 88, 261, 123, 62, 178]
order_list_each_player

# total orders submitted by all players each period (for market 'market'); note that period is called "session" here!

total_order_each_period = []
order_ID_each_period = []
order_price_each_period = []
order_type_each_period = []
order_time_each_period = []

for session in range(begin_session, end_session + 1):
    temp = 0
    tempIDs = []
    tempPrices = []
    tempTypes = []
    tempTimes = []
    for j in range(1, len(market_book)):
        if market_book[j][13] != '':
            if market_book[j][6].isnumeric():
                a = int(market_book[j][4]) == session
                b = market_book[j][6] == market_book[j][7]
                c = market_book[j][7] == market_book[j][8]
                d = market_book[j][5] == market
                if a and b and c:
                    temp += 1
                    tempIDs.append(market_book[j][6])
                    tempPrices.append(market_book[j][13])
                    tempTypes.append(market_book[j][11])
                    tempB = market_book[j][14].split("T")[1]
                    tempB = tempB.split(".")[0]
                    temps = tempB.split(":")
                    if temps[0] == '05': temps[0] = '15'
                    if temps[0] == '06': temps[0] = '16'
                    tempB = ':'.join(temps)
                    tempTimes.append(tempB)
    order_ID_each_period.append(tempIDs)
    order_price_each_period.append(tempPrices)
    order_type_each_period.append(tempTypes)
    total_order_each_period.append(temp)
    order_time_each_period.append(tempTimes)

total_order_each_period  # [123, 106, 76, 89, 94, 68, 55, 89, 72, 45, 33, 62, 105, 36, 52]

# total trades submitted by all players each period (again, it's referred to as "session" in the do-loop)
# also collect Flex-E-Markets (trade) order IDs, and corresponding SID and CID

total_trade_each_period = []

trade_orderID_each_period = []

for session in range(begin_session, end_session + 1):
    temp = 0
    period_trade_orderID = []
    for j in range(1, len(market_book)):
        tempA = []
        # determine whether record refers to a trade
        if market_book[j][6] != '':
            if market_book[j][6].isnumeric():
                if market_book[j][3].isnumeric() and market_book[j][5].isnumeric():
                    if int(market_book[j][3]) == session:
                        if int(market_book[j][5]) == market:
                            if market_book[j][10] != 'CANCEL':
                                if market_book[j][9].isnumeric():
                                    if int(market_book[j][6]) > int(market_book[j][9]) > 0:
                                        # This indicates a trade; see BAspread method above
                                        temp += 1  # count trades
                                        tempA.append(int(market_book[j][6]))  # Order ID
                                        tempA.append(int(market_book[j][8]))  # S(upplier) ID
                                        tempA.append(int(market_book[j][9]))  # C(onsumer) ID
                                        tempA.append(int(market_book[j][13]))  # price
                                        tempA.append(market_book[j][11])  # type
                                        tempB = market_book[j][14].split("T")[1]
                                        tempB = tempB.split(".")[0]
                                        temps = tempB.split(":")
                                        if temps[0] == '05': temps[0] = '15'
                                        if temps[0] == '06': temps[0] = '16'
                                        tempB = ':'.join(temps)
                                        tempA.append(tempB)  # time
                                        period_trade_orderID.append(tempA)
    total_trade_each_period.append(temp)
    trade_orderID_each_period.append(period_trade_orderID)

sum(total_trade_each_period)

plt.figure()
plt.plot(range(1, 16), total_trade_each_period, "k")
plt.title("Total Number of Trades in each Period")
plt.ylabel("number of trades")
plt.xlabel("period number")
plt.grid()

# plot order to trade ratio for each period

order_trade_ratio = []

for i in range(15):
    ratio = (total_order_each_period[i] / total_trade_each_period[i]) * 100
    order_trade_ratio.append(ratio)

order_trade_ratio

plt.figure()
plt.plot(range(1, 16), order_trade_ratio, "k--")
plt.title("Order-to-Trade Ratio in each Period")
plt.ylabel("ratio (in %)")
plt.xlabel("period number")
plt.grid()

# total robot orders submitted each period

total_robot_order_each_period = []

for i in range(15):
    start_time = intervaltime_s[i][0]
    end_time = intervaltime_s[i][1]
    temp = 0
    for j in range(len(active_book)):
        for k in range(len(active_book[j])):
            a = int(active_book[j][k][2]) >= start_time
            b = int(active_book[j][k][2]) <= end_time
            c = active_book[j][k][7][
                0:8] == 'An order'  # This identifies records in robot log that confirm an order submission
            if a and b and c:
                temp += 1
    total_robot_order_each_period.append(temp)

plt.figure()
plt.plot(range(1, 16), total_order_each_period, "k", range(1, 16), total_robot_order_each_period, "b")
plt.title("Total [Orders Submitted] and [Orders Submitted by Robot] for each Period")
plt.ylabel("number of orders")
plt.xlabel("period number")
plt.legend(('All Orders', 'Robot Orders'))
plt.grid()

# compute the ratio of above

robot_order_ratio = []

for i in range(15):
    robot_order_ratio.append(total_robot_order_each_period[i] / total_order_each_period[i] * 100)

plt.figure()
plt.plot(range(1, 16), robot_order_ratio, "k:")
plt.title("Ratio of Robot Orders to Total Orders for each Period")
plt.ylabel("ratio (in %)")
plt.xlabel("period number")
# plt.legend()
plt.grid()

### total trade made by robot each period

# (active_book[5][5][7]).split(":")[2]

# trades that had at least one robot involved for each period
# In robot log, entries with 'An order was ac' states that the order was accepted, not necessarily that it traded!
# This is how Charlie (Tingxuan) recognized bot trades, unfortunately. But only for Re (R) robots is this correct
# For MM (M) robots, we know whether robot-generated orders traded only if new orders were submitted and accepted:
# indicated in acceptance record as "REFb# where # > 1" except LAST record before end of robot (which only suggests a
# a submission)
# There are several issues with this. Probably the most damaging is that if the bot is switched off but the order is still sitting
# in the book (when switching off, or replacing bots, bots do not clean up/cancel their orders), it can still trade.
# There is another way to determine whether bot orders traded. When they are accepted, the bot log includes the order ID
# so we can check in market_book whether the order traded. Since bot orders are always for 1 unit, this is easy to determine.
# (i) If the CID = 0 it is a market order and hence traded
# (ii) If the CID > (Order) ID then it traded unless CID refers to a cancel
# Yet another way is to go back to the SID and CID of the order entries in market_book (see trade_ordernumber_book) and
# check whether SID and CID are mentioned in the robot log. No further checking has to be done since robot orders are never
# multi-unit orders so the original order ID always shows up as either SID or CID.
# The latter two procedures are the best since it will catch all robot-generated orders that traded regardless of whether
# the robot was engaged when it traded.

################ Implement last strategy discussed above ######################
## First; collect order number of orders accepted in Flex-E-Markets; ...
## Need this later to check which trades involved a robot

robot_ordertime_each_period = []
robot_orderprice_each_period = []
robot_ordertype_each_period = []

for i in range(15):
    start_time = intervaltime_s[i][0]
    end_time = intervaltime_s[i][1]
    period_orders_time = []
    period_orders_price = []
    period_orders_type = []
    for j in range(len(active_book)):
        for k in range(len(active_book[j])):
            if active_book[j][k][7][0:15] == 'An order was ac':
                # This entry in robot log states the order was accepted and but does NOT contain the Flex-E-Markets order number!!
                a = int(active_book[j][k][2]) >= start_time
                b = int(active_book[j][k][2]) <= end_time
                if a and b:
                    temp = active_book[j][k][7].split(":")[4]
                    temp = temp.split("@")[1]
                    tempt = active_book[j][k][1].split(",")[0]
                    period_orders_time.append(tempt)
                    period_orders_price.append(temp)
                    period_orders_type.append(active_book[j][k][7].split(":")[3])
    robot_ordertime_each_period.append(period_orders_time)
    robot_orderprice_each_period.append(period_orders_price)
    robot_ordertype_each_period.append(period_orders_type)


# Now determine orderIDs of ROBOTS
# Go over all orders in a period (FM) and match robot log data

robot_order_ID_each_period = []

for session in range(begin_session, end_session + 1):
    i = session - begin_session
    temp = 0
    robot_order_FM_ID = []
    for j in range(len(order_ID_each_period[i])):
        # determine whether record
        vlag = 0
        for k in range(len(robot_ordertime_each_period[i])):
            keyRL = robot_ordertime_each_period[i][k].split(":")
            keyRL = ''.join(keyRL)
            keyFM = order_time_each_period[i][j].split(":")
            keyFM = ''.join(keyFM)
            a = int(keyRL) >= int(keyFM)  # Is time on log after time in FM?
            b = int(robot_orderprice_each_period[i][k]) == int(order_price_each_period[i][j])  # Is order price the same?
            c = robot_ordertype_each_period[i][k] == order_type_each_period[i][j]  # Is order type the same?
            if a and b and c and vlag == 0:
                temp += 1
                vlag = 1
                robot_order_FM_ID.append(order_ID_each_period[i][j])

    robot_order_ID_each_period.append(robot_order_FM_ID)

# Now go over all trades in a period and identify whether the record included a SID or CID that features in robot_orderID_each-period
# Also determine whether trade is among robots, not with humans

total_robot_trade_each_period = []
total_robotrobot_trade_each_period = []

for session in range(begin_session, end_session + 1):
    i = session - begin_session
    temp1 = 0
    temp2 = 0
    robot_trade_FM_ID = []
    robot_trade_FM_CID = []
    for k in range(total_trade_each_period[i]):
        # determine whether record has corresponding SID or CID among robot orders in same period
        # If so, a robot was involved (avoid double counting though!)
        vlag = 0
        for j in range(len(robot_order_ID_each_period[i])):
            a = int(robot_order_ID_each_period[i][j]) == trade_orderID_each_period[i][k][2]  # CID
            b = int(robot_order_ID_each_period[i][j]) == trade_orderID_each_period[i][k][1]  # SID
            if (a or b) and vlag == 1:
                temp2 +=1
            if (a or b) and vlag == 0:
                temp1 += 1
                vlag = 1

    total_robot_trade_each_period.append(temp1)
    total_robotrobot_trade_each_period.append(temp2)

sum(total_robot_trade_each_period)  # Total number of trades where at least one side is a robot

plt.figure()
plt.plot(range(1, 16), total_robot_trade_each_period, "b", range(1, 16), total_trade_each_period, "k")
plt.title("[Total Trades] and [Trades involving Robots] per Period")
plt.ylabel("number of trades")
plt.xlabel("period number")
plt.grid()

## Now per player: period, orders submitted, orders by robot; update order_list_each_player

for session in range(begin_session, end_session+1):
    i = session - begin_session
    for j in range(len(robot_order_ID_each_period[i])):
        vlag = 0
        for k in range(order_list_each_player_length):
            if int(robot_order_ID_each_period[i][j]) == int(order_list_each_player[k][0]):
                order_list_each_player[k][2] = 'ROBOT'
                order_list_each_player[k][3] = i
                vlag = 1
        if vlag == 0:
            print('robot order not assigned to player')
            print([i, j])

#### Save all robot use data

# Per period

df = pd.DataFrame({
    "total_order_each_period": total_order_each_period,
    "total_trade_each_period": total_trade_each_period,
    "total_robot_order_each_period": total_robot_order_each_period,
    "total_robot_trade_each_period": total_robot_trade_each_period,
    "total_robotrobot_trade_each_period": total_robotrobot_trade_each_period
}
)
df.to_csv('robotordertrade_per_period.csv')


# Per PLAYER
Details = ['Order_ID', 'Participant','Type','Period_IF_Robot']
with open('order_list_each_player.csv', 'w') as f:
    write = csv.writer(f)
    write.writerow(Details)
    write.writerows(order_list_each_player)