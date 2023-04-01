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
        roundC = len(str(reqData["ORDER_PRICE"]).split(".")[1])
        self.side = reqData["SIDE"].upper()
        self.orderPrice = Decimal(str(round(reqData["ORDER_PRICE"], roundC)))
        self.limitPrice = Decimal(str(round(reqData["LIMIT_PRICE"], roundC)))
        self.stopPrice = Decimal(str(round(reqData["STOP_PRICE"], roundC)))
        self.lever = reqData["LEVER"]
        self.orderPerc = Decimal(str(reqData["ORDER_PERC"]))
        self.orderTime = reqData["ORDER_TIME"]


class Binance(TradingView):
    def __init__(self, reqData) -> None:
        TradingView.__init__(self, reqData)
        apikey = os.getenv("BINANCE_TOEKN")

        # servertime = self.requestGet("https://data.binance.com/api/v3/time")["serverTime"]
        # self.timeStamp = servertime
        self.timeStamp = self.orderTime

        self.headers = {"X-MBX-APIKEY": apikey}

    def getAccountInfo(self):
        accountInfo = self.requestGetPrivate("/fapi/v2/account", self.getSignature())
        if "respError" in accountInfo:
            return accountInfo

        self.marginAva = Decimal(str(accountInfo["availableBalance"]))
        self.tradingCount = self.getTradingCount(accountInfo["positions"])
        if self.total_order - self.tradingCount >= 1:
            self.perAmount = Decimal(str(round(self.marginAva / (self.total_order - self.tradingCount) * self.orderPerc / self.lever, 2)))
            # self.perAmount = Decimal(
            #     str((self.marginAva - self.balance * Decimal(str(0.2))) / (self.total_order - self.tradingCount) * self.orderPerc)
            # )
        else:
            return {"respError": {"code": "error", "message": "TradingCount too much."}}

        if self.perAmount < 1:
            return {"respError": {"code": "error", "message": "Balance not enough."}}

        return accountInfo
        # self.balance = Decimal(str(accountInfo["totalMarginBalance"]))

    def getTradingCount(self, positions):
        count = 0
        for position in positions:
            if position["initialMargin"] != "0":
                count = count + 1
        return count

    def requestGet(self, url):
        r = requests.get(url=url)
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
        params = {"symbol": self.symbol, "marginType": "CROSSED"}
        endPoint = "/fapi/v1/marginType"
        response = self.requestPost(endPoint, params, self.getSignature(params))
        print("setMarginType", response)

    def setLever(self):
        params = {"symbol": self.symbol, "leverage": self.lever}
        endPoint = "/fapi/v1/leverage"
        response = self.requestPost(endPoint, params, self.getSignature(params))
        print("setLever", response)

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
        elif self.side != "SELL":
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
