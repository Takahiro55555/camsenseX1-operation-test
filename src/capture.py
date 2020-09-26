# 参考: Qiita「激安LiDAR(Camsense X1)を使ってみる」
#    URL: https://qiita.com/junp007/items/819aced4d48efd97c79f

import math
import serial
import sys
import struct
import time
import threading


class Capture:
    def __init__(self, serialPort, dataSize=460, isInvert=True):
        self.theta = [0] * dataSize
        self.distance = [0] * dataSize
        self.intensity = [0] * dataSize
        self.writePos = 0
        self.serial = serial.Serial(port=serialPort, baudrate=115200)
        self.dataSize = dataSize
        self.thread = threading.Thread(target=self.getData)
        self.lock = threading.Lock()
        self.isInvert = isInvert
        self.dataObtained = False
        self.rpm = 0

    def getDataUnit(self):
        # まずはヘッダまで読み捨てる
        header = b"\x55\xAA\x03\x08"
        headerPos = 0
        while True:
            tmp = self.serial.read(1)
            if tmp[0] == header[headerPos]:
                headerPos += 1
                if headerPos == len(header):
                    break
            else:
                headerPos = 0

        tmp = self.serial.read(4)
        # "<" : リトルエンディアン, "H" : 2バイト符号なしデータ, "B" : 1バイト符号なしデータ
        (rotationSpeedTmp, startAngleTmp) = struct.unpack_from("<2H", tmp)
        self.rpm = rotationSpeedTmp / 64
        startAngle = (startAngleTmp - 0xa000) / 64
        # 距離、強度データを格納する配列を用意
        distanceTmp = [0] * 8
        intensityTmp = [0] * 8
        for i in range(8):
            tmp = self.serial.read(3)
            (distanceTmp[i], intensityTmp[i]) = struct.unpack_from("<HB", tmp)
        tmp = self.serial.read(4)
        (endAngleTmp, crc) = struct.unpack_from("<2H", tmp)
        endAngle = (endAngleTmp - 0xa000) / 64

        return (distanceTmp, intensityTmp, startAngle, endAngle)

    def getData(self):
        preStartAngle = 0
        while True:
            (distanceTmp, intensityTmp, startAngle, endAngle) = self.getDataUnit()

            # 0度付近の場合は開始角度と終了角度の大小関係が逆になることがあるので、終了角度に360度足して大小関係を維持する
            if endAngle < startAngle:
                endAngle += 360

            # 開始角度が小さくなったら0度の場所なのでデータ更新フラグを立てる
            if (startAngle - preStartAngle < 0):
                self.dataObtained = True
            preStartAngle = startAngle

            # 角度をラジアンに変換
            startAngleRad = startAngle * math.pi / \
                180 * (-1 if self.isInvert else 1)
            endAngleRad = endAngle * math.pi / \
                180 * (-1 if self.isInvert else 1)
            # 1ステップ当たりの角度を計算
            angleIncrement = (endAngleRad - startAngleRad) / len(distanceTmp)
            # 排他制御開始
            self.lock.acquire()
            for i in range(len(distanceTmp)):
                self.theta[self.writePos] = startAngleRad + angleIncrement * i
                self.distance[self.writePos] = distanceTmp[i]
                self.intensity[self.writePos] = intensityTmp[i]
                self.writePos += 1
                if self.writePos >= self.dataSize:
                    self.writePos = 0
            # 排他制御終了
            self.lock.release()

    def run(self, set_deamon=True):
        self.thread.setDaemon(set_deamon)
        self.thread.start()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("You must specify serial port! ex) " + sys.argv[0] + " COM2")
        quit()
    capture = Capture(sys.argv[1], dataSize=480, isInvert=True)
    capture.run()

    # 初期値を設定
    maxDistance = 0
    maxIntensity = 0
    maxElapsedTime = 0
    sequence_id = 0
    preTime = time.time()

    try:
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
                maxDistance = max([maxDistance] + distance)
                maxIntensity = max([maxIntensity] + intensity)

                # 送信するデータを作成
                data = dict(
                    sequenceId=sequence_id,
                    theta=theta,
                    distance=distance,
                    intensity=intensity,
                    maxDistance=maxDistance,
                    maxIntensity=maxIntensity
                )

                elapsedTime = time.time() - preTime
                preTime = time.time()
                print("[Log] Sequence ID: %d, Elapsed time: %f, Max elapsed time: %f" % (
                    sequence_id, elapsedTime, maxElapsedTime))
                sequence_id += 1
                if maxElapsedTime < elapsedTime:
                    maxElapsedTime = elapsedTime

            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        sys.exit(0)
