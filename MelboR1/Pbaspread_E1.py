# -*- coding: utf-8 -*-
"""
Created on Wed 17/3/2021, changed on Wed 3/5/2023

@author: PB

Refactoring Tingxuan Huang's baspread_E1.py using newly created ReadBookFromFMcsv.py

(May 23: BA spread computed by taking order ID of an order and searching for order ID of order where former is consumed
instead of reverse: find order ID in consumer record of original order ID; latter does not work in case there are FM mistakes:
order is consumed more than once)

Does not require work on original FM (Flex-E-Markets) output csv file; it only needs to be converted to xls (and perhaps, for
easy of reference, deletion of irrelevant sessions.

TWO PARTS:
(i) Methods, to (a) determine bid-ask (BA) spread, (b) read trade prices, (c) session beginning and ending times
(ii) MAIN:
(a) Trade price history [PLOT]
(b) Roll BA spread based on book 1s before each trade (per session)
(c) "True" BA spread based on book 1s before each trade [PLOT, per transaction]
(d) Average "true" BA spread based on book 1s before each trade (per session; averaged over trade count)
(e) "True" BA spread, each second, all sessions [PLOT]


"MAIN" starts with a list of parameters that identify the experiment/market, such as session IDs, market ID, ...
TO BE ADJUSTED IF ANOTHER EXPERIMENT IS TO BE ANALYZED THAN THE ONE IN THIS ORIGINAL PROGRAM

Some major lists or (numpy)arrays that the program creates (arrays are indicated with A)
TRADES:
tradeprice = trade prices (array version: Aprice)
tradetime = trade time in seconds
o_tradetime = original trade time, in hrmnse.milliseconds as in FM output file
tradetype = BUY/SELL (nature of market order)
tradevolume = number of units traded
tradesession = ID of the session of the trade record (array version: Asession)
B/A Spread:
tradetime_min = trade time minus 1 second, in seconds
BAspreadALL = BA spread recording, one for each trade, as of 1 second before trade (array version: ABA)
session_min = sessions corresponding to BA spread records in BAspreadALL (array version: ASS)
tradetime_exact = time, in increments of 1 second, from beginning to end of experiment
BAspreadALL_exact = BA spread recording, per second in experiment
sessions_exact = sessions corresponding to BA spread records in BAspreadALL2

REMARKS:
- The program takes a while to run because the FM output file is read repeatedly. This is especially true for (ii)(e) above,
whereby the output file is revisited for every second from the beginning to end of the experiment, regardless of whether
the second falls inside or outside a trading session
- The method that determines the BA spread occasionally prints times and session numbers when bid-ask spreads are found
 to be negative. This is extremely rare, but will happen if FM receives orders within milliseconds and classifies the second
 order as a standing order when it could have been crossed against the first one, but the first one was not fully processed
 yet
- Two versions of time are used: (i) Time in hrmnse.milliseconds or hrmnse (without milliseconds); this is the convention
in the FM output file; (ii) Time in seconds. This program produces plots using the latter notion of time (otherwise there
are big gaps since hours consist of only 60, not 100, minutes, and minutes consist of only 60, not 100, seconds).

"""

import numpy as np
from xlrd import open_workbook
from matplotlib import pyplot as plt
from statsmodels.tsa import stattools as st
import pandas as pd

def getbookandBAspread(export_fn, time_snap, session, market):

