// CachePage.qml - Çeviri Belleği (TM) Yöneticisi
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Rectangle {
    id: cachePage
    color: Material.background
    
    // Model: Backend'den çekilen cache verilerini tutar
    ListModel {
        id: cacheModel
    }

    function refreshData() {
        var filter = searchField.text
        cacheModel.clear()
        
        // Backend'den (snapshot) verilerini al
        var items = backend.getCacheEntries(filter)
        
        // Model'e ekle
        for(var i=0; i<items.length; i++) {
            cacheModel.append(items[i])
        }
    }
    
    // Sayfa görünür olduğunda veriyi yükle
    Component.onCompleted: refreshData()
    
    // Arama gecikmesi için Timer (her tuşta backend'e gitmemek için)
    Timer {
        id: searchTimer
        interval: 300
        repeat: false
        onTriggered: refreshData()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        // ==================== HEADER ====================
        RowLayout {
            Layout.fillWidth: true
            
            Label {
                text: "🧠 " + (backend.uiTrigger, backend.getTextWithDefault("nav_cache", "Çeviri Belleği (TM)"))
                font.pixelSize: 24
                font.bold: true
                color: root.mainTextColor
            }
            
            Item { Layout.fillWidth: true }
            
            Button {
                text: "🗑️ " + (backend.uiTrigger, backend.getTextWithDefault("btn_clear_cache", "Tümünü Temizle"))
                Material.background: Material.Red
                onClicked: clearConfirmDialog.open()
            }
        }
        
        // ==================== TOOLBAR (Search) ====================
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            
            TextField {
                id: searchField
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                placeholderText: (backend.uiTrigger, backend.getTextWithDefault("cache_search_placeholder", "Ara... (Orijinal, Çeviri, Motor)"))
                leftPadding: 16
                
                background: Rectangle {
                    color: root.inputBackground
                    radius: 8
                    border.color: searchField.activeFocus ? Material.accent : root.borderColor
                }
                
                onTextChanged: searchTimer.restart()
            }
            
            Button {
                text: "🔄"
                onClicked: refreshData()
                ToolTip.visible: hovered
                ToolTip.text: "Yenile"
            }
            
            Label {
                text: (backend.uiTrigger, backend.getTextWithDefault("total_cache", "Kayıt: {count}")).replace("{count}", cacheModel.count)
                color: root.secondaryTextColor
            }
        }

        // ==================== LIST VIEW ====================
        ListView {
            id: cacheList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: cacheModel
            spacing: 8
            
            delegate: Rectangle {
                width: ListView.view.width
                height: Math.max(80, columnContent.implicitHeight + 24)
                color: root.cardBackground
                radius: 8
                
                RowLayout {
                    id: columnContent
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12
                    
                    // Engine Badge
                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        width: 60
                        height: 24
                        radius: 4
                        color: {
                            if (model.engine.includes("google")) return "#4285F4"
                            if (model.engine.includes("deepl")) return "#0F2B46"
                            if (model.engine.includes("openai")) return "#10A37F"
                            if (model.engine.includes("gemini")) return "#8E44AD"
                            return "#555"
                        }
                        
                        Label {
                            anchors.centerIn: parent
                            text: model.engine.toUpperCase()
                            color: "white"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                    
                    // Texts
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4
                        
                        // Languages
                        Label {
                            text: model.source_lang + " ➔ " + model.target_lang
                            font.pixelSize: 10
                            color: root.mutedTextColor
                        }
                        
                        // Original
                        Label {
                            text: model.original
                            font.pixelSize: 13
                            color: root.mainTextColor
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                        
                        // Translated
                        Label {
                            text: model.translated
                            font.pixelSize: 13
                            color: Material.accent
                            font.italic: true
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true
                            maximumLineCount: 3
                            elide: Text.ElideRight
                        }
                    }
                    
                    // Actions
                    RowLayout {
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 0
                        
                        Button {
                            text: "✏️"
                            flat: true
                            onClicked: {
                                editDialog.engine = model.engine
                                editDialog.sourceLang = model.source_lang
                                editDialog.targetLang = model.target_lang
                                editDialog.original = model.original
                                editDialog.translation = model.translated
                                editDialog.open()
                            }
                        }
                        
                        Button {
                            text: "❌"
                            flat: true
                            onClicked: {
                                if (backend.deleteCacheEntry(model.engine, model.source_lang, model.target_lang, model.original)) {
                                    cacheModel.remove(index)
                                }
                            }
                        }
                    }
                }
            }
            
            ScrollBar.vertical: ScrollBar {
                active: true
            }
        }
    }
    
    // ==================== DIALOGS ====================
    Dialog {
        id: editDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("edit_cache_title", "Önbelleği Düzenle"))
        anchors.centerIn: parent
        modal: true
        width: 450
        
        property string engine: ""
        property string sourceLang: ""
        property string targetLang: ""
        property string original: ""
        property alias translation: translationField.text
        
        background: Rectangle { color: root.cardBackground; radius: 12; border.color: root.borderColor }
        header: Label { 
            text: title
            padding: 20
            font.bold: true
            font.pixelSize: 18
            color: root.mainTextColor 
        }
        
        contentItem: ColumnLayout {
            spacing: 15
            
            Label { text: (backend.uiTrigger, backend.getTextWithDefault("original_text", "Orijinal Metin")); color: root.secondaryTextColor }
            TextArea { 
                text: editDialog.original
                readOnly: true
                Layout.fillWidth: true
                Layout.preferredHeight: 60
                color: root.mutedTextColor
                background: Rectangle { color: root.inputBackground; radius: 6; border.color: root.borderColor }
                wrapMode: Text.Wrap
            }
            
            Label { text: (backend.uiTrigger, backend.getTextWithDefault("translated_text", "Çeviri")); color: root.secondaryTextColor }
            TextArea { 
                id: translationField
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                color: root.mainTextColor
                background: Rectangle { color: root.inputBackground; radius: 6; border.color: root.borderColor }
                wrapMode: Text.Wrap
            }
        }
        
        footer: DialogButtonBox {
            background: Rectangle { color: "transparent" }
            Button { 
                text: (backend.uiTrigger, backend.getTextWithDefault("btn_cancel", "İptal"))
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                flat: true 
            }
            Button { 
                text: (backend.uiTrigger, backend.getTextWithDefault("btn_save", "Kaydet"))
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                highlighted: true
                onClicked: {
                    if (backend.updateCacheEntry(editDialog.engine, editDialog.sourceLang, editDialog.targetLang, editDialog.original, editDialog.translation)) {
                        refreshData()
                    }
                }
            }
        }
    }

    Dialog {
        id: clearConfirmDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("confirm_clear_cache_title", "Önbelleği Temizle"))
        anchors.centerIn: parent
        modal: true
        standardButtons: Dialog.Yes | Dialog.No
        
        Text {
            text: (backend.uiTrigger, backend.getTextWithDefault("confirm_clear_cache_msg", "Tüm çeviri belleği silinecek. Bu işlem geri alınamaz.\nDevam etmek istiyor musunuz?"))
            color: root.mainTextColor
            padding: 20
        }
        
        onAccepted: {
            if (backend.clearCache()) {
                refreshData()
            }
        }
    }
}
