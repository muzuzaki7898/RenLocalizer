// NavigationBar.qml - Sol Navigasyon Menüsü
import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts

Rectangle {
    id: navRoot
    color: (root.currentTheme === "light") ? "#ffffff" : "#121224"

    property int currentIndex: 0
    signal pageSelected(int index)

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 20
        anchors.bottomMargin: 20
        spacing: 15

        // Logo / Başlık
        Rectangle {
            Layout.preferredWidth: 54
            Layout.preferredHeight: 54
            Layout.alignment: Qt.AlignHCenter
            radius: 14
            color: root.inputBackground
            border.color: Material.accent
            border.width: root.currentTheme === "light" ? 2 : 1

            Image {
                anchors.centerIn: parent
                source: backend.get_asset_url("icon.ico")
                width: 36
                height: 36
                fillMode: Image.PreserveAspectFit
            }
        }

        Item { Layout.preferredHeight: 15 }

        // Ana Menü Öğeleri
        NavButton {
            icon: "🏠"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_home", "Home"))
            selected: navRoot.currentIndex === 0
            onClicked: {
                navRoot.currentIndex = 0
                navRoot.pageSelected(0)
            }
        }

        NavButton {
            icon: "🛠"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_tools", "Tools"))
            selected: navRoot.currentIndex === 1
            onClicked: {
                navRoot.currentIndex = 1
                navRoot.pageSelected(1)
            }
        }

        NavButton {
            icon: "📚"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_glossary", "Glossary Management"))
            selected: navRoot.currentIndex === 2
            onClicked: {
                navRoot.currentIndex = 2
                navRoot.pageSelected(2)
            }
        }

        NavButton {
            icon: "🧠"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_cache", "Translation Memory (TM)"))
            selected: navRoot.currentIndex === 3
            onClicked: {
                navRoot.currentIndex = 3
                navRoot.pageSelected(3)
            }
        }

        NavButton {
            icon: "⚙"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_settings", "Settings"))
            selected: navRoot.currentIndex === 4
            onClicked: {
                navRoot.currentIndex = 4
                navRoot.pageSelected(4)
            }
        }

        // Spacer
        Item { Layout.fillHeight: true }

        // Alt Menü
        NavButton {
            icon: "❤"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_support", "Support"))
            onClicked: backend.openUrl("https://www.patreon.com/c/LordOfTurk")
        }

        NavButton {
            icon: "📖"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_wiki", "Wiki"))
            onClicked: backend.openUrl("https://github.com/Lord0fTurk/RenLocalizer/wiki")
        }

        NavButton {
            icon: "ℹ"
            tooltip: (backend.uiTrigger, backend.getTextWithDefault("nav_about", "About"))
            selected: navRoot.currentIndex === 5
            onClicked: {
                navRoot.currentIndex = 5
                navRoot.pageSelected(5)
            }
        }
    }

    // NavButton Component
    component NavButton: Rectangle {
        property string icon: ""
        property string tooltip: ""
        property bool selected: false
        signal clicked()

        Layout.preferredWidth: 48
        Layout.preferredHeight: 48
        Layout.alignment: Qt.AlignHCenter
        radius: 12
        color: {
            if (mouseArea.containsMouse) return root.separatorColor
            if (selected) return root.currentTheme === "light" ? Qt.alpha(Material.accent, 0.1) : root.cardBackground
            return "transparent"
        }

        Behavior on color {
            ColorAnimation { duration: 150 }
        }

        Label {
            anchors.centerIn: parent
            text: icon
            font.pixelSize: 22
            opacity: selected ? 1.0 : 0.7
        }

        // Sol kenar highlight
        Rectangle {
            visible: selected
            width: 3
            height: parent.height - 10
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            radius: 2
            color: Material.accent
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }

        ToolTip.visible: mouseArea.containsMouse
        ToolTip.text: tooltip
        ToolTip.delay: 500
    }
}