# Reads xls version of Flex-E-Markets output csv file; make sure "createdDate" and "lastModifiedDate" are in format <DATE>T<hr:mn:sec:ms>
# Since DATE is dropped (which the program does here0, be careful when time goes from 23:59:59.999 to 00:00:00.001!
#
# Goal:
# - construct the book of orders at a particular point in time (in seconds or even less) and for a particular market:
#     This is the method "getbookandBAspread"

    ## read excel file and store the data into list called "values"
    wb = open_workbook(export_fn)
    for s in wb.sheets():
        #print 'Sheet:',s.name
        values = []
        for row in range(s.nrows):
            col_value = []
            for col in range(s.ncols):
                value  = (s.cell(row,col).value)
                try : value = str(int(value))
                except : pass
                # The following ensures times are in the format hrmnse.msc
                # E.g. 05:24:18.826 becomes 052418.826
                isdatetime = value.find("T")
                if isdatetime > 0:
                    value = value[isdatetime+1:]
                    value = value.replace(':','')
                col_value.append(value)
            values.append(col_value)

    # Start building book by collecting limit orders that were valid at "time_snap"
    # Careful: orders with CID (Consumer ID) = "NULL" are valid ONLY till end of session!
    # So session id is needed as well -- we need to avoid an order to be picked up in a "time_snap" of a future session

    # Declare book (lists, per side: prices; quantities N;
    # length of lists varies over time of course, as book builds and shrinks; can even be empty)
    poolofbuy = []
    poolofbuyN = []
    poolofsell = []
    poolofsellN = []

    for i in range(0, len(values)-1):
        # first ascertain that record pertains to an order as opposed to holdings or other records
        # in the FM output file (first "if") and to the right market (second "if")
        if values[i][5].isnumeric() and values[i][3].isnumeric():
            if int(values[i][5]) == market and int(values[i][3]) == session:
                if values[i][9].isnumeric():
                # check if it is limit buy order, not a cancel, a trade, market order, or order to be split
                # Note: when a multi-unit market order is split against multiple incoming orders and the last split
                # happens after another limit order came in, trade takes place at the latter limit order price; a limit
                # order is converted to a market order and trades against the split order at the split order price
                # but the trade record violates the rule that [8] > [9]! It is as if the new incoming order is
                # briefly put in the book at the price of the split order!

                # Reverse search relative to original program: Search for
                # FIRST future record where C(onsumer) ID == O(rder) ID (sometimes order is consumed multiple
                # times, mistakenly)

                # Buy orders:
                    if values[i][11] == 'BUY' and int(values[i][6]) < int(values[i][9]):  # values[i][10] == 'LIMIT' and
                        # check if the limit buy order's came in before or at 'time_snap'
                        if float(values[i][14]) <= time_snap:
                            # Then check whether order is no longer standing at time_snap because:
                            # (i) order traded (when there is a record ID <= time_snap for which
                            # supplier ID = CID of original record and CID < supplierID)
                            # (ii) order canceled (when there is a record ID <= time_snap for which
                            # supplier ID = CID of original record and type=CANCEL)
                            isstand = 1  # By default it is standing
                            OID = int(values[i][6])  # OID
                            j = i + 1
                            withintime = 1
                            while isstand == 1 and withintime == 1:
                                if values[j][9].isnumeric():
                                    if float(values[j][14]) <= time_snap:
                                        if int(values[j][9]) == OID:  # is original order ID = current CID?
                                            isstand = 0  # order traded or canceled
                                    else:
                                        withintime = 0
                                j = j + 1
                            if isstand == 1:
                                poolofbuy.append(int(values[i][13]))  # order price
                                poolofbuyN.append(int(values[i][12]))  # order quantity

                # Sell orders:
                    if values[i][11] == 'SELL' and int(values[i][6]) < int(values[i][9]):  # values[i][10] == 'LIMIT' and
                        # check if the limit sell order's came in before or at 'time_snap'
                        if float(values[i][14]) <= time_snap:
                            # Then check whether order is no longer standing at time_snap because:
                            # (i) order traded (when there is a record ID <= time_snap for which
                            # supplier ID = CID of original record and CID < supplierID)
                            # (ii) order canceled (when there is a record ID <= time_snap for which
                            # supplier ID = CID of original record and type=CANCEL)
                            isstand = 1  # By default it is standing
                            OID = int(values[i][6])  # OID
                            j = i + 1
                            withintime = 1
                            while isstand == 1 and withintime == 1:
                                if values[j][9].isnumeric():
                                    if float(values[j][14]) <= time_snap:
                                        if int(values[j][9]) == OID:  # is original order ID = current CID?
                                            isstand = 0  # order traded or canceled
                                    else:
                                        withintime = 0
                                j = j + 1
                            if isstand == 1:
                                poolofsell.append(int(values[i][13]))  # order price
                                poolofsellN.append(int(values[i][12]))  # order quantity
                                
    if len(poolofbuy)>0:
        bestbuy = max(poolofbuy)
    else:
        bestbuy = 0
    if len(poolofsell)>0:
        bestsell = min(poolofsell)
    else:
        bestsell = 0
    if bestbuy > 0 and bestsell > 0:
        BAspread = bestsell - bestbuy
        if BAspread < 0:
            print(BAspread)
            print(time_snap)
            print(session)
    else:
        BAspread = -1

    return BAspread, bestbuy, bestsell

