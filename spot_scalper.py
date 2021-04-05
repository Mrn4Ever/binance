import os
import os.path
import pandas as pd
import hmac
import hashlib
import requests
import json
import sched
import time
import math
from termcolor import colored
import decimal as D
from decimal import *
import config
import logging

getcontext().prec = 8
logging.basicConfig(format='Date-Time : %(asctime)s -  %(levelname)s : %(message)s', filename="debug.log", level=logging.DEBUG)


#Trading Info
ALLOCATION   = [Decimal(0)]  * len(config.DEFAULT_COIN)
FREE         = [Decimal(0)]  * len(config.DEFAULT_COIN)
LOCKED       = [Decimal(0)]  * len(config.DEFAULT_COIN)
PROFIT       = [Decimal(0)]  * len(config.DEFAULT_COIN)
COUNT        = [0] * len(config.DEFAULT_COIN)
BID          = [Decimal(0)]  * len(config.DEFAULT_COIN)
BID_MOVE     = ["="]* len(config.DEFAULT_COIN)
ASK          = [Decimal(0)]  * len(config.DEFAULT_COIN)
ASK_MOVE     = ["="]* len(config.DEFAULT_COIN)
RBUY         = [Decimal(0)]  * len(config.DEFAULT_COIN)
TBUY         = [Decimal(0)]  * len(config.DEFAULT_COIN)
RSELL        = [Decimal(0)]  * len(config.DEFAULT_COIN)
TSELL        = [Decimal(0)]  * len(config.DEFAULT_COIN)
STATUS       = [Decimal(0)]  * len(config.DEFAULT_COIN)
COMMENT      = [""] * len(config.DEFAULT_COIN)
STEP_SIZE    = [Decimal(0)]  * len(config.DEFAULT_COIN)


def main ():
    # clear and  write header
    printHeader()

    # input Continue Or Relaunch
    inputContinueAction ()

    # read step size for each chosen pair
    getExchangeInfo()

    # initialize balance dataframe
    BDF = initializeBlanceDataframe()

    # initialize trading dataframe
    TDF = initializeTradingDataframe()

    # refresg pair quantities
    RefreshQuantities (TDF)

    # start trading bot
    while (1 == 1):
        calculate(TDF, BDF)

    return

def inputContinueAction ():
    # input Continue Or Relaunch
    print("* Available Actions")
    print(f"*  1 - CONTINUE TRADING FROM LAST CHEKOUT")
    print(f"*  2 - RESET FROM ZERO SELL {config.DEFAULT_COIN} to {config.DEFAULT_BASE}")
    print(f"*  3 - RESET WITHOUT SELLING")

    sContinue = input ("Select Action Default (1) :")
    if (sContinue == "" or sContinue == "1"):
        print (" - [OK] - CONTINUE TRADING FROM LAST CHEKOUT")
    elif (sContinue == "2"):
        print (colored(f"[WARNING] - THE BOT WILL SELL {config.DEFAULT_COIN} to {config.DEFAULT_BASE}","red"))
        for coin in config.DEFAULT_COIN:
            symbol = coin + config.DEFAULT_BASE
            free, locked = getQuantity (coin)
            if (free > 0):
                print (f"SELL {free} OF {symbol}")
                inputConfirmSellingAction (symbol,coin)
        if os.path.exists(config.CHECKPOINT_FILE):
            os.remove(config.CHECKPOINT_FILE)
    elif (sContinue == "3"):
        if os.path.exists(config.CHECKPOINT_FILE):
            os.remove(config.CHECKPOINT_FILE)
    else:
        inputContinueAction()

def inputConfirmSellingAction (symbol,coin):
    sConfirmSell = input ("Confirm Selling (Y/N) default (N):")
    if (sConfirmSell== "" or sConfirmSell =="N"):
        print (colored(f"[IGNORED]","yellow"))
    elif sConfirmSell == "Y":
        if (ClosePosition(coin, config.DEFAULT_BASE)):
            print (colored(f"SELLING {coin} OK","green"))
        else:
            print (colored(f"SELLING {coin} NOK","red"))
    else:
        inputConfirmSellingAction (symbol,coin)


def initializeBlanceDataframe():
    if os.path.isfile(config.BALANCE_FILE):
        # if file exists return dataframe for file
        BDF = pd.read_csv(config.BALANCE_FILE, index_col = 0)
        return BDF
    else:
        # if file doesn't exists initlize new dataframe
        data  = {'BALANCE':[getBalance()]}
        index = [pd.Timestamp.now().strftime("%m/%d/%Y, %H:%M:%S")]
        BDF = pd.DataFrame(data=data, index=index)
        return BDF

