// AboutPage.qml - Hakkında Sayfası
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Rectangle {
    id: aboutPage
    color: Material.background

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width - 72
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 24
            spacing: 24

            // App Info Card
            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: 20
                implicitHeight: 200
                radius: 16
                color: root.cardBackground

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 30
                    spacing: 30

                    // Logo
                    Rectangle {
                        Layout.preferredWidth: 120
                        Layout.preferredHeight: 120
                        radius: 24
                        color: root.inputBackground
                        border.color: Material.accent
                        border.width: 1

                        Image {
                            anchors.centerIn: parent
                            source: "file:///" + backend.get_app_path() + "/icon.ico"
                            width: 80
                            height: 80
                            fillMode: Image.PreserveAspectFit
                        }
                    }

                    // Info
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Label {
                            text: "RenLocalizer"
                            font.pixelSize: 32
                            font.bold: true
                            color: root.mainTextColor
                        }

                        Label {
                            text: "v" + backend.version
                            font.pixelSize: 18
                            color: Material.accent
                        }

                        Label {
                            text: (backend.uiTrigger, backend.getTextWithDefault("app_description", "Profesyonel Ren'Py çeviri aracı.\nAI destekli, çoklu motor, hızlı ve güvenilir."))
                            font.pixelSize: 14
                            color: root.secondaryTextColor
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }

                        Label {
                            text: "© 2024-2026 LordOfTurk"
                            font.pixelSize: 12
                            color: "#666"
                        }
                    }
                }
            }

            // Patreon Card
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 120
                radius: 16
                
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#ff424d" }
                    GradientStop { position: 1.0; color: "#e91e63" }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 20

                    Label {
                        text: "🎉"
                        font.pixelSize: 48
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Label {
                            text: (backend.uiTrigger, backend.getTextWithDefault("nav_support", "Destek Ol!"))
                            font.pixelSize: 20
                            font.bold: true
                            color: "white"
                        }

                        Label {
                            text: (backend.uiTrigger, backend.getTextWithDefault("support_banner_desc", "Geliştirmeye katkıda bulunun ve özel içeriklere erişin."))
                            font.pixelSize: 13
                            color: "#ccffffff"
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                        }
                    }

                    Button {
                        text: (backend.uiTrigger, backend.getTextWithDefault("patreon_button_text", "💜 Patreon"))
                        onClicked: backend.openUrl("https://www.patreon.com/c/LordOfTurk")

                        contentItem: Label {
                            text: parent.text
                            font.pixelSize: 16
                            font.bold: true
                            color: "#ff424d"
                            horizontalAlignment: Text.AlignHCenter
                        }

                        background: Rectangle {
                            radius: 12
                            color: parent.down ? "#eee" : parent.hovered ? "#fff" : "#f5f5f5"
                        }
                    }
                }
            }

            // Links Card
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: linksCol.height + 40
                radius: 16
                color: root.cardBackground

                ColumnLayout {
                    id: linksCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 20
                    spacing: 16

                    Label {
                        text: "🔗 " + (backend.uiTrigger, backend.getTextWithDefault("links_title", "Bağlantılar"))
                        font.pixelSize: 18
                        font.bold: true
                        color: root.mainTextColor
                    }

                    GridLayout {
                        columns: 2
                        columnSpacing: 16
                        rowSpacing: 12
                        Layout.fillWidth: true

                        // GitHub Button
                        LinkButton { label: (backend.uiTrigger, backend.getTextWithDefault("link_github", "📚 GitHub")); onClicked: backend.openUrl("https://github.com/Lord0fTurk/RenLocalizer") }
                        LinkButton { label: (backend.uiTrigger, backend.getTextWithDefault("link_wiki", "📖 Wiki")); onClicked: backend.openUrl("https://github.com/Lord0fTurk/RenLocalizer/wiki") }
                        LinkButton { label: (backend.uiTrigger, backend.getTextWithDefault("link_issues", "🐛 Hata Bildir")); onClicked: backend.openUrl("https://github.com/Lord0fTurk/RenLocalizer/issues") }
                    }
                }
            }

            // Features Card
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: featCol.height + 40
                radius: 16
                color: root.cardBackground

                ColumnLayout {
                    id: featCol
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 20
                    spacing: 16

                    Label {
                        text: "✨ " + (backend.uiTrigger, backend.getTextWithDefault("features_title", "Özellikler"))
                        font.pixelSize: 18
                        font.bold: true
                        color: root.mainTextColor
                    }

                    Flow {
                        Layout.fillWidth: true
                        spacing: 12

                        Repeater {
                            model: [
                                (backend.uiTrigger, backend.getTextWithDefault("feature_multi_engine", "🌐 Multi-Engine")),
                                (backend.uiTrigger, backend.getTextWithDefault("feature_ai_powered", "🤖 AI Destekli")),
                                (backend.uiTrigger, backend.getTextWithDefault("feature_fast_translation", "⚡ Hızlı Çeviri")),
                                (backend.uiTrigger, backend.getTextWithDefault("feature_rpa_support", "📦 RPA Desteği")),
                                (backend.uiTrigger, backend.getTextWithDefault("feature_auto_unren", "🔄 Auto UnRen")),
                                (backend.uiTrigger, backend.getTextWithDefault("feature_glossary_short", "📝 Glossary")),
                                (backend.uiTrigger, backend.getTextWithDefault("feature_multi_lang", "🌍 Çoklu Dil")),
                                (backend.uiTrigger, backend.getTextWithDefault("feature_modern_ui", "🎨 Modern UI"))
                            ]

                            delegate: Rectangle {
                                implicitWidth: featureLabel.implicitWidth + 24
                                implicitHeight: 32
                                radius: 16
                                color: root.inputBackground
                                border.color: Material.accent
                                border.width: 1

                                Label {
                                    id: featureLabel
                                    anchors.centerIn: parent
                                    text: modelData
                                    font.pixelSize: 12
                                    color: root.mainTextColor
                                }
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 40 }
        }
    }

    component LinkButton: Rectangle {
        property string label: ""
        signal clicked()
        Layout.fillWidth: true
        height: 44
        radius: 8
        color: mouseArea.containsMouse ? root.separatorColor : root.inputBackground
        border.color: root.borderColor
        
        Label { anchors.centerIn: parent; text: label; color: root.mainTextColor; font.pixelSize: 14 }
        MouseArea { id: mouseArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: parent.clicked() }
    }
}
