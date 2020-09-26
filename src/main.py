import sys
import json
import threading
import time

import requests
import websocket
from websocket import create_connection

from capture import Capture


def get_relay(token, endpoint='http://localhost:8080/api/v1/relays'):
    """リレーを取得する
    
    Parameters
    ----------
    token : str
        リレーを取得するためのトークン
    endpoint : str, optional
        APIのエンドポイント, by default 'http://localhost:8080/api/v1/relays'
    
    Returns
    -------
    str or None
        成功時：リレー
        失敗時：None
    """
    data = dict(
        token=token
    )
    response = requests.post(endpoint, data=data)
    if response.status_code != requests.codes.ok:
        return None
    # レスポンスデータのパース
    response_data = json.loads(response.text)
    if 'errors' in response_data:
        return None
    if not 'relay' in response_data:
        return None
    return response_data['relay']


# Callback functions
is_sending_captured_data = False


def on_message(ws, message):
    global is_sending_captured_data
    print('[Log] Received: %s' % message)
    message_data = json.loads(message)
    if 'header' in message_data and 'client_id' in message_data['header']:
        with open('settings.json') as fp:
            settings = json.load(fp)
        settings['relay']['client_id'] = message_data['header']['client_id']
        with open('settings.json', mode="w") as fp:
            json.dump(settings, fp)
        print("[Log] Writed client_id: %s" %
              message_data['header']['client_id'])

    if not is_sending_captured_data:
        thread01 = threading.Thread(target=send_captured_data, args=(ws,))
        thread01.setDaemon(True)  # sys.exit()時にスレッドも終了できるようにするための設定
        thread01.start()
        is_sending_captured_data = True

    if not 'contents' in message_data:
        return
    if message_data['contents'] == None:
        return
    print(message_data['contents'])


def on_error(ws, error):
    print('[Log] Error: %s' % error)


def on_close(ws):
    print("[Log] %s" % ws)
    print('[Log] Close')


def on_open(ws):
    print('[Log] Open new connection')

    settings = {}
    with open('settings.json') as fp:
        settings = json.load(fp)

    response = {'header': {'cmd': 'connect',
                           'client_id': None}, 'contents': None}
    if not settings['relay']['relay_token'] == None and not settings['relay']['client_id'] == None:
        response['header']['cmd'] = 'reconnect'
        response['header']['client_id'] = settings['relay']['client_id']

    ws.send(json.dumps(response))
    print("[Log] Sended: %s" % json.dumps(response))


def send_captured_data(ws):
    capture = Capture(sys.argv[1], dataSize=480, isInvert=True)
    capture.run()

    # 初期値を設定
    max_distance = 0
    max_intensity = 0
    max_elapsed_time = 0
    sequence_id = 0
    preTime = time.time()

    while True:
        if capture.dataObtained:
            # 排他制御開始
            capture.lock.acquire()

            # データを取得
            theta = list(capture.theta)
            distance = list(capture.distance)
            intensity = list(capture.intensity)

            # データを取得したのでデータ取得フラグを下ろす
            capture.dataObtained = False

            # 排他制御終了
            capture.lock.release()

            # 現在設定されている最大値を取得
            max_distance = max([max_distance] + distance)
            max_intensity = max([max_intensity] + intensity)

            # 送信するデータを作成
            payload = json.dumps(
                dict(
                    header=dict(
                        cmd="relay"
                    ),
                    contents=dict(
                        sequenceId=sequence_id,
                        theta=theta,
                        distance=distance,
                        intensity=intensity,
                        maxDistance=max_distance,
                        maxIntensity=max_intensity
                    )
                )
            )
            ws.send(payload)  # データを送信

            elapsedTime = time.time() - preTime
            preTime = time.time()
            if max_elapsed_time < elapsedTime:
                max_elapsed_time = elapsedTime
            print("[Log] Sequence ID: %d, Elapsed time: %f, Max elapsed time: %f" % (
                sequence_id, elapsedTime, max_elapsed_time))
            sequence_id += 1

        else:
            time.sleep(0.01)


def main():
    settings = {}
    with open('settings.json') as fp:
        settings = json.load(fp)

    if not 'token' in settings:
        print('[ERROR] Setting file format error')
        return
    if not 'endpoints' in settings:
        print('[ERROR] Setting file format error')
        return
    if not 'relay_token' in settings['endpoints']:
        print('[ERROR] Setting file format error')
        return
    if not 'relay_websocket' in settings['endpoints']:
        print('[ERROR] Setting file format error')
        return
    if not 'relay' in settings:
        print('[ERROR] Setting file format error')
        return
    if not 'relay_token' in settings['relay']:
        print('[ERROR] Setting file format error')
        return
    if not 'client_id' in settings['relay']:
        print('[ERROR] Setting file format error')
        return

    if settings['relay']['relay_token'] == None:
        token = settings['token']
        endpoint = settings['endpoints']['relay_token']
        settings['relay']['relay_token'] = get_relay(token, endpoint)
        print('[Log] New relay: %s' % settings['relay']['relay_token'])

    if len(sys.argv) == 1:
        print("You must specify serial port! ex) " + sys.argv[0] + " COM2")
        quit()

    with open('settings.json', mode='w') as fp:
        json.dump(settings, fp)

    websocket_endpoint = settings['endpoints']['relay_websocket'] % settings['relay']['relay_token']
    print("[Log] Endpoint: %s" % websocket_endpoint)
    ws = websocket.WebSocketApp(websocket_endpoint, on_message=on_message,
                                on_error=on_error, on_open=on_open, on_close=on_close)
    ws.run_forever()


if __name__ == "__main__":
    websocket.enableTrace(False)
    main()