def initializeTradingDataframe():
    if os.path.isfile(config.CHECKPOINT_FILE):
        # if file exists return dataframe for file
        TDF = pd.read_csv(config.CHECKPOINT_FILE, index_col = 0, dtype={'STATUS': int,'COUNT':int}, converters={'BID': D.Decimal,'ASK': D.Decimal,'TSELL': D.Decimal,'RSELL': D.Decimal,'RBUY': D.Decimal,'TBUY': D.Decimal,'ALLOCATION': D.Decimal,'FREE': D.Decimal,'LOCKED': D.Decimal,'PROFIT': D.Decimal})
        TDF.loc[TDF['STATUS'] == 1, 'STATUS'] = 0
        TDF.loc[TDF['STATUS'] == 3, 'STATUS'] = 2
        print (TDF)
        return TDF
    else:
        # initialize allocation
        free, locked = getQuantity (config.DEFAULT_BASE)
        print (" -> Free   {}: {}".format(config.DEFAULT_BASE,free))
        print (" -> Locked {}: {}".format(config.DEFAULT_BASE,locked))
        generalAllocation = input("Enter Equity to Trade (Max: {}):".format(free))
        if (generalAllocation == ""):
            generalAllocation = 0
        generalAllocation = Decimal(generalAllocation)
        ALLOCATION   = [generalAllocation/Decimal(len(config.DEFAULT_COIN))]  * len(config.DEFAULT_COIN)
        # if file doesn't exists initlize new dataframe
        tradingData = {
                        'BID':BID,
                        'BID_MOVE':BID_MOVE,
                        'ASK':ASK,
                        'ASK_MOVE':ASK_MOVE,
                        'TSELL':TSELL,
                        'RSELL':RSELL,
                        'RBUY':RBUY,
                        'TBUY':TBUY,
                        'STATUS':STATUS,
                        'COMMENT':COMMENT,
                        'ALLOCATION':ALLOCATION,
                        'FREE':FREE,
                        'LOCKED':LOCKED,
                        'PROFIT':PROFIT,
                        'COUNT':COUNT
                      }
        index = []
        for coin in config.DEFAULT_COIN:
            symbol = coin + config.DEFAULT_BASE
            index.append(symbol)
        TDF = pd.DataFrame(data=tradingData, index=index)
        return TDF

def calculate (TDF, BDF):
    # get Ticker from Bianance
    sBookTicker = getBookTicker()
    oBookTicker = json.loads(sBookTicker)
    for ticker in oBookTicker:
        symbol   = ticker['symbol']
        for coin in config.DEFAULT_COIN:
            if (symbol == coin + config.DEFAULT_BASE):
                if (Decimal(ticker['bidPrice']) > TDF.loc[symbol,'BID']):
                    TDF.loc[symbol,'BID_MOVE'] = "+"
                elif (Decimal(ticker['bidPrice']) < TDF.loc[symbol,'BID']):
                    TDF.loc[symbol,'BID_MOVE'] = "-"
                else:
                    TDF.loc[symbol,'BID_MOVE'] = "="

                TDF.loc[symbol,'BID']   = Decimal(ticker['bidPrice'])


                if (Decimal(ticker['askPrice']) > TDF.loc[symbol,'ASK']):
                    TDF.loc[symbol,'ASK_MOVE'] = "+"
                elif (Decimal(ticker['askPrice']) < TDF.loc[symbol,'ASK']):
                    TDF.loc[symbol,'ASK_MOVE'] = "-"
                else:
                    TDF.loc[symbol,'ASK_MOVE'] = "="

                TDF.loc[symbol,'ASK']   = Decimal(ticker['askPrice'])

                TDF.loc[symbol,'PROFIT'] =    TDF.loc[symbol,'BID'] * (TDF.loc[symbol,'FREE'] + TDF.loc[symbol,'LOCKED'])

                break

    #tradingWorkflow
    workflow (TDF, BDF)

    #print Overview
    printHeader()

    tdf_string = TDF.copy()
    bdf_string = BDF.copy()

    ADF = pd.DataFrame(data=[STEP_SIZE], index=["STEP SIZE"], columns=config.DEFAULT_COIN)
    print (colored("[Watched Assets]","green"))
    print (ADF)

    print (colored("[Account INFO]","green"))
    print (bdf_string.tail(1))


    print (colored("[Trading Dashboard]","green"))
    print (tdf_string)


    #Save Checkpoint
    TDF.to_csv(config.CHECKPOINT_FILE, index=True)


