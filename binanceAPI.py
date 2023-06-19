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
        apikey = os.getenv("BINANCE_TOEKN")
        self.headers = {"X-MBX-APIKEY": apikey}

        self.baseUrl = os.getenv("BINANCE_URL")
        self.servertime = self.requestGet("/fapi/v1/time")["serverTime"]
        self.timeStamp = self.orderTime

    def getAccountInfo(self):
        stepSize = self.getMinTick()

        endPoint = "/fapi/v2/account"
        accountInfo = self.requestGetPrivate(endPoint, self.getSignature(self.servertime))
        if "respError" in accountInfo:
            return accountInfo

        marginAva = Decimal(str(accountInfo["availableBalance"]))
        self.positionDatas = self.formatPositionDatas(accountInfo["positions"])
        tradingCount = self.positionDatas["tradingCount"]

        if self.side != "CLOSE":
            if self.total_order - tradingCount >= 1:
                self.perAmount = Decimal(
                    str(round(marginAva / (self.total_order - tradingCount) * self.orderPerc / self.orderPrice * self.lever, stepSize))
                )
            else:
                return {"respError": {"code": "error", "message": "TradingCount too much."}}
        return accountInfo

    def getMinTick(self):
        endPoint = "/fapi/v1/exchangeInfo"
        info = self.requestGet(endPoint)
        for symbol in info["symbols"]:
            if symbol["symbol"] == self.symbol:
                for filter in symbol["filters"]:
                    if filter["filterType"] == "MARKET_LOT_SIZE":
                        stepSize = filter["stepSize"]
                    elif filter["filterType"] == "PRICE_FILTER":
                        ticksize = filter["tickSize"]
                break
        ticksize = len(str(ticksize).split(".")[1])
        if stepSize != "1":
            stepSize = len(str(stepSize).split(".")[1])
        else:
            stepSize = len(str(stepSize))
        self.orderPrice = Decimal(str(round(self.orderPrice, ticksize)))
        self.limitPrice = Decimal(str(round(self.limitPrice, ticksize)))
        self.stopPrice = Decimal(str(round(self.stopPrice, ticksize)))
        return stepSize

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
        r = requests.get(url=self.baseUrl + url, params=params)
        if r.status_code != 200:
            return {"respError": r.json()}
        else:
            response = r.json()
            return response

    def requestGetPrivate(self, url, signature):
        r = requests.get(url=self.baseUrl + url, headers=self.headers, params=signature)
        if r.status_code != 200:
            return {"respError": r.json()}
        else:
            response = r.json()
            return response

    def requestPost(self, url, params, signature):
        params.update(signature)
        r = requests.post(url=self.baseUrl + url, headers=self.headers, data=params)
        if r.status_code != 200:
            return {"respError": r.json()}
        else:
            response = r.json()
            return response

    def requestDelete(self, url, params, signature):
        params.update(signature)
        r = requests.delete(url=self.baseUrl + url, headers=self.headers, data=params)
        if r.status_code != 200:
            return {"respError": r.json()}
        else:
            response = r.json()
            return response

    def setMarginType(self):
        if self.positionDatas[self.symbol]["isolated"] == True:
            params = {"symbol": self.symbol, "marginType": "CROSSED"}
            endPoint = "/fapi/v1/marginType"
            response = self.requestPost(endPoint, params, self.getSignature(self.servertime, params))
            print("setMarginType", response)
        else:
            print("setMarginType", "Nothing to change")

    def setLever(self):
        if self.positionDatas[self.symbol]["leverage"] != str(self.lever):
            params = {"symbol": self.symbol, "leverage": self.lever}
            endPoint = "/fapi/v1/leverage"
            response = self.requestPost(endPoint, params, self.getSignature(self.servertime, params))
            print("setLever", response)
        else:
            print("setLever", "Nothing to change")

    def getSignature(
        self,
        timeStamp,
        params={},
    ):
        secret = os.getenv("BINANCE_SECRET")
        if params:
            params["timestamp"] = timeStamp
            params = urlencode(params)
        else:
            params = urlencode(
                {
                    "timestamp": timeStamp,
                }
            )
        hashedsig = hmac.new(secret.encode("utf-8"), params.encode("utf-8"), hashlib.sha256).hexdigest()
        signature = {
            "timestamp": timeStamp,
            "signature": hashedsig,
        }
        return signature

    def clearOrders(self):
        params = {"symbol": self.symbol}
        endPoint = "/fapi/v1/allOpenOrders"
        self.requestDelete(endPoint, params, self.getSignature(self.orderTime, params))

    def putOrder(self):
        self.setMarginType()
        self.setLever()
        self.clearOrders()

        if self.side == "BUY":
            limitSide = "SELL"
            stopSide = "SELL"
        elif self.side == "SELL":
            limitSide = "BUY"
            stopSide = "BUY"
        else:
            return {"respError": {"code": "error", "message": "It's close."}}

        orderData = [
            {"symbol": self.symbol, "side": self.side, "positionSide": "BOTH", "type": "MARKET", "quantity": str(self.perAmount)},
            {
                "symbol": self.symbol,
                "side": limitSide,
                "positionSide": "BOTH",
                "type": "LIMIT",
                "quantity": str(self.perAmount),
                "price": str(self.limitPrice),
                "reduceOnly": "TRUE",
                "timeInForce": "GTC",
                "priceProtect": "TRUE",
            },
            {
                "symbol": self.symbol,
                "side": stopSide,
                "positionSide": "BOTH",
                "type": "STOP_MARKET",
                "quantity": str(self.perAmount),
                "stopPrice": str(self.stopPrice),
                "closePosition": "TRUE",
                "timeInForce": "GTC",
                "priceProtect": "TRUE",
            },
        ]
        params = {"batchOrders": json.dumps(orderData)}
        endPoint = "/fapi/v1/batchOrders"
        orderResp = self.requestPost(endPoint, params, self.getSignature(self.orderTime, params))
        if "respError" in orderResp:
            return orderResp
        return orderResp
