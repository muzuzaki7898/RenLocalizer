// ToolsPage.qml - Araçlar Sayfası (Restored)
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs

Rectangle {
    id: toolsPage
    color: Material.background

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width - 48
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.margins: 24
            spacing: 24

            Label {
                text: "🛠 " + (backend.uiTrigger, backend.getTextWithDefault("nav_tools", "Araçlar"))
                font.pixelSize: 24
                font.bold: true
                color: root.mainTextColor
            }

            // Araç Grupları
            Flow {
                Layout.fillWidth: true
                spacing: 15
                padding: 5
                Layout.alignment: Qt.AlignHCenter

                // --- RPA Araçları ---
                ToolCard {
                    title: (backend.uiTrigger, backend.getTextWithDefault("unrpa_title", "RPA Arşiv Yönetimi"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("unrpa_desc", ".rpa dosyalarını açın veya paketleyin."))
                    icon: "📦"
                    btnText: (backend.uiTrigger, backend.getTextWithDefault("btn_manage", "Yönet"))
                    onClicked: backend.runUnRen() // Backend'de tanımlanmalı veya dialog açmalı
                }

                // --- Sağlık Kontrolü ---
                ToolCard {
                    title: (backend.uiTrigger, backend.getTextWithDefault("health_check_title", "Sağlık Kontrolü"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("diagnostics_desc", "Proje hatalarını, eksik dosyaları tara."))
                    icon: "🩺"
                     btnText: (backend.uiTrigger, backend.getTextWithDefault("run_check", "Taramayı Başlat"))
                    onClicked: backend.runHealthCheck()
                }

                // --- Font Kontrolü ---
                ToolCard {
                    title: (backend.uiTrigger, backend.getTextWithDefault("font_check_title", "Font Uyumluluğu"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("font_check_desc", "Seçilen dilin font tarafından desteklenip desteklenmediğini test et."))
                    icon: "🔤"
                    btnText: (backend.uiTrigger, backend.getTextWithDefault("font_check_now_button", "Test Et"))
                    onClicked: backend.runFontCheck()
                }

                // --- Otomatik Font Enjeksiyonu ---
                ToolCard {
                    title: "🅰️ " + (backend.uiTrigger, backend.getTextWithDefault("font_injector_title", "Otomatik Font Düzeltici"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("font_injector_desc", "Seçilen dil için uyumlu fontu indir ve oyuna entegre et (Kare karakterleri çözümler)."))
                    icon: "🪄"
                    btnText: (backend.uiTrigger, backend.getTextWithDefault("btn_fix_now", "Onar"))
                    onClicked: backend.autoInjectFont()
                }

                // --- Manuel Font Seçimi (YENİ) ---
                ToolCard {
                    title: "🔠 " + (backend.uiTrigger, backend.getTextWithDefault("font_manual_title", "Manuel Font Seçimi"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("font_manual_desc", "Otomatik eşleşme yerine listeden istediğiniz bir Google Fontunu seçip indirebilirsiniz."))
                    icon: "📑"
                    btnText: (backend.uiTrigger, backend.getTextWithDefault("btn_open", "Seç"))
                    onClicked: manualFontDialog.open()
                }

                // --- Runtime Hook Oluşturucu ---
                ToolCard {
                    title: "🪝 " + (backend.uiTrigger, backend.getTextWithDefault("tool_runtime_hook_title", "Runtime Hook Oluşturucu"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("settings_hook_desc", "Oyunun çevirileri tanıması için Runtime Hook modunu oluştur."))
                    icon: "🪄"
                    btnText: (backend.uiTrigger, backend.getTextWithDefault("generate_hook_btn", "Oluştur"))
                    onClicked: backend.generateRuntimeHook()
                }
                
                // --- Sözde Çeviri (Test) ---
                ToolCard {
                    title: (backend.uiTrigger, backend.getTextWithDefault("pseudo_engine_name", "Sözde Çeviri (Test)"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("pseudo_desc", "Test amaçlı rastgele karakterlerle çeviri yap (UI taşmalarını görmek için)."))
                    icon: "🧪"
                    btnText: (backend.uiTrigger, backend.getTextWithDefault("start", "Başlat"))
                    onClicked: {
                        backend.setEngine("pseudo")
                        backend.startTranslation()
                    }
                }

                // --- TL Klasörünü Çevir ---
                ToolCard {
                    title: "📂 " + (backend.uiTrigger, backend.getTextWithDefault("tl_translate_title", "TL Klasörünü Çevir"))
                    desc: (backend.uiTrigger, backend.getTextWithDefault("tl_translate_desc", "Oyunun 'tl' klasöründeki mevcut çeviri dosyalarını doğrudan çevirmeye yarar."))
                    icon: "🌐"
                    btnText: (backend.uiTrigger, backend.getTextWithDefault("btn_select_and_start", "Klasör Seç ve Başlat"))
                    onClicked: tlDialog.open()
                }
            }
        }
    }

    // Manuel Font Diyaloğu
    Dialog {
        id: manualFontDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("font_manual_title", "Manuel Font Seçimi"))
        anchors.centerIn: parent
        modal: true
        width: 400
        
        background: Rectangle { color: root.cardBackground; radius: 12; border.color: root.borderColor }
        header: Label { text: (backend.uiTrigger, backend.getTextWithDefault("font_manual_title", "Manuel Font Seçimi")); padding: 20; font.bold: true; color: root.mainTextColor; font.pixelSize: 18 }
        
        contentItem: ColumnLayout {
            spacing: 15
            Label { 
                text: (backend.uiTrigger, backend.getTextWithDefault("font_manual_desc", "Listeden bir font seçin:")); 
                color: root.secondaryTextColor; 
                wrapMode: Text.Wrap; 
                Layout.fillWidth: true 
            }
            
            ComboBox {
                id: manualFontCombo
                Layout.fillWidth: true
                model: backend.getGoogleFontsList()
                editable: true // Kullanıcı yazarak arayabilsin
            }
        }
        
        footer: DialogButtonBox {
            background: Rectangle { color: "transparent" }
            Button { text: (backend.uiTrigger, backend.getTextWithDefault("btn_cancel", "İptal")); DialogButtonBox.buttonRole: DialogButtonBox.RejectRole; flat: true }
            Button { 
                text: (backend.uiTrigger, backend.getTextWithDefault("btn_download_inject", "İndir ve Uygula")); 
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole; 
                highlighted: true
                onClicked: {
                    backend.manualInjectFont(manualFontCombo.currentText)
                    manualFontDialog.close()
                }
            }
        }
    }

    // TL Çeviri Diyaloğu
    Dialog {
        id: tlDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("tl_dialog_title", "TL Çevirisi"))
        anchors.centerIn: parent
        modal: true
        width: 450
        
        background: Rectangle { color: root.cardBackground; radius: 12; border.color: root.borderColor }
        header: Label { text: (backend.uiTrigger, backend.getTextWithDefault("tl_dialog_header", "📂 TL Klasörü Çevirisi")); padding: 20; font.bold: true; color: root.mainTextColor; font.pixelSize: 18 }
        
        contentItem: ColumnLayout {
            spacing: 15
            Label { text: (backend.uiTrigger, backend.getTextWithDefault("tl_select_folder_instruction", "Çevrilecek klasörü (örn: game/tl/turkish) seçin:")); color: root.secondaryTextColor; wrapMode: Text.Wrap; Layout.fillWidth: true }
            
            RowLayout {
                TextField { id: tlPathField; Layout.fillWidth: true; placeholderText: (backend.uiTrigger, backend.getTextWithDefault("path_not_selected_placeholder", "Yol seçilmedi...")); color: root.mainTextColor; background: Rectangle { color: root.inputBackground; border.color: root.borderColor; radius: 6 } }
                Button { text: "📁"; onClicked: tlPathDialog.open() }
            }
            
            RowLayout {
                Label { text: (backend.uiTrigger, backend.getTextWithDefault("target_lang_label", "Hedef Dil:")); color: root.secondaryTextColor; Layout.preferredWidth: 100 }
                ComboBox {
                    id: tlTargetCombo
                    Layout.fillWidth: true
                    model: backend.getTargetLanguages()
                    textRole: "name"
                    valueRole: "code"
                }
            }
        }
        
        footer: DialogButtonBox {
            background: Rectangle { color: "transparent" }
            Button { text: (backend.uiTrigger, backend.getTextWithDefault("btn_cancel", "İptal")); DialogButtonBox.buttonRole: DialogButtonBox.RejectRole; flat: true }
            Button { 
                text: (backend.uiTrigger, backend.getTextWithDefault("start_translation", "Çeviriyi Başlat")); DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole; highlighted: true
                onClicked: backend.startTLTranslation(tlPathField.text, tlTargetCombo.currentValue, "auto", "google", false)
            }
        }
    }

    FolderDialog {
        id: tlPathDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("select_tl_folder_title", "TL Klasörünü Seçin"))
        currentFolder: "file:///" + backend.get_app_path()
        onAccepted: tlPathField.text = selectedFolder.toString().replace("file:///", "")
    }

    component ToolCard: Rectangle {
        id: toolCardRoot
        property string title: ""
        property string desc: ""
        property string icon: ""
        property string btnText: (backend.uiTrigger, backend.getTextWithDefault("btn_open", "Aç"))
        signal clicked()

        width: 280
        height: 250
        radius: 12
        color: root.cardBackground
        border.color: actionButton.hovered ? Material.accent : root.borderColor
        border.width: actionButton.hovered ? 2 : 1
        
        Behavior on border.color { ColorAnimation { duration: 150 } }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            RowLayout {
                spacing: 15
                Layout.fillWidth: true
                Label { text: icon; font.pixelSize: 28; Layout.alignment: Qt.AlignVCenter }
                Label { 
                    text: title
                    font.bold: true
                    font.pixelSize: 16
                    color: root.mainTextColor
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    Layout.alignment: Qt.AlignVCenter
                }
            }
            
            Rectangle { Layout.fillWidth: true; height: 1; color: root.separatorColor }

            // Açıklama Metni (Esnek alan)
            Label { 
                text: desc; 
                color: root.secondaryTextColor; 
                font.pixelSize: 13; 
                Layout.fillWidth: true; 
                wrapMode: Text.Wrap; 
                Layout.fillHeight: true 
                verticalAlignment: Text.AlignTop
                elide: Text.ElideNone
                clip: true
            }

            // Buton (En altta)
            Button {
                id: actionButton
                // Use backend.isBusy to disable ALL tools when one is running + local visual timer
                text: (busyTimer.running || backend.isBusy) ? "..." : btnText
                enabled: !busyTimer.running && !backend.isBusy
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignBottom
                onClicked: {
                    toolCardRoot.clicked()
                    busyTimer.start()
                }
                highlighted: true
                Material.elevation: 0
                
                Timer {
                    id: busyTimer
                    interval: 1000 // Short visual feedback only
                    running: false
                }
                
                contentItem: Label {
                    text: parent.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                    font.bold: true
                }
            }
        }
    }
}