def workflow (TDF, BDF):
    for coin in config.DEFAULT_COIN:
        symbol = coin + config.DEFAULT_BASE
        Status = TDF.loc[symbol,'STATUS']

        if (Status == 0):
            TDF.loc[symbol,'COMMENT'] = "Waiting Opportunity To Buy"
            TDF.loc[symbol,'TSELL']    = Decimal(0)
            TDF.loc[symbol,'RSELL']    = Decimal(0)
            if (TDF.loc[symbol,'ASK_MOVE'] == "+"):
                tempRBUY = TDF.loc[symbol,'ASK'] * Decimal( 1 - config.RBUY_PERCENT/100)
                if (tempRBUY > TDF.loc[symbol,'RBUY']):
                    TDF.loc[symbol,'RBUY']  = tempRBUY
                    TDF.loc[symbol,'TBUY']  = TDF.loc[symbol,'ASK'] * Decimal( 1 - config.TBUY_PERCENT/100)

            elif (TDF.loc[symbol,'ASK'] <= TDF.loc[symbol,'RBUY']):
                TDF.loc[symbol,'COMMENT'] = "[Good News] - Price is Under the Trailing Buy Price"
                TDF.loc[symbol,'STATUS']  = 1
                RefreshQuantities (TDF)

        elif (Status == 1):
            TDF.loc[symbol,'COMMENT'] = "Waiting Trailing Opportunity To Buy"
            TDF.loc[symbol,'TSELL']    = Decimal(0)
            TDF.loc[symbol,'RSELL']    = Decimal(0)
            if (TDF.loc[symbol,'ASK'] <= TDF.loc[symbol,'TBUY']):
                TDF.loc[symbol,'COMMENT'] = "[Good News] - Price is Still Going Under the Trailing Buy Price"
                tempGap                   = TDF.loc[symbol,'RBUY'] - TDF.loc[symbol,'TBUY']
                TDF.loc[symbol,'TBUY']    = TDF.loc[symbol,'ASK']
                TDF.loc[symbol,'RBUY']    = TDF.loc[symbol,'TBUY'] + tempGap
            elif (TDF.loc[symbol,'ASK'] >= TDF.loc[symbol,'RBUY']):
                TDF.loc[symbol,'COMMENT'] = "[Good News] - The Perfect Moment To Buy"
                RefreshQuantities (TDF)
                if (OpenPosition(TDF, coin, config.DEFAULT_BASE)):
                    TDF.loc[symbol,'TSELL'] = TDF.loc[symbol,'BID'] * Decimal( 1 + config.TSELL_PERCENT/100)
                    TDF.loc[symbol,'RSELL'] = TDF.loc[symbol,'BID'] * Decimal( 1 + config.RSELL_PERCENT/100)
                    TDF.loc[symbol,'ALLOCATION']    = Decimal(0)
                    TDF.loc[symbol,'COUNT']         = TDF.loc[symbol,'COUNT'] + 1
                    TDF.loc[symbol,'STATUS']        = 2
                    RefreshQuantities(TDF)
                    BDF.loc[ pd.Timestamp.now().strftime("%m/%d/%Y, %H:%M:%S") , 'BALANCE'] = getBalance()
                    BDF.to_csv(config.BALANCE_FILE, index=True)

        elif (Status == 2):
            TDF.loc[symbol,'COMMENT'] = "Waiting Opportunity To Sell"
            TDF.loc[symbol,'TBUY']    = Decimal(0)
            TDF.loc[symbol,'RBUY']    = Decimal(0)
            if (TDF.loc[symbol,'BID'] > TDF.loc[symbol,'TSELL']):
                TDF.loc[symbol,'COMMENT'] = "[Good News] - Price is Above the Trailing Sell Price"
                TDF.loc[symbol,'STATUS']  = 3
                RefreshQuantities (TDF)

        elif (Status == 3):
            TDF.loc[symbol,'COMMENT'] = "Waiting Trailing Opportunity To Sell"
            TDF.loc[symbol,'TBUY']    = Decimal(0)
            TDF.loc[symbol,'RBUY']    = Decimal(0)
            if (TDF.loc[symbol,'BID'] > TDF.loc[symbol,'TSELL']):
                TDF.loc[symbol,'COMMENT'] = "[Good News] - Price is Still Going Above the Trailing Sell Price"
                tempGap                   = TDF.loc[symbol,'TSELL'] - TDF.loc[symbol,'RSELL']
                TDF.loc[symbol,'TSELL']   = TDF.loc[symbol,'BID']
                TDF.loc[symbol,'RSELL']   = TDF.loc[symbol,'TSELL'] - tempGap

            elif (TDF.loc[symbol,'BID'] < TDF.loc[symbol,'RSELL']):
                TDF.loc[symbol,'COMMENT'] = "[Good News] - The Perfect Moment To Sell"
                RefreshQuantities (TDF)
                if (ClosePosition(coin, config.DEFAULT_BASE)):
                    TDF.loc[symbol,'TBUY']          = TDF.loc[symbol,'ASK']  * Decimal( 1 - config.TBUY_PERCENT/100)
                    TDF.loc[symbol,'RBUY']          = TDF.loc[symbol,'ASK']  * Decimal( 1 - config.RBUY_PERCENT/100)
                    TDF.loc[symbol,'ALLOCATION']    = TDF.loc[symbol,'FREE'] * TDF.loc[symbol,'BID']
                    TDF.loc[symbol,'STATUS']        = 0
                    BDF.loc[ pd.Timestamp.now().strftime("%m/%d/%Y, %H:%M:%S") , 'BALANCE'] = getBalance()
                    BDF.to_csv(config.BALANCE_FILE, index=True)
                    RefreshQuantities (TDF)


