import os
import os.path
import decimal as D
import pandas as pd
import config
from termcolor import colored
import logging


def printHeader():
    os.system('cls' if os.name=='nt' else 'clear')
    print (colored(".oO(Binance Trading Bot)","yellow"))
    print (colored("-> Last Execution: " + pd.Timestamp.now().strftime("%m/%d/%Y, %H:%M:%S"),'red'))

def main():
    printHeader()
    if os.path.isfile(config.CHECKPOINT_FILE):
        global DEFAULT_COIN
        # if file exists return dataframe for file
        TDF = pd.read_csv(config.CHECKPOINT_FILE, index_col = 0, dtype={'STATUS': int,'COUNT':int}, converters={'BID': D.Decimal,'ASK': D.Decimal,'TSELL': D.Decimal,'RSELL': D.Decimal,'RBUY': D.Decimal,'TBUY': D.Decimal,'ALLOCATION': D.Decimal,'FREE': D.Decimal,'LOCKED': D.Decimal,'PROFIT': D.Decimal})
        print(TDF)
        sResult = input (" - Refresh")
        main()
    else:
        print (config.CHECKPOINT_FILE + " Not Found")


if __name__ == '__main__':
    main ()
