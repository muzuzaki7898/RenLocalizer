// main.qml - RenLocalizer Ana Pencere
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs

import "components"
import "pages"

ApplicationWindow {
    id: root
    width: 1200
    height: 800
    minimumWidth: 900
    minimumHeight: 600
    title: (backend.uiTrigger, backend.getTextWithDefault("app_title", "RenLocalizer") + " v" + backend.version)

    // Global Theme Colors Manager
    readonly property var currentTheme: settingsBackend.currentTheme
    
    readonly property color cardBackground: {
        if (currentTheme === "light") return "#ffffff"
        if (currentTheme === "red") return "#2d1b2e"
        if (currentTheme === "turquoise") return "#0d2b3a"
        if (currentTheme === "green") return "#0a1f12"
        if (currentTheme === "neon") return "#1a0f2d"
        return "#252540" // dark default
    }
    
    readonly property color mainTextColor: (currentTheme === "light") ? "#1a1a2e" : "#ffffff"
    readonly property color secondaryTextColor: (currentTheme === "light") ? "#495057" : "#aaaaaa"
    readonly property color mutedTextColor: (currentTheme === "light") ? "#868e96" : "#666666"
    readonly property color borderColor: (currentTheme === "light") ? "#dee2e6" : "#3d3d54"
    readonly property color inputBackground: (currentTheme === "light") ? "#f8f9fa" : "#1a1a2e"
    readonly property color separatorColor: (currentTheme === "light") ? "#e9ecef" : "#2d2d44"

    // Material Tema Ayarları - Tamamen program içi, sistem temasından bağımsız
    Material.theme: (currentTheme === "light") ? Material.Light : Material.Dark
    
    Material.accent: {
        if (currentTheme === "red") return "#f03e3e" // Lighter red for visibility
        if (currentTheme === "turquoise") return "#0ca678"
        if (currentTheme === "green") return "#37b24d"
        if (currentTheme === "neon") return "#ae3ec9"
        if (currentTheme === "light") return "#4c6ef5" // Modern Blue for light
        return "#7950f2" // Deep Purple for dark default
    }
    
    Material.primary: (currentTheme === "light") ? "#4c6ef5" : "#1a1a2e"
    
    Material.background: {
        if (currentTheme === "light") return "#f1f3f5"
        if (currentTheme === "red") return "#1a0f0f"
        if (currentTheme === "turquoise") return "#050a0f"
        if (currentTheme === "green") return "#050a05"
        if (currentTheme === "neon") return "#0a050f"
        return "#121224" // darker default back
    }

    // Arka plan
    color: Material.background

    // Ana Layout
    RowLayout {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: statusBar.top
        spacing: 0

        // Sol Navigasyon Çubuğu
        NavigationBar {
            id: navBar
            Layout.preferredWidth: 70
            Layout.fillHeight: true
            currentIndex: 0
            onPageSelected: function(index) {
                stackLayout.currentIndex = index
            }
        }

        // Dikey Ayırıcı
        Rectangle {
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            color: "#2d2d44"
        }

        // İçerik Alanı
        StackLayout {
            id: stackLayout
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: 0

            HomePage {
                id: homePage
            }

            ToolsPage {
                id: toolsPage
            }

            GlossaryPage {
                id: glossaryPage
            }

            CachePage {
                id: cachePage
            }

            SettingsPage {
                id: settingsPage
            }

            AboutPage {
                id: aboutPage
            }
        }
    }



    // ==================== GLOBAL TOAST NOTIFICATION ====================
    Rectangle {
        id: toast
        property string message: ""
        property string type: "info" // info, success, error, warning
        
        visible: opacity > 0
        opacity: 0
        z: 9999
        
        anchors.bottom: statusBar.top
        anchors.bottomMargin: 30
        anchors.horizontalCenter: parent.horizontalCenter
        
        width: Math.min(contentLayout.implicitWidth + 60, root.width - 60)
        height: Math.max(54, contentLayout.implicitHeight + 24)
        radius: 10
        color: type === "error" ? "#c0392b" : type === "success" ? "#27ae60" : type === "warning" ? "#d35400" : "#2c3e50"
        border.color: "white"
        border.width: 1
        
        // Shadow (No external plugin needed)
        // opacity behavior is already there

        RowLayout {
            id: contentLayout
            anchors.fill: parent
            anchors.margins: 15
            spacing: 12

            Label {
                text: toast.type === "success" ? "✅" : toast.type === "error" ? "❌" : toast.type === "warning" ? "⚠️" : "ℹ️"
                font.pixelSize: 18
            }

            Label {
                id: toastText
                text: toast.message
                color: "white"
                font.bold: true
                font.pixelSize: 13
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                verticalAlignment: Text.AlignVCenter
            }

            ToolButton {
                text: "✕"
                font.pixelSize: 14
                Material.accent: "white"
                onClicked: toast.opacity = 0
                Layout.alignment: Qt.AlignTop
            }
        }
        
        Behavior on opacity { NumberAnimation { duration: 600 } }
        
        Timer {
            id: toastTimer
            interval: 8000 // 8 saniye (Garantili okuma süresi)
            onTriggered: toast.opacity = 0
        }
        
        function show(msg, lvl) {
            toast.message = msg
            toast.type = lvl
            toast.opacity = 1
            toastTimer.restart()
        }
    }

    // Backend sinyallerini dinle
    Connections {
        target: backend

        function onLogMessage(level, message) {
            homePage.addLog(level, message)
            
            // Eğer ana sayfada değilsek her şeyi (info dahil) göster, 
            // ana sayfadaysak sadece önemli olanları (success/error/warning) göster
            if (stackLayout.currentIndex !== 0 || level === "success" || level === "error" || level === "warning") {
                toast.show(message, level)
            }
        }

        function onProgressChanged(current, total, text) {
            homePage.updateProgress(current, total, text)
        }

        function onStageChanged(stage, displayName) {
            homePage.setStage(stage, displayName)
        }

        function onTranslationStarted() {
            homePage.setTranslating(true)
        }

        function onTranslationFinished(success, message) {
            homePage.setTranslating(false)
            homePage.addLog(success ? "success" : "error", message)
        }

        function onStatsReady(total, translated, untranslated) {
            homePage.showStats(total, translated, untranslated)
        }

        function onWarningMessage(title, message) {
            warningDialog.title = title
            warningDialog.text = message
            warningDialog.open()
        }

        function onUpdateAvailable(currentVersion, latestVersion, releaseUrl) {
            updateDialog.currentVer = currentVersion
            updateDialog.latestVer = latestVersion
            updateDialog.url = releaseUrl
            updateDialog.open()
        }

        function onUpdateCheckFinished(hasUpdate, message) {
            if (!hasUpdate) {
                warningDialog.title = (backend.uiTrigger, backend.getTextWithDefault("info", "Bilgi"))
                warningDialog.text = message
                warningDialog.open()
            }
        }
    }

    Component.onCompleted: {
        // Otomatik güncelleme kontrolü
        backend.checkForUpdates(false)
    }

    // Güncelleme Dialogu
    Dialog {
        id: updateDialog
        property string currentVer: ""
        property string latestVer: ""
        property string url: ""
        
        anchors.centerIn: parent
        width: 450
        modal: true
        title: (backend.uiTrigger, backend.getTextWithDefault("update_available_title", "🚀 Güncelleme Mevcut!"))
        
        background: Rectangle {
            color: "#252540"
            radius: 16
            border.color: "#3498db"
            border.width: 2
        }
        
        contentItem: ColumnLayout {
            spacing: 15
            Label { 
                text: (backend.uiTrigger, backend.getTextWithDefault("update_available_message", "Yeni bir sürüm mevcut!")).replace("{latest}", updateDialog.latestVer).replace("{current}", "") 
                font.bold: true; font.pixelSize: 18; color: "#3498db"
                Layout.alignment: Qt.AlignHCenter
            }
            Label { 
                text: (backend.uiTrigger, backend.getTextWithDefault("current_version", "Mevcut Sürüm: ")) + updateDialog.currentVer
                color: "#ccc"; font.pixelSize: 14
                Layout.alignment: Qt.AlignHCenter
            }
            Label { 
                text: (backend.uiTrigger, backend.getTextWithDefault("new_version", "Yeni Sürüm: ")) + updateDialog.latestVer
                color: "#2ecc71"; font.bold: true; font.pixelSize: 16
                Layout.alignment: Qt.AlignHCenter
            }
            Label {
                text: (backend.uiTrigger, backend.getTextWithDefault("update_download_desc", "İndirmek için tarayıcıda açmak ister misiniz?"))
                color: "#aaa"; font.pixelSize: 13
                Layout.alignment: Qt.AlignHCenter
            }
        }
        
        footer: DialogButtonBox {
            // "İndir" butonu -> Tarayıcıda açar
            Button {
                text: "🌐 " + (backend.uiTrigger, backend.getTextWithDefault("btn_download", "İndir ve Güncelle"))
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                background: Rectangle { radius: 8; color: "#2ecc71" }
                contentItem: Label { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter }
                onClicked: Qt.openUrlExternally(updateDialog.url)
            }
            // "Kapat" butonu
            Button {
                text: (backend.uiTrigger, backend.getTextWithDefault("btn_close", "Kapat"))
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                background: Rectangle { radius: 8; color: "#555" }
                contentItem: Label { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter }
                onClicked: updateDialog.close()
            }
        }
    }

    // Uyarı Dialogu (QML Popup)
    Dialog {
        id: warningDialog
        property alias text: warningText.text
        
        anchors.centerIn: parent
        width: 400
        modal: true
        
        title: "⚠️ " + (backend.uiTrigger, backend.getTextWithDefault("warning", "Uyarı"))
        
        background: Rectangle {
            color: "#252540"
            radius: 16
            border.color: "#ffd93d"
            border.width: 1
        }
        
        header: Rectangle {
            color: "transparent"
            height: 50
            
            Label {
                anchors.centerIn: parent
                text: warningDialog.title
                font.pixelSize: 16
                font.bold: true
                color: "#ffd93d"
            }
        }
        
        contentItem: ColumnLayout {
            spacing: 15
            Label {
                id: warningText
                text: ""
                color: "white"
                wrapMode: Text.Wrap
                font.pixelSize: 14
                Layout.fillWidth: true
                Layout.margins: 20
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
        
        footer: DialogButtonBox {
            background: Rectangle { color: "transparent" }
            Button {
                text: (backend.uiTrigger, backend.getTextWithDefault("btn_ok", "Tamam"))
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                
                background: Rectangle {
                    radius: 8
                    color: Material.accent
                }
                
                contentItem: Label {
                    text: parent.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: warningDialog.close()
            }
            alignment: Qt.AlignHCenter
            padding: 10
        }
    }

    // Alt Durum Çubuğu
    Rectangle {
        id: statusBar
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 25
        color: Material.theme === Material.Dark ? "#121224" : "#e0e0e0"

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 20

            Label {
                text: (backend.uiTrigger, backend.getTextWithDefault("version_label", "Sürüm:")) + " v" + backend.version
                font.pixelSize: 11
                color: "#888"
            }

            Label {
                id: statusText
                text: homePage.isTranslating ? 
                    (backend.uiTrigger, backend.getTextWithDefault("translating", "Çeviri yapılıyor...")) : 
                    (backend.uiTrigger, backend.getTextWithDefault("ready", "Hazır"))
                font.pixelSize: 11
                color: homePage.isTranslating ? Material.accent : "#888"
            }

            Item { Layout.fillWidth: true }
            
            Label {
                text: settingsBackend.currentTheme.toUpperCase()
                font.pixelSize: 11
                color: "#666"
            }

            Label {
                text: settingsBackend.currentLanguage.toUpperCase()
                font.pixelSize: 11
                color: "#666"
            }
        }
    }
}
