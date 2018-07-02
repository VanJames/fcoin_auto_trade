#!-*-coding:utf-8 -*-

#@TIME    : 2018/6/23/0030 15:18

#@Author  : Fanxu
import argparse
import json
import logging
import math
import os
import time
from sdk.fcoin.api import FCoin
from sdk.fcoin.balance import Balance
from collections import defaultdict
from config.coin import *


class Robot:

    def __init__(self,option):
        self.option = option
        self.fcoin = FCoin()
        self.fcoin.auth(FCOIN_API_KEY, FCOIN_SECRET_KEY)
        self.symbol = option.symbol + option.base_symbol
        #价格小数点 位数
        self.price_decimal = 0
        #数量小数点位数
        self.amount_decimal = 0
        #买价
        self.buy_price = 0.00
        #挂单盈利卖价
        self.sell_price = 0.00
        self.symbols = {}
        #余额
        self.dic_balance = None

    def initSymbol(self):
        symbols = self.fcoin.get_symbols()
        for symbol in symbols:
            self.symbols[symbol['name']] = symbol
        self.amount_decimal = self.symbols[self.symbol]['amount_decimal']
        self.price_decimal = self.symbols[self.symbol]['price_decimal']
        logging.info("最小金额小数点：{}最小投资数量小数点：{}".format(self.price_decimal,self.amount_decimal))


    def init(self):
        self.dic_balance = None

    def get_all_order(self):
        #拿取所有的订单
        list = self.fcoin.list_orders(symbol=self.symbol,states='submitted')
        if not list or "data" not in list:
            return None
        submit_order_list = list['data']

    def get_all_balance(self):
        #拿取账户和代币余额
        dic_blance = defaultdict(lambda: None)
        data = self.fcoin.get_balance()
        if not data or "data" not in data:
            return None
        if data:
            for item in data['data']:
                dic_blance[item['currency']] = Balance( float(item['available']) , float(item['frozen']) ,float(item['balance']) )

        self.dic_balance = dic_blance
        symbol = self.dic_balance[self.option.symbol]

        baseSymbol = self.dic_balance[self.option.base_symbol]
        logging.info("{}账户余额:{},{}代币余额:{}".format(self.option.base_symbol , baseSymbol.balance , self.option.symbol , symbol.balance))

    def digits(self, num, digit):
        site = pow(10, digit)
        tmp = num * site
        tmp = math.floor(tmp) / site
        return tmp

    #获取挂单信息
    def get_depth(self):
        list = self.fcoin.get_market_depth("L20",self.symbol)
        if not list or "data" not in list:
            return None
        asks = list['data']['asks']
        bids = list['data']['bids']

        if asks[0] > bids[0]:
           self.buy_price = bids[0]
           self.sell_price = asks[0]
        else:
           self.buy_price = asks[0]
           self.sell_price = bids[0]
        # self.buy_price = self.sell_price = bids[0]
        logging.info("建议买价：{} 建议卖价：{}".format(self.buy_price,self.sell_price))

    def sell_order(self,price):
        self.get_depth()
        amount = self.digits(self.dic_balance[self.option.symbol].available,self.amount_decimal)
        if float(self.sell_price) >= float(price) or (price-self.sell_price) / price > 0.08:
            price = self.sell_price + self.option.profit + self.option.fee
            price = self.digits(price,self.price_decimal)
        else:
            #跌了 需要通过购买弥补损失 1元买了2个 跌到 0.5元 则 买0.5 买 2 个 成本 3 ／ 4 0.75
            self.buy_order()
            return
        try_times = 0
        #盈利单挂3次
        while try_times < 3 :
            logging.info('【卖单】{}价格：{}-数量：{}'.format(self.symbol,price, amount ))
            data = self.fcoin.sell(self.symbol, price, amount)
            if data and "data" in data :
                db = self.get_json_data()
                db['sell_order_id'] = data['data']
                db['sell_order_time'] = int(time.time())
                db['buy_order_id'] = 0
                db['buy_order_time'] = 0
                self.set_json_data(db)
                logging.info('挂卖单成功！{}'.format(data))
                self.check_sell_order(data['data'],int(time.time()))
                break
            try_times += 1
            time.sleep(1)

    def check_buy_order(self,orderId,start):
        while True:
            time.sleep(2)
            result = self.fcoin.get_order(orderId)
            if result and "data" in result:
                logging.info("【订单状态】：{}".format(result["data"]["state"]))
                #看挂单状态
                if result["data"]["state"] == "filled" or result["data"]["state"] == "partial_canceled":
                    #如果成交
                    db = self.get_json_data()
                    self.get_all_balance()
                    db['balance'] = self.dic_balance[self.option.symbol].balance
                    price = count = 0.00
                    if 'price' in db:
                        price = float(db['price'])
                    if 'amount' in db:
                        count = float(db['amount'])
                    #成本价
                    db['price'] = (price*count+float(result['data']['price'])*float(result['data']['amount']))/(count+float(result['data']['amount']))
                    #数量
                    db['amount'] = count+float(result['data']['amount'])
                    self.set_json_data(db)
                    self.sell_order(db['price'])

                    break
                #看挂单状态
                if result["data"]["state"] == "canceled":
                    #如果取消
                    db = self.get_json_data()
                    db['buy_order_id'] = 0
                    db['buy_order_time'] = 0
                    self.set_json_data(db)
                    break
                end = int( time.time() )
                if end - start > TIMEOUT :
                    #10s取消订单
                    r = self.fcoin.cancel_order(orderId)
                    if r and "data" in r:
                        db = self.get_json_data()
                        db['buy_order_id'] = 0
                        db['buy_order_time'] = 0
                        self.set_json_data(db)
                        logging.info("【取消订单成功】orderID：{}".format(orderId))
                        break

    #检测卖单
    def check_sell_order(self,orderId,start):
        while True:
            time.sleep(2)
            result = self.fcoin.get_order(orderId)
            if result and "data" in result:
                logging.info("【订单状态】：{}".format(result["data"]["state"]))
                #看挂单状态
                if result["data"]["state"] == "filled" or result["data"]["state"] == "partial_canceled":
                    #如果成交
                    db = self.get_json_data()
                    db['sell_order_id'] = 0
                    db['sell_order_time'] = 0
                    db['price'] = 0
                    db['amount'] = 0
                    self.set_json_data(db)
                    break
                if result["data"]["state"] == "canceled":
                    #如果成交
                    db = self.get_json_data()
                    db['sell_order_id'] = 0
                    db['sell_order_time'] = 0
                    self.set_json_data(db)
                    break
                end = int( time.time() )
                if end - start > TIMEOUT*3 :
                    self.order = None
                    #180s取消订单
                    r = self.fcoin.cancel_order(orderId)
                    if r and "data" in r:
                        db = self.get_json_data()
                        db['sell_order_id'] = 0
                        db['sell_order_time'] = 0
                        self.set_json_data(db)
                        logging.info("取消订单成功{}".format(orderId))
                        break

    def buy_order(self):
        amount = self.digits(self.dic_balance[self.option.base_symbol].available / self.buy_price * self.option.rate, self.amount_decimal)
        logging.info('【买单】{}价格：{}-数量：{}'.format(self.symbol,self.buy_price,amount))
        data = self.fcoin.buy(self.symbol, self.buy_price, amount)
        if data and "data" in data :
            db = self.get_json_data()
            #订单id
            db['buy_order_id'] = data["data"]
            #时间
            start = int( time.time() )
            db['buy_order_time'] = start
            logging.info('买单成功！{}'.format(data))
            self.set_json_data(db)
            orderId = data["data"]
            self.check_buy_order(orderId,start)


    def get_json_data(self):
        filename = "data/{}{}.json".format(self.option.base_symbol,self.option.symbol)
        if not os.path.exists(filename) :
            return {}
        f = open(filename, encoding='utf-8')
        data = {}
        if f:
            data = json.load(f)
        return data

    def set_json_data(self,data):
        with open("data/{}{}.json".format(self.option.base_symbol,self.option.symbol),"w") as f:
            json.dump(data,f)

    def process(self):
        self.init()
        #查看所有持仓
        self.get_all_balance()

        self.get_depth()

        db = self.get_json_data()
        print(db)
        if 'buy_order_id' in db and db['buy_order_id']:
            #检测买单信息
            self.check_buy_order(db['buy_order_id'],db['buy_order_time'])
            return

        if ('sell_order_id' in db and db['sell_order_id'] ) or ( 'price' in db and float(db['price']) >0.00 ):
            #检测卖单信息
            if db['sell_order_id']:
                self.check_sell_order(db['sell_order_id'],db['sell_order_time'])
            else :
                self.sell_order(db['price'])
            return

        self.buy_order()

    def loop(self):
        while True:
            try:
                logging.info("程序启动")
                self.process()
                time.sleep(5)
            except Exception as err:
                time.sleep(10)
                logging.error(err)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-bs', '--base_symbol', type=str, default='usdt',
                        help='symbol') #基础 货币
    parser.add_argument('-s', '--symbol', type=str, default='etc',
                        help='symbol') #需要交易的货币
    parser.add_argument('-r', '--rate', type=float, default=0.2,
                        help='rate must grater than 0') #投入账户的百分比 购买
    parser.add_argument('-f', '--fee', type=float, default=0.0001,
                        help='fee') #币种交易的手续费
    parser.add_argument('-p', '--profit', type=float, default=0.0001,
                        help='profit') #盈利点
    parser.add_argument('-m', '--min', type=float, default=0.0001,
                        help='min price') #最小金额
    option = parser.parse_args()
    try:
        log_filename = "data/{}{}.log".format(option.base_symbol,option.symbol)
        logging.basicConfig(level=logging.INFO,
                    filename=log_filename,
                    format='[%(asctime)s] %(levelname)s [%(funcName)s: %(filename)s, %(lineno)d] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filemode='a')
        run = Robot(option)

        run.initSymbol()
        run.loop()

    except KeyboardInterrupt:
        logging.info("ctrl+c exit")
