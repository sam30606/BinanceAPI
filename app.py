from binanceAPI import Binance
from flask import Flask, request
import json
import os


app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def main():

    reqData = json.loads(request.data)
    binance = Binance(reqData)
    account = binance.getAccountInfo()
    if "respError" in account:
        print(account["respError"])
        return account["respError"]

    msg = binance.putOrder()
    if "respError" in msg:
        print(msg["respError"])
        return msg["respError"]

    print(msg)
    return msg


@app.route("/heartBeat", methods=["GET"])
def checkConnect():
    msg = "Alive"
    return msg


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
