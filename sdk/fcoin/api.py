# -- coding: UTF-8 --

import hmac
import hashlib
import logging
import requests
import time
import base64
from config.coin import *


class FCoin():

    def __init__(self, base_url='https://api.fcoin.com/v2/'):
        self.base_url = base_url
        self.key = None
        self.secret = None

    def auth(self, key, secret):
        self.key = bytes(key, 'utf-8')
        self.secret = bytes(secret, 'utf-8')

    #公共接口不需要加密
    def public_request(self, method, api_url, **payload):
        """request public url"""
        r_url = self.base_url + api_url
        try:
            r = requests.request(method, r_url, params=payload, timeout=3)
            r.raise_for_status()
            if r.status_code == 200:
                return r.json()
        except requests.exceptions.HTTPError as err:
            logging.info(err)
        return None

    #签名
    def get_signed(self, sig_str):
        """signed params use sha512"""
        sig_str = base64.b64encode(sig_str)
        signature = base64.b64encode(hmac.new(self.secret, sig_str, digestmod=hashlib.sha1).digest())
        return signature

    #需要签名接口
    def signed_request(self, method, api_url, **payload):
        timestamp = str(int(time.time() * 1000))
        logging.info("请求url:{}-请求时间：{}".format(api_url, timestamp))
        """request a signed url"""
        param = ''
        if payload:
            sort_pay = sorted(payload.items())
            # sort_pay.sort()
            for k in sort_pay:
                param += '&' + str(k[0]) + '=' + str(k[1])
            param = param.lstrip('&')
        full_url = self.base_url + api_url
        sig_str = ''
        if method == 'GET':
            if param:
                full_url = full_url + '?' + param
            sig_str = method + full_url + timestamp
        elif method == 'POST':
            sig_str = method + full_url + timestamp + param

        signature = self.get_signed(bytes(sig_str, 'utf-8'))

        headers = {
            'FC-ACCESS-KEY': self.key,
            'FC-ACCESS-SIGNATURE': signature,
            'FC-ACCESS-TIMESTAMP': timestamp
        }
        r = {"r":"result"}

        try:
            r = requests.request(method, full_url, headers=headers, json=payload, timeout=6)
            r.raise_for_status()
            if r.status_code == 200:
                return r.json()
            else:
                logging.info(r.text)
        except requests.exceptions.HTTPError as err:
            logging.info(err)
            logging.info(r.text)
        return None

    #获取服务器时间
    def get_server_time(self):
        """Get server time"""
        return self.public_request('GET', '/public/server-time')['data']

    def get_currencies(self):
        """get all currencies"""
        return self.public_request('GET', '/public/currencies')['data']

    #获取所有的symbol
    def get_symbols(self):
        """get all symbols"""
        result = self.public_request('GET', '/public/symbols')
        if "data" in result:
            return result['data']
        return []
    #获取ticker信息
    def get_market_ticker(self, symbol):
        """get market ticker"""
        return self.public_request('GET', 'market/ticker/{symbol}'.format(symbol=symbol))

    #获取市场深度
    def get_market_depth(self, level, symbol):
        """get market depth"""
        return self.public_request('GET', 'market/depth/{level}/{symbol}'.format(level=level, symbol=symbol))

    '''
     选择最近20个的吧
    '''
    # 获取最近的交易
    def get_trades(self, symbol):
        """get detail trade"""
        return self.public_request('GET', 'market/trades/{symbol}?limit=10'.format(symbol=symbol))

    # 查你账户里有多钱
    def get_balance(self):
        """get user balance"""
        return self.signed_request('GET', 'accounts/balance')

    # 查某个币种的余额是否够
    def get_coin_balance(self, symbol):
        try:
            coin_map = zip([coin['currency'] for coin in self.get_balance()['data']],
                           [coin['balance'] for coin in self.get_balance()['data']])
            return (dict(coin_map))[symbol]
        except:
            return 0

    # 查询某个币获取最低币价
    def get_coin_price_min(self, symbol):
        try:
            price = [coin['price'] for coin in self.get_trades(symbol)['data']]
            '''
             获取最低币价，接口目前只返回10个，为了快速交易
            '''
            price = sum(price) / 10
            return price
        except:
            return 0

    # 查询某个币价格,考虑中位数卖
    def get_coin_price_max(self, symbol):
        try:
            price = [coin['price'] for coin in self.get_trades(symbol)['data']]
            '''
             获取最低币价，接口目前只返回10个，为了快速交易
            '''
            price = sum(price) / 10
            return price
        except:
            return 0

    # 查询某个币数量
    def get_coin_amount_max(self, symbol):
        try:
            amount = [coin['amount'] for coin in self.get_trades(symbol)['data']]
            '''
            获取最低币价，接口目前只返回一个
            '''
            return min(amount)
        except:
            return 0

    # 查询某个币最少数量
    def get_coin_amount_min(self, symbol):
        try:
            amount = [coin['amount'] for coin in self.get_trades(symbol)['data']]
            '''
            获取最低币价，接口目前只返回一个
            '''
            return min(amount)
        except:
            return 0

    #订单列表
    def list_orders(self, **payload):
        """get orders"""
        return self.signed_request('GET', 'orders', **payload)

    def create_order(self, **payload):
        """create order"""
        return self.signed_request('POST', 'orders', **payload)

    '''
    price是四位小数
    amount是两位小数
    '''

    def buy(self, symbol, price, amount, type='limit'):
        if DEBUG == 1:
            logging.info("【DEBUG】【买单】价格：{}数量：{}".format(price, amount))
            return None
        """buy someting"""
        if type == 'market':
            return self.create_order(symbol=symbol, side='buy', amount=str(amount), type=type)
        return self.create_order(symbol=symbol, side='buy', price=str(price), amount=str(amount), type=type)

    def sell(self, symbol, price, amount, type='limit'):
        if DEBUG == 1:
            logging.info("【DEBUG】【卖单】价格：{}数量：{}".format(price, amount))
            return None
        try:
            if type == 'market':
                return self.create_order(symbol=symbol, side='sell', amount=str(amount), type=type)
            return self.create_order(symbol=symbol, side='sell', price=str(price), amount=str(amount), type=type)
        except:
            logging.info("【卖单报错】")
            return None

    def get_order(self, order_id):
        """get specfic order"""
        return self.signed_request('GET', 'orders/{order_id}'.format(order_id=order_id))

    def cancel_order(self, order_id):
        if DEBUG == 1:
            logging.info("【DEBUG】【取消订单】orderID：{}".format(order_id))
            return None
        """cancel specfic order"""
        return self.signed_request('POST', 'orders/{order_id}/submit-cancel'.format(order_id=order_id))

    def order_result(self, order_id):
        """check order result"""
        return self.signed_request('GET', 'orders/{order_id}/match-results'.format(order_id=order_id))

    def get_candle(self, resolution, symbol, **payload):
        """get candle data"""
        return self.public_request('GET',
                                   'market/candles/{resolution}/{symbol}'.format(resolution=resolution, symbol=symbol),
                                   **payload)