from urllib.parse import urlencode
import requests
import json
import re
from decimal import Decimal
import os
from dotenv import load_dotenv
import hmac
import hashlib


class TradingView:
    def __init__(self, reqData) -> None:
        load_dotenv()
        if reqData.get("PASSWORD"):
            if self.passwordVerify(reqData["PASSWORD"]):
                self.defData(reqData)
            else:
                raise {"code": "error", "message": "Nice try"}
        else:
            raise {"code": "error", "message": "Password Empty"}

    def passwordVerify(self, password):
        if password == os.getenv("TRADINGVIEW_PASSWD"):
            return True
        else:
            return False

    def defData(self, reqData):
        self.total_order = reqData["TOTAL_ORDER"]
        ticker = re.search(r"([A-Z]{2,})(?:_|)(USDT)(?:PERP|)", reqData["TICKER"])
        self.symbol = ticker.group(1) + ticker.group(2)
        # roundC = len(str(reqData["ORDER_PRICE"]).split(".")[1])
        self.side = reqData["SIDE"].upper()
        self.orderPrice = reqData["ORDER_PRICE"]
        self.limitPrice = reqData["LIMIT_PRICE"]
        self.stopPrice = reqData["STOP_PRICE"]
        self.lever = reqData["LEVER"]
        self.orderPerc = Decimal(str(reqData["ORDER_PERC"]))
        self.orderTime = reqData["ORDER_TIME"]


class Binance(TradingView):
    def __init__(self, reqData) -> None:
        TradingView.__init__(self, reqData)
        self.getMinTick()
        apikey = os.getenv("BINANCE_TOEKN")

        # servertime = self.requestGet("https://data.binance.com/api/v3/time")["serverTime"]
        # self.timeStamp = servertime
        self.timeStamp = self.orderTime

        self.headers = {"X-MBX-APIKEY": apikey}

    def getAccountInfo(self):
        endPoint = "/fapi/v2/account"
        accountInfo = self.requestGetPrivate(endPoint, self.getSignature())
        if "respError" in accountInfo:
            return accountInfo

        marginAva = Decimal(str(accountInfo["availableBalance"]))

        self.positionDatas = self.formatPositionDatas(accountInfo["positions"])
        tradingCount = self.positionDatas["tradingCount"]

        if self.total_order - tradingCount >= 1:
            self.perAmount = Decimal(str(round(marginAva / (self.total_order - tradingCount) * self.orderPerc / self.orderPrice * self.lever, 2)))
            # self.perAmount = Decimal(
            #     str((marginAva - self.balance * Decimal(str(0.2))) / (self.total_order - tradingCount) * self.orderPerc)
            # )
        else:
            return {"respError": {"code": "error", "message": "TradingCount too much."}}

        # if self.perAmount < 0.1:
        #     return {"respError": {"code": "error", "message": "Balance not enough."}}
        return accountInfo
        # self.balance = Decimal(str(accountInfo["totalMarginBalance"]))

    def getMinTick(self):
        endPoint = "/fapi/v1/ticker/price"
        params = {"symbol": self.symbol}
        price = self.requestGet(endPoint, params)["price"]
        minTick = len(str(price).split(".")[1])
        self.orderPrice = Decimal(str(round(self.orderPrice, minTick)))
        self.limitPrice = Decimal(str(round(self.limitPrice, minTick)))
        self.stopPrice = Decimal(str(round(self.stopPrice, minTick)))

    def formatPositionDatas(self, positions):
        datas = {}
        count = 0
        for position in positions:
            if position["initialMargin"] != "0":
                count = count + 1
            symbol = position["symbol"]
            datas[symbol] = position
        datas["tradingCount"] = count
        return datas

    def requestGet(self, url, params={}):
        r = requests.get(url="https://testnet.binancefuture.com/" + url, params=params)
        if r.status_code != 200:
            return {"respError": r.json()}
        else:
            response = r.json()
            return response

    def requestGetPrivate(self, url, signature):
        r = requests.get(url="https://testnet.binancefuture.com/" + url, headers=self.headers, params=signature)
        if r.status_code != 200:
            return {"respError": r.json()}
        else:
            response = r.json()
            return response

    def requestPost(self, url, params, signature):
        params.update(signature)
        r = requests.post(url="https://testnet.binancefuture.com/" + url, headers=self.headers, data=params)
        if r.status_code != 200:
            return {"respError": r.json()}
        else:
            response = r.json()
            return response

    def setMarginType(self):
        if self.positionDatas[self.symbol]["isolated"] == True:
            params = {"symbol": self.symbol, "marginType": "CROSSED"}
            endPoint = "/fapi/v1/marginType"
            response = self.requestPost(endPoint, params, self.getSignature(params))
            print("setMarginType", response)
        else:
            print("setMarginType", "Nothing to change")

    def setLever(self):
        if self.positionDatas[self.symbol]["leverage"] != str(self.lever):
            params = {"symbol": self.symbol, "leverage": self.lever}
            endPoint = "/fapi/v1/leverage"
            response = self.requestPost(endPoint, params, self.getSignature(params))
            print("setLever", response)
        else:
            print("setLever", "Nothing to change")

    def getSignature(self, params={}):
        secret = os.getenv("BINANCE_SECRET")
        if params:
            params["timestamp"] = self.timeStamp
            params = urlencode(params)
        else:
            params = urlencode(
                {
                    "timestamp": self.timeStamp,
                }
            )
        hashedsig = hmac.new(secret.encode("utf-8"), params.encode("utf-8"), hashlib.sha256).hexdigest()
        signature = {
            "timestamp": self.timeStamp,
            "signature": hashedsig,
        }
        return signature

    def putOrder(self):
        self.setMarginType()
        self.setLever()

        if self.side == "BUY":
            limitSide = "SELL"
            stopSide = "SELL"
        elif self.side == "SELL":
            limitSide = "BUY"
            stopSide = "BUY"
        else:
            return {"respError": {"code": "error", "message": "It's close."}}

        orderData = [
            {
                "symbol": self.symbol,
                "side": self.side,
                "positionSide": "BOTH",
                "type": "LIMIT",
                "quantity": str(self.perAmount),
                "price": str(self.orderPrice),
                "timeInForce": "GTC",
            },
            {
                "symbol": self.symbol,
                "side": limitSide,
                "positionSide": "BOTH",
                "type": "TAKE_PROFIT",
                "quantity": str(self.perAmount),
                "price": str(self.limitPrice),
                "stopPrice": str(self.limitPrice),
                "timeInForce": "GTC",
            },
            {
                "symbol": self.symbol,
                "side": stopSide,
                "positionSide": "BOTH",
                "type": "STOP",
                "quantity": str(self.perAmount),
                "price": str(self.stopPrice),
                "stopPrice": str(self.stopPrice),
                "timeInForce": "GTC",
            },
        ]
        params = {"batchOrders": json.dumps(orderData)}
        endPoint = "/fapi/v1/batchOrders"
        orderResp = self.requestPost(endPoint, params, self.getSignature(params))
        if "respError" in orderResp:
            return orderResp
        return orderResp
