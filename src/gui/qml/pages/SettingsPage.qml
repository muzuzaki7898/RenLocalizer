// SettingsPage.qml - Ayarlar Sayfası (Full Feature Restoration)
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Rectangle {
    id: settingsPage
    color: Material.background

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        contentHeight: settingsColumn.height + 60
        ScrollBar.vertical.policy: ScrollBar.AlwaysOn

        ColumnLayout {
            id: settingsColumn
            width: Math.min(parent.width - 48, 1000)
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.margins: 24
            spacing: 24

            Label {
                text: "⚙️ " + (backend.uiTrigger, backend.getTextWithDefault("nav_settings", "Ayarlar"))
                font.pixelSize: 28
                font.bold: true
                color: root.mainTextColor
            }

            // ==================== GENEL AYARLAR ====================
            SettingsGroup {
                title: "🌐 " + (backend.uiTrigger, backend.getTextWithDefault("settings_general", "Genel Ayarlar"))
                
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    SettingsRow {
                        label: (backend.uiTrigger, backend.getTextWithDefault("ui_language_label", "Uygulama Dili:"))
                        ComboBox {
                            Layout.fillWidth: true
                            model: settingsBackend.getAvailableUILanguages()
                            textRole: "name"
                            valueRole: "code"
                            currentIndex: findIndex(model, settingsBackend.currentLanguage)
                            onActivated: settingsBackend.setUILanguage(currentValue)
                            
                            function findIndex(model, value) {
                                for(var i=0; i<model.length; i++) if(model[i].code === value) return i;
                                return 0;
                            }
                        }
                    }

                    SettingsRow {
                        label: (backend.uiTrigger, backend.getTextWithDefault("theme_menu", "Tema:"))
                        ComboBox {
                            Layout.fillWidth: true
                            model: settingsBackend.getAvailableThemes()
                            textRole: "name"
                            valueRole: "code"
                            currentIndex: findIndex(model, settingsBackend.currentTheme)
                            onActivated: settingsBackend.setTheme(currentValue)
                            
                            function findIndex(model, value) {
                                for(var i=0; i<model.length; i++) if(model[i].code === value) return i;
                                return 0;
                            }
                        }
                    }
                    
                    CheckBox {
                        checked: settingsBackend.getCheckUpdates()
                        onCheckedChanged: settingsBackend.setCheckUpdates(checked)
                        text: (backend.uiTrigger, backend.getTextWithDefault("check_updates", "Güncellemeleri Otomatik Denetle"))
                    }

                    Button {
                        text: "🔄 " + (backend.uiTrigger, backend.getTextWithDefault("check_updates_now_button", "Şimdi Güncellemeleri Denetle"))
                        onClicked: backend.checkForUpdates(true)
                        Layout.preferredHeight: 40
                        background: Rectangle {
                            radius: 8
                            color: parent.down ? Qt.darker(Material.accent, 1.2) : parent.hovered ? Qt.darker(Material.accent, 1.1) : Material.accent
                            border.color: root.borderColor
                        }
                    }
                }
            }

            // ==================== ÇEVİRİ FİLTRELERİ ====================
            SettingsGroup {
                title: "🔍 " + (backend.uiTrigger, backend.getTextWithDefault("translation_filters", "Neler Çevrilsin?"))
                
                GridLayout {
                    columns: 2
                    Layout.fillWidth: true
                    rowSpacing: 10
                    columnSpacing: 20

                    FilterCheck { key: "dialogue"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_dialogue_label", "Diyaloglar")) }
                    FilterCheck { key: "menu"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_menu_label", "Menü Seçenekleri")) }
                    FilterCheck { key: "buttons"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_buttons_label", "Butonlar")) }
                    FilterCheck { key: "notifications"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_notifications_label", "Bildirimler")) }
                    FilterCheck { key: "alt_text"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_alt_text_label", "Alternatif Metinler")) }
                    FilterCheck { key: "confirmations"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_confirmations_label", "Onay Diyalogları")) }
                    FilterCheck { key: "input_text"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_input_label", "Giriş Kutuları")) }
                    FilterCheck { key: "ui"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_ui_label", "UI Metinleri")) }
                    FilterCheck { key: "gui_strings"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_gui_label", "GUI Stringleri")) }
                    FilterCheck { key: "style_strings"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_style_label", "Stil Metinleri")) }
                    FilterCheck { key: "renpy_functions"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_renpy_func_label", "Ren'Py Fonksiyonları")) }
                    FilterCheck { key: "config_strings"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_config_label", "Config Stringleri")) }
                    FilterCheck { key: "define_strings"; label: (backend.uiTrigger, backend.getTextWithDefault("translate_define_label", "Define Stringleri")) }
                }
            }

            // ==================== API AYARLARI ====================
            SettingsGroup {
                title: "🔑 " + (backend.uiTrigger, backend.getTextWithDefault("api_keys", "API Anahtarları"))
                
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 20
                    
                    // Google API Key (Opsiyonel)
                    ApiField { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("google_api_title", "Google API Key (Opsiyonel)")); 
                        text: settingsBackend.getGoogleApiKey ? settingsBackend.getGoogleApiKey() : ""; 
                        onChanged: (newValue) => { if(settingsBackend.setGoogleApiKey) settingsBackend.setGoogleApiKey(newValue) }
                    }
                    
                    // DeepL API Key
                    ColumnLayout {
                        spacing: 8
                        Label { text: (backend.uiTrigger, backend.getTextWithDefault("deepl_api_title", "DeepL API Key:")); color: root.secondaryTextColor }
                        TextField {
                            Layout.fillWidth: true
                            echoMode: TextInput.Password
                            text: settingsBackend.getDeepLApiKey()
                            onTextChanged: settingsBackend.setDeepLApiKey(text)
                            placeholderText: (backend.uiTrigger, backend.getTextWithDefault("deepl_api_key_placeholder", "API Key (sk-...) or (free:...)"))
                            background: Rectangle { radius: 8; color: root.inputBackground; border.color: root.borderColor }
                        }
                    }
                    
                    RowLayout {
                        spacing: 12
                        Label { text: (backend.uiTrigger, backend.getTextWithDefault("deepl_formality_label", "DeepL Hitap:")); color: root.secondaryTextColor; Layout.preferredWidth: 150 }
                        ComboBox {
                            Layout.fillWidth: true
                            model: [
                                {code: "default", name: (backend.uiTrigger, backend.getTextWithDefault("formality_default", "Varsayılan"))},
                                {code: "formal", name: (backend.uiTrigger, backend.getTextWithDefault("formality_formal", "Resmi"))},
                                {code: "informal", name: (backend.uiTrigger, backend.getTextWithDefault("formality_informal", "Samimi"))}
                            ]
                            textRole: "name"
                            valueRole: "code"
                            currentIndex: findIndex(model, settingsBackend.getDeepLFormality())
                            onActivated: settingsBackend.setDeepLFormality(currentValue)
                            function findIndex(model, value) {
                                for(var i=0; i<model.length; i++) if(model[i].code === value) return i;
                                return 0;
                            }
                        }
                    }

                    // OpenAI / OpenRouter Section
                    Label { text: "🤖 OpenAI / OpenRouter / DeepSeek"; font.bold: true; color: root.mainTextColor; Layout.topMargin: 10 }
                    
                    // Preset ComboBox
                    RowLayout {
                        spacing: 12
                        Label { text: (backend.uiTrigger, backend.getTextWithDefault("preset_label", "Preset:")); color: root.secondaryTextColor; Layout.preferredWidth: 80 }
                        ComboBox {
                            id: openaiPresetCombo
                            Layout.fillWidth: true
                            model: settingsBackend.getOpenAIPresets()
                            textRole: "name"
                            onActivated: {
                                var result = settingsBackend.applyOpenAIPreset(currentText)
                                var data = JSON.parse(result)
                                openaiModelField.text = data.model
                                openaiBaseUrlField.text = data.url
                            }
                        }
                    }
                    
                    ApiField { 
                        id: openaiApiKeyField
                        label: "API Key"; 
                        text: settingsBackend.getOpenAIApiKey(); 
                        onChanged: (newValue) => settingsBackend.setOpenAIApiKey(newValue) 
                    }
                    RowLayout {
                        spacing: 12
                        TextField {
                            id: openaiModelField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            placeholderText: text.length > 0 ? "" : (backend.uiTrigger, backend.getTextWithDefault("placeholder_openai_model", "Model (örn: gpt-3.5-turbo)"))
                            text: settingsBackend.getOpenAIModel()
                            onEditingFinished: settingsBackend.setOpenAIModel(text)
                            leftPadding: 12
                            rightPadding: 12
                            color: root.mainTextColor
                            verticalAlignment: TextInput.AlignVCenter
                            background: Rectangle { radius: 8; color: root.inputBackground; border.color: root.borderColor }
                            placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.45)
                        }
                        TextField {
                            id: openaiBaseUrlField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            placeholderText: text.length > 0 ? "" : (backend.uiTrigger, backend.getTextWithDefault("placeholder_openai_base_url", "Base URL (Opsiyonel)"))
                            text: settingsBackend.getOpenAIBaseUrl()
                            onEditingFinished: settingsBackend.setOpenAIBaseUrl(text)
                            leftPadding: 12
                            rightPadding: 12
                            color: root.mainTextColor
                            verticalAlignment: TextInput.AlignVCenter
                            background: Rectangle { radius: 8; color: root.inputBackground; border.color: root.borderColor }
                            placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.45)
                        }
                    }

                    // Gemini Section
                    Label { text: "✨ Google Gemini"; font.bold: true; color: root.mainTextColor; Layout.topMargin: 10 }
                    ApiField { 
                        label: "Gemini API Key"; 
                        text: settingsBackend.getGeminiApiKey(); 
                        onChanged: (newValue) => settingsBackend.setGeminiApiKey(newValue) 
                    }
                    RowLayout {
                        spacing: 12
                        TextField {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            placeholderText: text.length > 0 ? "" : (backend.uiTrigger, backend.getTextWithDefault("placeholder_gemini_model", "Model (örn: gemini-2.0-flash)"))
                            text: settingsBackend.getGeminiModel()
                            onEditingFinished: settingsBackend.setGeminiModel(text)
                            leftPadding: 12
                            rightPadding: 12
                            color: root.mainTextColor
                            verticalAlignment: TextInput.AlignVCenter
                            background: Rectangle { radius: 8; color: root.inputBackground; border.color: root.borderColor }
                            placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.45)
                        }
                        ComboBox {
                            Layout.preferredWidth: 200
                            model: [
                                {code: "BLOCK_NONE", name: (backend.uiTrigger, backend.getTextWithDefault("gemini_safety_none", "Kapalı"))},
                                {code: "BLOCK_ONLY_HIGH", name: (backend.uiTrigger, backend.getTextWithDefault("gemini_safety_high", "Yüksek"))},
                                {code: "BLOCK_MEDIUM_AND_ABOVE", name: (backend.uiTrigger, backend.getTextWithDefault("gemini_safety_medium", "Orta"))},
                                {code: "BLOCK_LOW_AND_ABOVE", name: (backend.uiTrigger, backend.getTextWithDefault("gemini_safety_low", "Düşük"))}
                            ]
                            textRole: "name"
                            valueRole: "code"
                            currentIndex: findIndex(model, settingsBackend.getGeminiSafety())
                            onActivated: settingsBackend.setGeminiSafety(currentValue)
                            function findIndex(model, value) {
                                for(var i=0; i<model.length; i++) if(model[i].code === value) return i;
                                return 0;
                            }
                        }
                    }
                }
            }

            // ==================== PERFORMANS & TEKNİK ====================
            SettingsGroup {
                title: "⚙️ " + (backend.uiTrigger, backend.getTextWithDefault("settings_advanced", "Gelişmiş & Performans"))
                
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16
                    
                    RowLayout {
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("batch_size_label", "Batch Boyutu:")); Layout.fillWidth: true;
                            SpinBox { from: 1; to: 1000; value: settingsBackend.getBatchSize(); onValueChanged: settingsBackend.setBatchSize(value); editable: true }
                        }
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("concurrent_threads_label", "Eş Zamanlı Thread:")); Layout.fillWidth: true;
                            SpinBox { from: 1; to: 64; value: settingsBackend.getConcurrentThreads(); onValueChanged: settingsBackend.setConcurrentThreads(value); editable: true }
                        }
                    }

                    RowLayout {
                         CheckBox { 
                             text: (backend.uiTrigger, backend.getTextWithDefault("use_multi_endpoint_label", "Çoklu Endpoint Kullan"))
                             checked: settingsBackend.getUseMultiEndpoint() 
                             onCheckedChanged: settingsBackend.setUseMultiEndpoint(checked) 
                         }
                         CheckBox { 
                             text: (backend.uiTrigger, backend.getTextWithDefault("enable_lingva_fallback_label", "Lingva Fallback"))
                             checked: settingsBackend.getEnableLingvaFallback() 
                             onCheckedChanged: settingsBackend.setEnableLingvaFallback(checked) 
                         }
                    }

                    RowLayout {
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("chunk_size_label", "Bağlam (Context) Sınırı:")); Layout.fillWidth: true;
                            SpinBox { from: 0; to: 50; value: settingsBackend.getContextLimit(); onValueChanged: settingsBackend.setContextLimit(value); editable: true }
                        }
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("max_chars_label", "Maksimum Karakter:")); Layout.fillWidth: true;
                             SpinBox { from: 1000; to: 50000; stepSize: 1000; value: settingsBackend.getMaxCharsPerRequest(); onValueChanged: settingsBackend.setMaxCharsPerRequest(value); editable: true }
                        }
                    }


                    RowLayout {
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("request_delay_label", "İstek Gecikmesi (sn):")); Layout.fillWidth: true;
                            // Backend expects float, but SpinBox works with Int. 
                            // Using DoubleSpinBox logic: value 10 = 0.1s
                            DoubleSpinBox { 
                                from: 0; to: 1000; stepSize: 10 
                                value: settingsBackend.getRequestDelay() * 100 
                                onValueChanged: settingsBackend.setRequestDelay(value / 100.0) 
                                editable: true 
                            }
                        }
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("timeout_label", "Zaman Aşımı (sn):")); Layout.fillWidth: true;
                            SpinBox { from: 5; to: 300; value: settingsBackend.getTimeout(); onValueChanged: settingsBackend.setTimeout(value); editable: true }
                        }
                    }

                    RowLayout {
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("max_retries_label", "Maksimum Deneme:")); Layout.fillWidth: true;
                             SpinBox { from: 0; to: 10; value: settingsBackend.getMaxRetries(); onValueChanged: settingsBackend.setMaxRetries(value); editable: true }
                        }
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("deep_scan", "Derin Tarama"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("deep_scan_desc", ""))
                        checked: settingsBackend.getEnableDeepScan()
                        onToggled: (isChecked) => settingsBackend.setEnableDeepScan(isChecked)
                    }
                    
                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("enable_rpyc_reader_label", "RPYC Okuyucu"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("rpyc_reader_desc", ""))
                        checked: settingsBackend.getEnableRpycReader()
                        onToggled: (isChecked) => settingsBackend.setEnableRpycReader(isChecked)
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("scan_rpym_files", ".rpym Dosyalarını Tara"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("scan_rpym_files_desc", ""))
                        checked: settingsBackend.getScanRpymFiles()
                        onToggled: (isChecked) => settingsBackend.setScanRpymFiles(isChecked)
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("use_cache_label", "Çeviri Belleğini Kullan"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("use_cache_desc", ""))
                        checked: settingsBackend.getUseCache()
                        onToggled: (isChecked) => settingsBackend.setUseCache(isChecked)
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("use_global_cache", "Global Çeviri Belleği (Taşınabilir)"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("use_global_cache_desc", ""))
                        checked: settingsBackend.getUseGlobalCache()
                        onToggled: (isChecked) => settingsBackend.setUseGlobalCache(isChecked)
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("exclude_system_folders", "Sistem Klasörlerini Dışla"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("exclude_system_folders_desc", ""))
                        checked: settingsBackend.getExcludeSystemFolders()
                        onToggled: (isChecked) => settingsBackend.setExcludeSystemFolders(isChecked)
                    }
                    
                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("aggressive_retry", "Agresif Çeviri"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("aggressive_retry_desc", ""))
                        checked: settingsBackend.getAggressiveRetry()
                        onToggled: (isChecked) => settingsBackend.setAggressiveRetry(isChecked)
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("force_runtime", "Zorla Çeviri (Force Translate)"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("force_runtime_desc", ""))
                        checked: settingsBackend.getForceRuntime()
                        onToggled: (isChecked) => settingsBackend.setForceRuntime(isChecked)
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("show_debug_engines", "Geliştirici Araçlarını Göster"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("show_debug_engines_desc", ""))
                        checked: settingsBackend.getShowDebugEngines()
                        onToggled: (isChecked) => settingsBackend.setShowDebugEngines(isChecked)
                    }

                    DescriptiveCheck {
                        label: (backend.uiTrigger, backend.getTextWithDefault("auto_hook_gen", "Çeviri Sonrası Otomatik Oluştur"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("auto_hook_gen_desc", ""))
                        checked: settingsBackend.getAutoHook()
                        onToggled: (isChecked) => settingsBackend.setAutoHook(isChecked)
                    }

                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("auto_unren", "Otomatik RPA Çıkarımı"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("auto_unren_desc", ""))
                        checked: settingsBackend.getAutoUnren()
                        onToggled: (isChecked) => settingsBackend.setAutoUnren(isChecked)
                    }
                }
            }

            // ==================== PROXY AYARLARI ====================
            SettingsGroup {
                title: "🌐 " + (backend.uiTrigger, backend.getTextWithDefault("group_proxy", "Proxy Ayarları"))
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 12
                    DescriptiveCheck { 
                        label: (backend.uiTrigger, backend.getTextWithDefault("proxy_enabled", "Proxy Kullan"))
                        description: (backend.uiTrigger, backend.getTextWithDefault("enable_proxy_tooltip", ""))
                        checked: settingsBackend.getProxyEnabled()
                        onToggled: (isChecked) => settingsBackend.setProxyEnabled(isChecked)
                    }
                    TextField {
                        Layout.fillWidth: true
                        placeholderText: "Örn: http://user:pass@host:port"
                        text: settingsBackend.getProxyUrl()
                        onEditingFinished: settingsBackend.setProxyUrl(text)
                        leftPadding: 12
                        rightPadding: 12
                        color: root.mainTextColor
                        background: Rectangle { 
                            color: root.inputBackground
                            radius: 8
                            border.color: root.borderColor
                            border.width: 1
                        }
                    }

                    // Manual Proxies
                    Label { 
                        text: (backend.uiTrigger, backend.getTextWithDefault("manual_proxies", "Manuel Proxyler (Her satıra bir tane):")) 
                        color: "#ccc"
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.max(120, manualProxyArea.contentHeight + 24)
                        color: root.inputBackground
                        radius: 8
                        border.color: root.borderColor
                        border.width: 1

                        ScrollView {
                            anchors.fill: parent
                            clip: true
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded

                            TextArea {
                                id: manualProxyArea
                                text: settingsBackend.getManualProxies()
                                placeholderText: "ipp:port\nuser:pass@ip:port"
                                color: root.mainTextColor
                                font.pixelSize: 13
                                wrapMode: TextEdit.NoWrap
                                leftPadding: 12
                                rightPadding: 12
                                topPadding: 12
                                bottomPadding: 12
                                selectByMouse: true
                                background: null // Container handles the background
                                
                                onEditingFinished: settingsBackend.setManualProxies(text)
                                
                                // Placeholder style fix
                                placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.35)
                            }
                        }
                    }

                    // Refresh Button & Status
                    RowLayout {
                        Button {
                            id: proxyRefreshBtn
                            text: (backend.uiTrigger, backend.getTextWithDefault("refresh_proxies", "Proxy Listesini Yenile"))
                            onClicked: {
                                enabled = false
                                proxyStatusLabel.text = "Yenileniyor..."
                                proxyStatusLabel.color = "#f39c12" // orange
                                settingsBackend.refreshProxies()
                            }
                        }
                        Label {
                            id: proxyStatusLabel
                            text: ""
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                        }
                    }

                    Connections {
                        target: settingsBackend
                        function onProxyRefreshFinished(success, msg) {
                            proxyRefreshBtn.enabled = true
                            proxyStatusLabel.text = msg
                            proxyStatusLabel.color = success ? "#2ecc71" : "#e74c3c"
                        }
                    }
                }
            }

            // ==================== YEREL LLM ====================
            // ... (Already mostly there, but adding some layout polish)
            SettingsGroup {
                title: "🖥️ " + (backend.uiTrigger, backend.getTextWithDefault("settings_local_llm_title", "Yerel LLM Ayarları"))
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 15
                    RowLayout {
                         Label { text: (backend.uiTrigger, backend.getTextWithDefault("local_llm_preset_label", "Preset:")); color: "#ccc"; Layout.preferredWidth: 100 }
                         ComboBox {
                             Layout.fillWidth: true
                             model: settingsBackend.getLocalLLMPresets()
                             textRole: "name"
                             onActivated: {
                                 var result = settingsBackend.applyLocalLLMPreset(currentText)
                                 var data = JSON.parse(result)
                                 llmUrlField.text = data.url
                                 llmModelField.text = data.model
                             }
                         }
                    }
                    TextField { 
                        id: llmUrlField; 
                        Layout.fillWidth: true; 
                        Layout.preferredHeight: 40
                        text: settingsBackend.getLocalLLMUrl(); 
                        onEditingFinished: settingsBackend.setLocalLLMUrl(text); 
                        placeholderText: text.length > 0 ? "" : "Sunucu URL"
                        leftPadding: 12; rightPadding: 12; color: root.mainTextColor
                        verticalAlignment: TextInput.AlignVCenter
                        background: Rectangle { radius: 8; color: root.inputBackground; border.color: root.borderColor }
                        placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.45)
                    }
                    TextField { 
                        id: llmModelField; 
                        Layout.fillWidth: true; 
                        Layout.preferredHeight: 40
                        text: settingsBackend.getLocalLLMModel(); 
                        onEditingFinished: settingsBackend.setLocalLLMModel(text); 
                        placeholderText: text.length > 0 ? "" : "Model Adı"
                        leftPadding: 12; rightPadding: 12; color: root.mainTextColor
                        verticalAlignment: TextInput.AlignVCenter
                        background: Rectangle { radius: 8; color: root.inputBackground; border.color: root.borderColor }
                        placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.45)
                    }
                    
                    RowLayout {
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("local_llm_timeout_label", "Zaman Aşımı (sn):")); Layout.fillWidth: true;
                            SpinBox { from: 10; to: 600; value: settingsBackend.getLocalLLMTimeout(); onValueChanged: settingsBackend.setLocalLLMTimeout(value); editable: true }
                        }
                    }

                    Button {
                        text: "🔌 " + (backend.uiTrigger, backend.getTextWithDefault("test_local_llm_connection", "Bağlantıyı Test Et"))
                        Layout.fillWidth: true; highlighted: true
                        onClicked: testResultLabel.text = settingsBackend.testLocalLLMConnection()
                    }
                    Label { id: testResultLabel; Layout.fillWidth: true; color: text.includes("Success") ? "#6bcb77" : "#ff6b6b"; wrapMode: Text.Wrap }
                }
            }

            // ==================== AI MODEL PARAMETRELERİ ====================
            SettingsGroup {
                title: "🎛️ AI " + (backend.uiTrigger, backend.getTextWithDefault("settings_ai_model_params", "Model Parametreleri"))
                
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 16
                    
                    // AI Uyarı Mesajları
                    Rectangle {
                        Layout.fillWidth: true
                        height: warningCol.height + 16
                        radius: 8
                        color: "#2d1a1a"
                        border.color: "#e74c3c"
                        
                        ColumnLayout {
                            id: warningCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8
                            spacing: 4
                            Label { text: (backend.uiTrigger, backend.getTextWithDefault("ai_hallucination_warning", "⚠️ DİKKAT: Küçük modeller halüsinasyon gösterebilir.")); color: "#e74c3c"; font.pixelSize: 12; wrapMode: Text.Wrap }
                            Label { text: (backend.uiTrigger, backend.getTextWithDefault("ai_vram_warning", "⚠️ DİKKAT: Yerel LLM için 4GB+ VRAM önerilir.")); color: "#e74c3c"; font.pixelSize: 12; wrapMode: Text.Wrap }
                            Label { text: (backend.uiTrigger, backend.getTextWithDefault("ai_source_lang_warning", "💡 İPUCU: Kaynak dili belirtmek çeviri kalitesini artırır.")); color: "#3498db"; font.pixelSize: 12; wrapMode: Text.Wrap }
                        }
                    }
                    
                    // Sıcaklık (Temperature)
                    ColumnLayout {
                        Layout.fillWidth: true
                        RowLayout {
                             Label { text: (backend.uiTrigger, backend.getTextWithDefault("ai_creativity_label", "Yaratıcılık (Temperature):")); color: "#ccc" }
                             Label { text: tempSlider.value.toFixed(1); color: Material.accent; font.bold: true }
                        }
                        Slider {
                            id: tempSlider
                            Layout.fillWidth: true
                            from: 0.0
                            to: 2.0
                            value: settingsBackend.getAITemperature()
                            onMoved: settingsBackend.setAITemperature(value)
                        }
                    }

                    // Tokens & Timeout
                    RowLayout {
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("ai_tokens_short", "Max Tokens:")); Layout.fillWidth: true;
                            SpinBox { from: 256; to: 128000; stepSize: 256; value: settingsBackend.getAIMaxTokens(); onValueChanged: settingsBackend.setAIMaxTokens(value); editable: true }
                        }
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("local_llm_timeout_label", "Zaman Aşımı (sn):")); Layout.fillWidth: true;
                            SpinBox { from: 10; to: 300; value: settingsBackend.getAITimeout(); onValueChanged: settingsBackend.setAITimeout(value); editable: true }
                        }
                    }

                    // AI Batch & Concurrency (New!)
                    RowLayout {
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("ai_batch_important_label", "AI Batch Boyutu:")); Layout.fillWidth: true;
                            SpinBox { 
                                from: 1; to: 100; 
                                value: settingsBackend.getAIBatchSize(); 
                                onValueChanged: settingsBackend.setAIBatchSize(value); 
                                editable: true 
                            }
                        }
                        SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("ai_parallel_label", "AI Paralel İstek:")); Layout.fillWidth: true;
                            SpinBox { from: 1; to: 10; value: settingsBackend.getAIConcurrency(); onValueChanged: settingsBackend.setAIConcurrency(value); editable: true }
                        }
                    }

                    RowLayout {
                         SettingsRow { label: (backend.uiTrigger, backend.getTextWithDefault("ai_request_delay_label_sec", "AI İstek Gecikmesi (sn):")); Layout.fillWidth: true;
                            DoubleSpinBox { 
                                from: 0; to: 2000; stepSize: 10 
                                value: settingsBackend.getAIRequestDelay() * 100 
                                onValueChanged: settingsBackend.setAIRequestDelay(value / 100.0) 
                                editable: true 
                            }
                        }
                    }

                    // System Prompt
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Label { 
                            text: (backend.uiTrigger, backend.getTextWithDefault("settings_ai_prompt_title", "Özel Sistem Promptu (Opsiyonel):"))
                            color: "#ccc" 
                            font.bold: true
                        }
                        
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 120
                            color: root.inputBackground
                            radius: 8
                            border.color: root.borderColor
                            border.width: 1

                            ScrollView {
                                anchors.fill: parent
                                clip: true
                                TextArea {
                                    text: settingsBackend.getAISystemPrompt()
                                    onEditingFinished: settingsBackend.setAISystemPrompt(text)
                                    placeholderText: (backend.uiTrigger, backend.getTextWithDefault("settings_ai_prompt_desc", "AI için varsayılan talimatları geçersiz kıl..."))
                                    color: root.mainTextColor
                                    font.pixelSize: 13
                                    wrapMode: TextEdit.Wrap
                                    leftPadding: 12
                                    rightPadding: 12
                                    topPadding: 12
                                    bottomPadding: 12
                                    selectByMouse: true
                                    background: null
                                    placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.35)
                                }
                            }
                        }
                    }
                }
            }

            // Reset Button
            Button {
                text: (backend.uiTrigger, backend.getTextWithDefault("restore_defaults_full", "♻️ Tüm Ayarları Varsayılana Döndür"))
                Layout.alignment: Qt.AlignRight
                flat: true; Material.foreground: Material.Red
                onClicked: {
                    settingsBackend.restoreDefaults()
                    backend.refreshUI()
                }
            }
        }
    }

    // Helper Components
    component SettingsGroup: Rectangle {
        property string title: ""
        default property alias content: innerLayout.children
        Layout.fillWidth: true
        implicitHeight: innerLayout.height + 40
        radius: 12
        color: root.cardBackground
        ColumnLayout {
            id: innerLayout
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 20; spacing: 16
            Label { text: title; font.pixelSize: 18; font.bold: true; color: Material.accent }
            Rectangle { Layout.fillWidth: true; height: 1; color: root.separatorColor }
        }
    }

    component SettingsRow: RowLayout {
        property string label: ""
        spacing: 20
        Label { text: label; Layout.preferredWidth: 200; color: root.secondaryTextColor }
    }

    component FilterCheck: CheckBox {
        property string key: ""
        property string label: ""
        text: label
        checked: settingsBackend.getFilter(key)
        onCheckedChanged: settingsBackend.setFilter(key, checked)
        Layout.fillWidth: true
    }

    component DescriptiveCheck: RowLayout {
        property string label: ""
        property string description: ""
        property bool checked: false
        signal toggled(bool isChecked)

        spacing: 12
        Layout.fillWidth: true

        CheckBox {
            id: cb
            checked: parent.checked
            onCheckedChanged: parent.toggled(checked)
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: -8
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Label {
                text: label
                color: root.mainTextColor
                font.bold: true
                font.pixelSize: 14
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                MouseArea {
                    anchors.fill: parent
                    onClicked: cb.checked = !cb.checked
                }
            }
            Label {
                text: description
                color: root.secondaryTextColor
                font.pixelSize: 11
                wrapMode: Text.Wrap
                Layout.fillWidth: true
                opacity: 0.7
            }
        }
    }

    component DoubleSpinBox: SpinBox {
        property int decimals: 2
        property real realValue: value / 100.0

        from: 0
        to: 1000
        stepSize: 10
        editable: true

        validator: DoubleValidator {
            bottom: Math.min(from, to)
            top: Math.max(from, to)
        }

        textFromValue: function(value, locale) {
            return Number(value / 100.0).toLocaleString(locale, 'f', decimals)
        }

        valueFromText: function(text, locale) {
            return Number.fromLocaleString(locale, text) * 100
        }
    }

    component ApiField: ColumnLayout {
        property string label: ""
        property string text: ""
        signal changed(string newValue)
        Label { text: label; color: "#ccc"; font.bold: true }
        TextField {
            Layout.fillWidth: true; 
            Layout.preferredHeight: 40
            echoMode: TextInput.Password; 
            text: parent.text; 
            onTextChanged: parent.changed(text)
            leftPadding: 12; rightPadding: 12; color: root.mainTextColor
            verticalAlignment: TextInput.AlignVCenter
            background: Rectangle { color: root.inputBackground; radius: 8; border.color: root.borderColor }
            placeholderTextColor: Qt.rgba(root.mainTextColor.r, root.mainTextColor.g, root.mainTextColor.b, 0.35)
        }
    }
}