def gettrades(export_fn, session, market):

# Reads xls version of Flex-E-Markets output csv file; make sure "createdDate" and "lastModifiedDate" are in format <DATE>T<hr:mn:sec:ms>
# Since DATE is dropped (which the program does here0, be careful when time goes from 23:59:59.999 to 00:00:00.001!
#
# Goal:
# - get trades and trade times

    ## read excel file and store the data into list called "values"
    wb = open_workbook(export_fn)
    for s in wb.sheets():
        #print 'Sheet:',s.name
        values = []
        for row in range(s.nrows):
            col_value = []
            for col in range(s.ncols):
                value  = (s.cell(row,col).value)
                try : value = str(int(value))
                except : pass
                # The following ensures times are in the format hrmnse.msc
                # E.g. 05:24:18.826 becomes 052418.826
                isdatetime = value.find("T")
                if isdatetime > 0:
                    value = value[isdatetime+1:]
                    value = value.replace(':','')
                col_value.append(value)
            values.append(col_value)

    # Collect trades, trade times, quantities and whether buy or sell generated, for session and market
    trades = []

    for i in range(0, len(values)-1):
        # first ascertain that record pertains to an order as opposed to holdings or other records
        # in the FM output file (first "if") and to the right market (second "if")
        # then check whether the order type (BUY, SELL) is correctly indicated (FM reverts if market order hits
        # a multiunit order that needs to be split; "if" after "misclassification")
        if values[i][3].isnumeric() and values[i][5].isnumeric():
            if int(values[i][3]) == session:
                if int(values[i][5]) == market:
                    if values[i][10] != 'CANCEL':
                        if values[i][9].isnumeric():
                            if int(values[i][6]) > int(values[i][9]) > 0:  # This indicates a trade; see BAspread method above
                                # convert time to seconds.milliseconds instead of hrmnse.milliseconds
                                temp_time = float(values[i][14])
                                convert_time = (60*60)*int(temp_time/10000) + 60*int((temp_time % 10000)/100) + (temp_time % 100)
                                temp_type = values[i][11]
                                # convert BUY to +1, Sell to -1
                                convert_type = (temp_type == 'BUY') - (temp_type == 'SELL')
                                # Correct misclassification in FM when market order hits multiunit order that is to be
                                # split; this can be recognized because for valid classification, SID > CID!
                                if int(values[i][8]) < int(values[i][9]):
                                    convert_type = -convert_type
                                # add record with price, original time, converted time, quantity, BUY/SELL and session
                                to_be_added = [int(values[i][13]), temp_time, convert_time, int(values[i][12]), convert_type, session]
                                trades.append(to_be_added)

    return trades

def getsessiontimes(export_fn, session):

# Determines begin/end times of "session"

    vlagb = 0  # Flag used to indicate whether record belogs to "session"
    vlage = 0
    begin_time = ''
    end_time = ''

    ## read excel file and store the data into list called "values"
    wb = open_workbook(export_fn)
    for s in wb.sheets():
        # print 'Sheet:',s.name
        values = []
        for row in range(s.nrows):
            col_value = []
            for col in range(s.ncols):
                value = (s.cell(row, col).value)
                try:
                    value = str(int(value))
                except:
                    pass
                # The following ensures times are in the format hrmnse.msc
                # E.g. 05:24:18.826 becomes 052418.826
                isdatetime = value.find("T")
                if isdatetime > 0:
                    value = value[isdatetime + 1:]
                    value = value.replace(':', '')
                col_value.append(value)
            if col_value[3].isnumeric():
                if int(col_value[3]) == session and col_value[14] != '':
                    if vlagb == 0:
                        begin_time = float(col_value[14])
                        begin_time = int(begin_time)
                        vlagb = 1
                if int(col_value[3]) > session and vlagb == 1 and vlage == 0 and col_value[14] != '':
                    vlage = 1
                    end_time = int(lastModTime)
            if col_value[15] != '' and col_value[15].find('.') != -1:
                lastModTime = float(col_value[15])+1.0
        if end_time == '':
            end_time = int(lastModTime)
        sessiontimes = [begin_time, end_time]
    return sessiontimes