def printHeader():
    os.system('cls' if os.name=='nt' else 'clear')
    print (colored(".oO(Binance Trading Bot)","yellow"))
    print (colored("-> Last Execution: " + pd.Timestamp.now().strftime("%m/%d/%Y, %H:%M:%S"),'red'))


def getQuantity (coin):
    sAllCoins = getAllCoins()
    oAllCoins = json.loads(sAllCoins)
    for oCoin in oAllCoins:
        coinCode    = oCoin['coin']
        coinName    = oCoin['name']
        coinFree    = Decimal(oCoin['free'])
        coinLocked  = Decimal(oCoin['locked'])
        if (coinCode == coin):
            return coinFree, coinLocked
    return 0, 0

def RefreshQuantities (TDF):
    sAllCoins = getAllCoins()
    oAllCoins = json.loads(sAllCoins)
    for oCoin in oAllCoins:
        coinCode    = oCoin['coin']
        for coin in config.DEFAULT_COIN:
            symbol = coin + config.DEFAULT_BASE
            if (coinCode == coin):
                coinFree    = Decimal(oCoin['free'])
                coinLocked  = Decimal(oCoin['locked'])
                TDF.loc[symbol, 'FREE']   = coinFree
                TDF.loc[symbol, 'LOCKED'] = coinLocked
                break
    return 0, 0

def getBalance ():
    sAllCoins = getAllCoins()
    oAllCoins = json.loads(sAllCoins)

    sBookTicker = getBookTicker()
    oBookTicker = json.loads(sBookTicker)

    balance = Decimal(0)
    for oCoin in oAllCoins:
        coinCode    = oCoin['coin']
        coinFree    = Decimal(oCoin['free'])
        coinLocked  = Decimal(oCoin['locked'])
        coinBalance = coinFree + coinLocked
        if (coinCode == config.DEFAULT_BASE):
            balance = balance + coinBalance
        else:
            if (coinBalance > Decimal(0)):
                symbol = coinCode + config.DEFAULT_BASE
                for ticker in oBookTicker:
                    if (symbol == ticker['symbol']):
                        balance = balance + coinBalance * Decimal(ticker['bidPrice'])
                        break
    return balance

def OpenPosition(TDF, coin, base):
    symbol = coin + base
    allocation   = TDF.loc[symbol,'ALLOCATION']
    free, locked = getQuantity (base)

    if (allocation > free):
        allocation = free

    log (f"Open {symbol} Quantity {allocation}", 1)
    sResult = postOrder(symbol, "BUY", allocation)
    log (sResult,0)
    oResult = json.loads(sResult)

    if ('orderId' in oResult):
        return True

    else:
        log (sResult,0)
        return False


