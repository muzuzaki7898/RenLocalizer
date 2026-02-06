// GlossaryPage.qml - Sözlük Yönetimi Sayfası (Full Logic)
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs

Rectangle {
    id: glossaryPage
    color: Material.background
    
    // Model: Backend'den çekilen veriyi tutar
    ListModel {
        id: glossaryModel
    }

    // Backend iletişimi ve veri yenileme
    function refreshData() {
        glossaryModel.clear()
        var items = backend.getGlossaryItems()
        for(var i=0; i<items.length; i++) {
            glossaryModel.append(items[i])
        }
    }

    Component.onCompleted: refreshData()
    
    // Backend loglarını dinle, gerekirse refresh yap
    Connections {
        target: backend
        function onLogMessage(level, msg) {
            // Refresh on any glossary-related action (language-independent keywords)
            var lowerMsg = msg.toLowerCase()
            if (lowerMsg.includes("glossary") || lowerMsg.includes("terim") || lowerMsg.includes("sözlük") ||
                lowerMsg.includes("added") || lowerMsg.includes("translated") || lowerMsg.includes("removed") ||
                lowerMsg.includes("eklendi") || lowerMsg.includes("çevrildi") || lowerMsg.includes("silindi")) {
                refreshData()
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 20

        // ==================== HEADER ====================
        RowLayout {
            Layout.fillWidth: true
            
            Label {
                text: "📚 " + (backend.uiTrigger, backend.getTextWithDefault("nav_glossary", "Glossary Management"))
                font.pixelSize: 24
                font.bold: true
                color: root.mainTextColor
            }
            
            Item { Layout.fillWidth: true }
            
            Button {
                text: "✨ " + (backend.uiTrigger, backend.getTextWithDefault("glossary_extract_btn", "Auto Extract"))
                onClicked: {
                    var result = backend.extractGlossaryTerms()
                    // Sonuç zaten logMessage ile geliyor ama direkt de gösterebiliriz
                    if (result.includes("Hata") || result.includes("Error")) {
                        console.error(result)
                    }
                }
                Material.background: Material.BlueGrey
            }
            
            Button {
                text: "➕ " + (backend.uiTrigger, backend.getTextWithDefault("edit_add", "Add"))
                highlighted: true
                onClicked: addDialog.open()
            }
        }
        
        // ==================== TOOLBAR ====================
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            
            Button {
                text: "🔄 " + (backend.uiTrigger, backend.getTextWithDefault("btn_translate_empty", "Translate Empty"))
                onClicked: backend.translateEmptyGlossaryItems()
                flat: true
            }
            
            Button {
                text: "📝 " + (backend.uiTrigger, backend.getTextWithDefault("btn_copy_source", "Copy Source"))
                onClicked: backend.fillEmptyGlossaryWithSource()
                flat: true
            }
            
            Item { Layout.fillWidth: true }
            
            Label {
                text: (backend.uiTrigger, backend.getTextWithDefault("total_count_label", "Total: {count}")).replace("{count}", glossaryModel.count)
                color: "#666"
                font.pixelSize: 12
            }
        }
        
        // ==================== EXPORT/IMPORT TOOLBAR ====================
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            
            Button {
                text: "📤 " + (backend.uiTrigger, backend.getTextWithDefault("btn_export_glossary", "Export"))
                flat: true
                onClicked: exportDialog.open()
            }
            
            Button {
                text: "📥 " + (backend.uiTrigger, backend.getTextWithDefault("btn_import_glossary", "Import"))
                flat: true
                onClicked: importDialog.open()
            }
        }

        // ==================== TABLE HEADERS ====================
        Rectangle {
            Layout.fillWidth: true
            height: 40
            color: root.cardBackground
            radius: 8
            
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 10
                
                Label { text: (backend.uiTrigger, backend.getTextWithDefault("glossary_source", "Source Text")); color: root.secondaryTextColor; font.bold: true; Layout.preferredWidth: 250 }
                Rectangle { width: 1; height: 20; color: root.separatorColor }
                Label { text: (backend.uiTrigger, backend.getTextWithDefault("glossary_target", "Translation")); color: root.secondaryTextColor; font.bold: true; Layout.fillWidth: true }
                Rectangle { width: 1; height: 20; color: root.separatorColor }
                Label { text: (backend.uiTrigger, backend.getTextWithDefault("action", "Action")); color: root.secondaryTextColor; font.bold: true; Layout.preferredWidth: 60 }
            }
        }

        // ==================== LIST (TABLE BODY) ====================
        ListView {
            id: glossaryList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: glossaryModel
            spacing: 6
            
            delegate: Rectangle {
                width: ListView.view.width
                height: 50
                color: index % 2 === 0 ? root.inputBackground : root.cardBackground
                radius: 6
                border.width: 0
                
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 10
                    
                    // Source
                    Label { 
                        text: model.source
                        color: root.mainTextColor
                        font.bold: true
                        Layout.preferredWidth: 250
                        elide: Text.ElideRight 
                    }
                    
                    Rectangle { width: 1; height: 30; color: root.separatorColor }
                    
                    // Target (Editable-like look but currently view-only in list, edit via delete/re-add for MVP)
                    Label { 
                        text: model.target ? model.target : (backend.uiTrigger, backend.getTextWithDefault("empty_placeholder", "<empty>"))
                        color: model.target ? Material.accent : "#555"
                        font.italic: !model.target
                        Layout.fillWidth: true
                        elide: Text.ElideRight 
                    }
                    
                    Rectangle { width: 1; height: 30; color: root.separatorColor }
                    
                    // Delete Button
                    Button {
                        text: "❌"
                        flat: true
                        Layout.preferredWidth: 40
                        onClicked: {
                            backend.removeGlossaryItem(model.source)
                            glossaryModel.remove(index)
                        }
                    }
                }
            }
        }
    }
    
    // ==================== ADD DIALOG ====================
    Dialog {
        id: addDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("glossary_add_title", "Add Term"))
        anchors.centerIn: parent
        modal: true
        width: 400
        
        property alias sourceText: sourceField.text
        property alias targetText: targetField.text
        
        onOpened: {
            sourceField.text = ""
            targetField.text = ""
            sourceField.forceActiveFocus()
        }
        
        background: Rectangle { color: root.cardBackground; radius: 12; border.color: root.borderColor }
        header: Label { 
            text: (backend.uiTrigger, backend.getTextWithDefault("glossary_add_title", "Add Term"))
            padding: 20
            font.bold: true
            font.pixelSize: 18
            color: root.mainTextColor 
        }
        
        contentItem: ColumnLayout {
            spacing: 15
            
            Label { text: (backend.uiTrigger, backend.getTextWithDefault("glossary_source_hint", "Source (e.g. Sword)")); color: root.secondaryTextColor }
            TextField { 
                id: sourceField
                Layout.fillWidth: true
                color: root.mainTextColor 
                background: Rectangle { color: root.inputBackground; radius: 6; border.color: root.borderColor }
            }
            
            Label { text: (backend.uiTrigger, backend.getTextWithDefault("glossary_target_hint", "Translation (e.g. Sword Translation)")); color: root.secondaryTextColor }
            TextField { 
                id: targetField
                Layout.fillWidth: true
                color: root.mainTextColor
                background: Rectangle { color: root.inputBackground; radius: 6; border.color: root.borderColor }
            }
        }
        
        footer: DialogButtonBox {
            background: Rectangle { color: "transparent" }
            Button { 
                text: (backend.uiTrigger, backend.getTextWithDefault("btn_cancel", "Cancel"))
                DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
                flat: true 
            }
            Button { 
                text: (backend.uiTrigger, backend.getTextWithDefault("btn_save", "Save"))
                DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
                highlighted: true

                onClicked: {
                    backend.addGlossaryItem(addDialog.sourceText, addDialog.targetText)
                    refreshData() // Listeyi güncelle
                }
            }
        }
    }


    // ==================== FILE DIALOGS ====================
    FileDialog {
        id: importDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("dialog_import_glossary", "Import Glossary"))
        nameFilters: ["Data Files (*.xlsx *.xls *.csv *.json)", "Excel Files (*.xlsx *.xls)", "CSV Files (*.csv)", "JSON Files (*.json)", "All Files (*)"]
        fileMode: FileDialog.OpenFile
        onAccepted: {
            var msg = backend.importGlossary(importDialog.selectedFile.toString())
            if (msg === "") {
                 refreshData()
            }
        }
    }

    FileDialog {
        id: exportDialog
        title: (backend.uiTrigger, backend.getTextWithDefault("dialog_export_glossary", "Export Glossary"))
        nameFilters: ["Excel Files (*.xlsx)", "CSV Files (*.csv)", "JSON Files (*.json)"]
        fileMode: FileDialog.SaveFile
        defaultSuffix: "xlsx"
        onAccepted: {
            // Determine format from filter or extension
            var path = exportDialog.selectedFile.toString()
            var format = "xlsx" // default
            if (path.endsWith(".csv")) format = "csv"
            else if (path.endsWith(".json")) format = "json"
            else if (path.endsWith(".xlsx")) format = "xlsx"
            
            backend.exportGlossary(path, format)
        }
    }
}
