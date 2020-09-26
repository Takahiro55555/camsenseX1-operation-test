let ws = null;
let relayIdPublic = null;
let isAvailableWebsocket = false;
let messageContents = null;

function connectDisconnectBtn(obj) {
    if (obj.value === "connect") {
        connect();
    } else if (obj.value === "disconnect") {
        disconnect();
    }
}

function makeConnectButton(obj) {
    const connectClass = "btn btn-primary btn-block";
    obj.setAttribute("value", "connect");
    obj.setAttribute("class", connectClass);
    obj.innerText = "接続";
}

function makeDisconnectButton(obj) {
    const disconnectClass = "btn btn-danger btn-block";
    obj.setAttribute("value", "disconnect");
    obj.setAttribute("class", disconnectClass);
    obj.innerText = "切断";
}

function makeReconnectButton(obj) {
    const disconnectClass = "btn btn-success btn-block";
    obj.setAttribute("value", "disconnect");
    obj.setAttribute("class", disconnectClass);
    obj.innerText = "再接続";
}

function connect() {
    let relayToken = document.getElementById("relay-token").value;
    if (relayToken === "") {
        makeConnectButton(document.getElementById("btn-connect-disconnect"));
        return;
    }

    const wsUrl = 'wss://controller.moyashi.dev/ws/v1/relays/' + relayToken;
    relayIdPublic = relayToken.match(/^[0-9a-zA-Z]+/)[0];

    try {
        ws = new WebSocket(wsUrl);
        ws.onopen = onOpen;
        ws.onmessage = onMessage;
        ws.onerror = onError;
        ws.onclose = onClose;
    } catch (e) {
        console.error("[WebSocket] 接続に失敗しました");
        makeConnectButton(document.getElementById("btn-connect-disconnect"));
        return;
    }
    makeDisconnectButton(document.getElementById("btn-connect-disconnect"));
}

function disconnect() {
    if (isAvailableWebsocket) {
        isAvailableWebsocket = false;
        let msg = {
            "header": {
                "cmd": "exit"
            },
            "contents": null
        }
        ws.send(JSON.stringify(msg));
        localStorage.removeItem(relayIdPublic);
        makeConnectButton(document.getElementById("btn-connect-disconnect"));
    }
}

function onOpen(e) {
    console.log("[WebSocket] 接続に成功しました");
    isAvailableWebsocket = true;
    makeDisconnectButton(document.getElementById("btn-connect-disconnect"));
    let clientId = localStorage.getItem(relayIdPublic);
    let msg = {
        "header": {
            "cmd": "connect",
            "client_id": clientId
        },
        "contents": null
    };
    if (clientId) {
        // 再接続
        msg['header']['cmd'] = 'reconnect';
        console.log('[WebSocket] reconnect');
        console.log(JSON.stringify(msg));
    }
    ws.send(JSON.stringify(msg));
}

function onMessage(e) {
    let msg = JSON.parse(e.data);
    if (msg.errors) {
        console.error('[WebSocket][Message] ' + String(e.data));
    } else if (msg.header.client_id) {
        localStorage.setItem(relayIdPublic, msg.header.client_id);
        console.log('[WebSocket] Save new client id: ' + msg.header.client_id);
    } else if (msg.contents) {
        messageContents = msg.contents;
        plotP5.redraw();
    } else {
        console.log('[WebSocket][Message] ' + String(e.data));
    }
}

function onError(error) {
    console.error("[WebSocker] エラーが発生しました");
    isAvailableWebsocket = false;
    if (localStorage.getItem(relayIdPublic)) {
        makeReconnectButton(document.getElementById("btn-connect-disconnect"));
    } else {
        makeConnectButton(document.getElementById("btn-connect-disconnect"));
    }
}

function onClose(e) {
    console.log("[WebSocket] 接続が切断されました");
    console.log("[WebSocket] Code: " + String(e.code));
    console.log("[WebSocket] Reason: " + e.reason);
    isAvailableWebsocket = false;

    if (localStorage.getItem(relayIdPublic)) {
        makeReconnectButton(document.getElementById("btn-connect-disconnect"));
    } else {
        makeConnectButton(document.getElementById("btn-connect-disconnect"));
    }
}

const plotP5Sketch = function (p) {
    p.preload = function () { };

    p.setup = function () {
        p.createCanvas(500, 500);
        p.background(0);
        p.noLoop();
    };

    p.draw = function () {
        if(messageContents === null){
            return;
        }
        const from = p.color(0x0, 0xa1, 0xe9, 20);
        const to = p.color(0x0, 0xa1, 0xe9, 0xff);

        const centerX = p.width / 2;
        const centerY = p.height / 2;
        const radius = p.width / 2 - 10;


        p.background(200);

        for(let i=0; i < messageContents.theta.length; i++){

            const x = centerX + 8 * Math.sin(messageContents.theta[i]) * radius * messageContents.distance[i] / messageContents.maxDistance;
            const y = centerY + 8 * Math.cos(messageContents.theta[i]) * radius * messageContents.distance[i] / messageContents.maxDistance;
            const pointColor = p.lerpColor(from, to, messageContents.intensity[i] / messageContents.maxIntensity)

            p.push();
            p.stroke(pointColor);
            p.strokeWeight(6);
            p.point(x, y);
            p.pop();
        }
        console.log("SequenceId: " + String(messageContents.sequenceId));
        p.counter++;
    };
}

function toggleCard(obj, id) {
    const pulusBtnPath = "/img/plus.svg";
    const minusBtnPath = "/img/minus.svg";
    const target = document.getElementById(id);
    console.log("toggle btn");
    const isHidden = target.hasAttribute("hidden");
    if (isHidden) {
        // 非表示部分を表示する
        target.removeAttribute("hidden");
        obj.src = minusBtnPath;
    } else {
        // 表示部分を非表示にする
        target.setAttribute("hidden", true);
        obj.src = pulusBtnPath;
    }
}

const plotP5 = new p5(plotP5Sketch, "plot-area");
function resizeCanvas() {
    const plotWidth = document.getElementById("plot-area").clientWidth;
    const plotHeight = plotWidth;
    plotP5.resizeCanvas(plotHeight, plotWidth);
    plotP5.redraw();
}
window.onresize = resizeCanvas;
window.onload = resizeCanvas;