############################# MAIN #####################################

# Information needed besides time
# name = 'Extract_FM_CSV.xls'
name = 'output15ADD.xls' # FM csv file converted to xls (from marketplaceSSW.csv)
mark = 166 #  market
begin_session = 896  # Round 1
end_session = 910  # Round 15
min_time = 051849.671  # min createDate
max_time = 064411.899  # max lastModifiedDate

#=============================================================================
# Extract variables we need, starting with transaction prices
# This code reads the variables in the format/arrays of the original program (baspread_E1.py)

tradeprice = []
tradetime = []
o_tradetime = [] # Original time, in hrmnse.milliseconds, needed later for bid-ask spread
tradetype = []
tradevolume = []
tradesession = []
for sess in range(begin_session, end_session+1):
    trans_prices = gettrades(name, sess, mark)
    tradeprice.extend([row[0] for row in trans_prices])
    tradetime.extend([row[2] for row in trans_prices])  # This is converted time (i.e., in seconds)
    o_tradetime.extend([row[1] for row in trans_prices])  # This is original time
    tradetype.extend([row[4] for row in trans_prices])
    tradevolume.extend([row[3] for row in trans_prices])
    tradesession.extend([row[5] for row in trans_prices])


plt.figure()
plt.scatter(tradetime, tradeprice, c=tradetype, cmap="Set1")
plt.title("Trades [Session 1; Red = Sale, Grey = Buy]")
plt.ylabel("Price (Cents)")
plt.xlabel("Time (Seconds)")
plt.show()

# Save output
t_prices = pd.DataFrame(
    {
        "seconds": tradetime,
        "price": tradeprice,
        "buy_sell": tradetype,
        "round": tradesession,
    }
)
t_prices.to_csv('save_t_prices.csv')

#=============================================================================
# Compute Roll estimates of the BA spread, per session
BAsession = []
BA=[]
Aprice = np.array(tradeprice)
Asession = np.array(tradesession)
for i in range(begin_session, end_session+1):
    PriceExtract = np.where(Asession == i, Aprice, np.nan)
    # Take first differences
    DiffPriceExtract = np.diff(PriceExtract)
    # Delete the "nan"s
    DiffPriceExtract = DiffPriceExtract[~np.isnan(DiffPriceExtract)]
    # Compute autocovariance
    ac = st.acovf(DiffPriceExtract,nlag=1)
    baROLL = 2*np.sqrt(np.abs(ac))
    print(f'Session {i}')
    BAsession.append(i)
    print(f'Roll BA spread [in cents] is {baROLL[1]}')
    BA.append(baROLL[1])

# Save output
BA_roll = pd.DataFrame(
    {
        "round": BAsession,
        "bid_ask": BA,
    }
)
BA_roll.to_csv('save_BA_roll.csv')

#=============================================================================
# Extract BA spread (True B/A spread at each trade time - 1s)

# Note: see file "NoteFMRecord.rtf"

tradetime_min = []
BAspreadALL = []
session_min = []
for t in range(0,len(o_tradetime)-1):
    time_t = o_tradetime[t]-1.0  # one second before trade
    session_t = tradesession[t]
    [BA, bb, bs] = getbookandBAspread(name, time_t, session_t, mark)
    # REMARK: This prints times and session numbers when the bid ask spread is found to be negative (it will
    # also print the value of the bid ask spread)
    convert_time = (60 * 60) * int(time_t / 10000) + 60 * int((time_t % 10000) / 100) + int(time_t % 100)
    tradetime_min.append(convert_time)
    BAspreadALL.append(BA)
    session_min.append(session_t)