def ClosePosition(coin, base):
    symbol        = coin + base
    index        = config.DEFAULT_COIN.index(coin)
    step_size    = STEP_SIZE [index]
    free, locked = getQuantity (coin)
    rounded_free = round_down(float(free), step_size)

    log (f"Close {symbol} Quantity {rounded_free} Precision {step_size}", 1)
    sResult = postOrder(symbol, "SELL", 0, rounded_free)
    log (sResult,0)
    oResult = json.loads(sResult)
    if ('orderId' in oResult):
        return True
    else:
        log (sResult,0)
        return False




def sendGET(url, bUseKey = False):

    if (bUseKey):
        header = {'X-MBX-APIKEY': config.API_KEY}
        r = requests.get(url, headers = header)
        log (str(r.status_code) + " | " + url + " | SIGNED" , 2)
        return r.text

    else:
        r = requests.get(url)
        log (str(r.status_code) + " | " + url, 2)
        return r.text





def sendPost(url, data, bUseKey = False):

    if (bUseKey):
        header = {'X-MBX-APIKEY': config.API_KEY}
        r = requests.post(url, headers = header, data = data)
        log (str(r.status_code) + " | " + url + " | SIGNED" , 2)
        return r.text

    else:
        r = requests.post(url, data)
        log (str(r.status_code) + " | " + url, 2)
        return r.text



def log (sValue, sLevel):
    if config.DEBUG:
        logging.debug(sValue)



def getTimestamp ():
    result = json.loads(sendGET(config.BASE_URL + config.EP_TIME_SERVER))
    return result['serverTime']


def encode (message):

    signature = hmac.new(bytes(config.API_SECRET , 'latin-1'), msg = bytes(message , 'latin-1'), digestmod = hashlib.sha256).hexdigest().upper()
    return signature



def getStatus():

    url = config.BASE_URL + config.EP_SYSTEM_STATUS
    sResult = sendGET(url)
    oResult = json.loads(sResult)
    if(oResult['status'] == 0):
        log ("Connection Status: {}".format(oResult['msg']), 1)
        return True
    else:
        log ("Connection Status: {}".format(oResult['msg']), 1)
        return False



def getExchangeInfo():
    url = config.BASE_URL + config.EP_EXCHANGE_INFO
    sResult = sendGET(url)
    oResult = json.loads(sResult)
    for oSymbol in oResult['symbols']:
        for coin in config.DEFAULT_COIN:
            symbol = coin + config.DEFAULT_BASE
            if symbol == oSymbol['symbol']:
                index  = config.DEFAULT_COIN.index(coin)
                for oFilter in oSymbol['filters']:
                    if oFilter['filterType'] == "LOT_SIZE":
                         STEP_SIZE[index] = Decimal(oFilter['stepSize'])



def getAllCoins():

    url = config.BASE_URL + config.EP_ALL_COINS + "?[PARAMS]"
    sParams = ""
    sParams = sParams + "timestamp={}".format(getTimestamp())
    sParams = sParams + "&signature=" + encode(message = sParams)

    url = url.replace("[PARAMS]",sParams)
    return sendGET(url = url, bUseKey = True)



def getAccountInfo():

    url = config.BASE_URL + config.EP_ACCOUNT_INFO + "?[PARAMS]"
    sParams = ""
    sParams = sParams + "timestamp={}".format(getTimestamp())
    sParams = sParams + "&signature=" + encode(message = sParams)

    url = url.replace("[PARAMS]",sParams)
    return sendGET(url = url, bUseKey = True)



def getBookTicker():
    url = config.BASE_URL + config.EP_BOOK_TICKER
    return sendGET(url = url)



def postOrder(symbol,side ,price = 0, quantity= 0, type = "MARKET"):

    url = config.BASE_URL + config.EP_ORDER
    sParams = ""
    sParams = sParams + "&symbol={}".format(symbol)
    sParams = sParams + "&side={}".format(side)
    sParams = sParams + "&type={}".format(type)


    if price > 0 :
        sParams = sParams + "&quoteOrderQty={}".format(price)

    if quantity > 0:
        sParams = sParams + "&quantity={}".format(quantity)

    sParams = sParams + "&timestamp={}".format(getTimestamp())

    sParams = sParams + "&signature=" + encode(message = sParams)

    url = url.replace("[PARAMS]",sParams)
    return sendPost(url = url, data = sParams, bUseKey = True)


def round_down(num, step_size):
    digits = math.log10(step_size) if step_size != 0 else 0
    if (digits < 0):
        digits = digits * -1
        factor = 10.0 ** digits
        return math.floor(num * factor) / factor
    else:
        return math.floor(num)

if __name__ == '__main__':
    main ()
