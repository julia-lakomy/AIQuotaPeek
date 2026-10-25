pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import "../code/Config.js" as Config

PlasmoidItem {
    id: root

    property var snapshot: ({
        chatgpt: { state: "checking", session: { remaining: null }, weekly: { remaining: null } },
        claude: { state: "checking", session: { remaining: null }, weekly: { remaining: null } },
        paused: true, fullscreenKnown: false, browserOpen: false, busy: false
    })
    property bool backendAvailable: false

    Plasmoid.title: "Limity AI"
    Plasmoid.icon: "view-statistics"

    function service(name) {
        return snapshot[name] || { state: "checking", session: {}, weekly: {} }
    }

    function percent(value) {
        return value === null || value === undefined ? "—" : value + "%"
    }

    function panelPercent(name) {
        if (!backendAvailable) return "—"
        var item = service(name)
        var values = [item.session.remaining, item.weekly.remaining].filter(v => v !== null && v !== undefined)
        return values.length ? Math.min.apply(null, values) + "%" : "—"
    }

    function metricText(name, key) {
        if (!backendAvailable) return "brak danych"
        var metric = service(name)[key] || {}
        return metric.remaining === null || metric.remaining === undefined ? "brak danych" : metric.remaining + "% pozostało"
    }

    function resetText(name, key) {
        var metric = service(name)[key] || {}
        return metric.reset ? "Reset: " + metric.reset : "Reset: brak danych"
    }

    function lastRead(name) {
        var value = service(name).lastRead
        return value ? "Odczyt: " + value.slice(11, 16) : "Brak odczytu"
    }

    function request(method, path, done) {
        var xhr = new XMLHttpRequest()
        xhr.open(method, "http://127.0.0.1:" + Config.port + path)
        xhr.setRequestHeader("X-Limity-Token", Config.token)
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== 4) return
            if (done) done(xhr.status, xhr.responseText)
        }
        xhr.onerror = function() { if (done) done(0, "") }
        xhr.send()
    }

    function updateStatus() {
        request("GET", "/status", function(code, body) {
            backendAvailable = code === 200
            if (code === 200) {
                try { snapshot = JSON.parse(body) } catch (e) { backendAvailable = false }
            }
        })
    }

    function openBrowser(name) {
        request("POST", "/open?service=" + name, function() { updateStatus() })
    }

    function finishBrowser() {
        request("POST", "/finish", function() { updateStatus() })
    }

    function refresh() {
        request("POST", "/refresh", function() { updateStatus() })
    }

    function activate() {
        if (!backendAvailable) {
            expanded = true
            return
        }
        if (snapshot.browserOpen) {
            expanded = !expanded
            return
        }
        var chatNeedsLogin = service("chatgpt").state === "login"
        var claudeNeedsLogin = service("claude").state === "login"
        var firstUse = service("chatgpt").state === "checking" && service("claude").state === "checking"
        if ((chatNeedsLogin && claudeNeedsLogin) || firstUse) openBrowser("all")
        else if (chatNeedsLogin) openBrowser("chatgpt")
        else if (claudeNeedsLogin) openBrowser("claude")
        else expanded = !expanded
    }

    Timer {
        interval: 3000
        repeat: true
        running: true
        onTriggered: root.updateStatus()
    }
    Component.onCompleted: updateStatus()

    compactRepresentation: Item {
        implicitWidth: compactLabel.implicitWidth + 12
        implicitHeight: Math.max(compactLabel.implicitHeight + 4, Kirigami.Units.gridUnit)
        Layout.minimumWidth: implicitWidth
        Layout.preferredWidth: implicitWidth

        QQC2.Label {
            id: compactLabel
            anchors.centerIn: parent
            text: "GPT " + root.panelPercent("chatgpt") + " · Claude " + root.panelPercent("claude")
            font.pixelSize: 12
            elide: Text.ElideNone
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.activate()
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 15
        spacing: Kirigami.Units.smallSpacing

        RowLayout {
            Layout.fillWidth: true
            QQC2.Label {
                text: "Limity AI"
                font.bold: true
                font.pixelSize: 16
                Layout.fillWidth: true
            }
            QQC2.ToolButton {
                text: "⟳"
                enabled: root.backendAvailable && !root.snapshot.busy
                onClicked: root.refresh()
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.text: "Odśwież"
            }
        }

        QQC2.Label {
            Layout.fillWidth: true
            visible: !root.backendAvailable || !root.snapshot.fullscreenKnown || root.snapshot.paused || root.snapshot.browserOpen
            text: !root.backendAvailable ? "Usługa widgetu nie działa" :
                  !root.snapshot.fullscreenKnown ? "Oczekiwanie na stan pełnego ekranu z KDE" :
                  root.snapshot.paused ? "Wstrzymano podczas pełnego ekranu" :
                  "Przeglądarka jest otwarta. Po zalogowaniu wybierz „Zakończ logowanie”."
            wrapMode: Text.WordWrap
            opacity: 0.8
        }

        QQC2.Button {
            visible: root.snapshot.browserOpen
            text: "Zakończ logowanie"
            onClicked: root.finishBrowser()
        }

        Repeater {
            model: ["chatgpt", "claude"]
            delegate: ColumnLayout {
                required property string modelData
                Layout.fillWidth: true
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true
                    QQC2.Button {
                        text: parent.parent.modelData === "chatgpt" ? "ChatGPT ↗" : "Claude ↗"
                        flat: true
                        onClicked: root.openBrowser(parent.parent.modelData)
                    }
                    Item { Layout.fillWidth: true }
                    QQC2.Label {
                        text: root.lastRead(parent.parent.modelData)
                        opacity: 0.65
                    }
                }

                QQC2.Label {
                    text: "Obecna sesja: " + root.metricText(parent.modelData, "session")
                }
                QQC2.Label {
                    text: root.resetText(parent.modelData, "session")
                    opacity: 0.7
                }
                QQC2.Label {
                    text: "Limit tygodniowy: " + root.metricText(parent.modelData, "weekly")
                }
                QQC2.Label {
                    text: root.resetText(parent.modelData, "weekly")
                    opacity: 0.7
                }
                QQC2.Button {
                    visible: root.service(parent.modelData).state === "login" && !root.snapshot.browserOpen
                    text: "Zaloguj się"
                    onClicked: root.openBrowser(parent.modelData)
                }
                QQC2.Label {
                    visible: root.service(parent.modelData).state === "unavailable"
                    text: "Nie udało się odczytać danych"
                    opacity: 0.7
                }
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: Kirigami.Theme.textColor
                    opacity: 0.15
                }
            }
        }
    }
}