plt.figure()
plt.scatter(tradetime_min, BAspreadALL)
plt.title("B/A Spread [Session 1]")
plt.ylabel("Spread (Cents)")
plt.xlabel("Time (Seconds)")
plt.show()

# Save output
BA_trade = pd.DataFrame(
    {
        "time": tradetime_min,
        "bid_ask": BAspreadALL,
        "round": session_min,
    }
)
BA_trade.to_csv('save_BA_trade.csv')

#=============================================================================
# Compute average B/A spread per session (average over trades, not seconds)
ABA = np.array(BAspreadALL)
ASS = np.array(session_min)
for i in range(begin_session, end_session+1):
    BAextract = np.where(ASS == i, ABA, np.nan)
    # Get rid of "nan"s
    BAextract = BAextract[~np.isnan(BAextract)]
    # Compute stats
    mn = np.nanmean(np.where(BAextract >= 0, BAextract, np.nan), axis=0)
    sd = np.nanstd(np.where(BAextract >= 0, BAextract, np.nan), axis=0)
    mini = np.nanmin(np.where(BAextract >= 0, BAextract, np.nan), axis=0)
    maxi = np.nanmax(np.where(BAextract >= 0, BAextract, np.nan), axis=0)
    print(f'Session {i}')
    print(f'Mean BA spread is {mn}')
    print(f'St Dev BA spread is {sd}')
    print(f'Min BA spread is {mini}')
    print(f'Max BA spread is {maxi}')

#=============================================================================
# Extract BA spread (Every second, in calendar time)

# Need session times
begin_end_sessions = []
for i in range(begin_session, end_session+1):
    temp_sessiontimes = getsessiontimes(name, i)
    begin_end_sessions.append(temp_sessiontimes)

# Check: print out the min_time and max_time (parameters) and the list of begin and end times for all sessions
print(min_time)
print(begin_end_sessions)
print(max_time)
# Convert to array
Abegin_end_sessions = np.array(begin_end_sessions)
# Save array
np.save('B_E_sessions', Abegin_end_sessions)

tradetime_exact = []
BAspreadALL_exact = []
sessions_exact = []
for t in range(int(min_time), int(max_time)):
    time_t = t
    # determine whether the time t is fake or not; fake times are those ending on 60...99 (e.g., ****62)
    # or with middle digits 60...99 (e.g., **71**). If fake, skipe
    if 60 <= int(time_t % 100) <= 99:
        # do nothing
        pass
    elif 60 <= int((time_t % 10000) / 100) <= 99:
        # do nothing
        pass
    else:
        # determine session
        Awhich_session = np.where((Abegin_end_sessions[:, 0]-time_t <= 0) == (Abegin_end_sessions[:, 1]-time_t >= 0))
        which_session = np.array(Awhich_session).tolist()
        if which_session[0] != []:
            session_t = which_session[0][0] + begin_session
            [BA, bb, bs] = getbookandBAspread(name, time_t, session_t, mark)
        # REMARK: This prints times and session numbers when the bid ask spread is found to be negative (it will
        # also print the value of the bid ask spread)
            # Convert time to seconds
            convert_time = (60 * 60) * int(time_t / 10000) + 60 * int((time_t % 10000) / 100) + int(time_t % 100)
            tradetime_exact.append(convert_time)
            BAspreadALL_exact.append(BA)
            sessions_exact.append(session_t)

plt.figure()
ABAspreadALL_exact = np.array(BAspreadALL_exact)
NoBAspread = (lambda x: x<0)(ABAspreadALL_exact)
plt.scatter(tradetime_exact, BAspreadALL_exact)
plt.scatter(tradetime_exact, BAspreadALL_exact, c=NoBAspread, cmap="Set1")
plt.title("B/A Spread [Experiment 1]")
plt.ylabel("Spread (Cents)")
plt.xlabel("Time (Seconds)")
plt.show()

# Save output
BA_second = pd.DataFrame(
    {
        "time": tradetime_exact,
        "bid_ask": BAspreadALL_exact,
        "round": sessions_exact,
    }
)
BA_second.to_csv('save_BA_second.csv')