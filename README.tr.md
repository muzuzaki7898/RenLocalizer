> ⚠️ **Warning (English)**: This project has been assisted by AI. It may contain mistakes, incomplete implementations and is still under active development. It is NOT a final release.
> ⚠️ **Uyarı (Türkçe)**: Bu proje yapay zeka desteğiyle hazırlanmıştır; hatalar ve eksikler içerebilir, halen geliştirme aşamasındadır ve nihai sürüm değildir.

# RenLocalizer V2

[English README](./README.md) | **Türkçe**

![Lisans](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

**RenLocalizer V2**, Ren'Py görsel roman (.rpy) dosyalarını profesyonel şekilde çoklu çeviri motorlarıyla otomatik çevirmek için geliştirilmiş yüksek performanslı bir masaüstü uygulamasıdır. Otomatik proxy rotasyonu, toplu çeviri, akıllı filtreleme ve modern arayüz sunar.

## ✨ Özellikler

### 🚀 Yüksek Performans
- **Uygulanan motorlar**: Google (web), DeepL (API)
- **Planlanan**: Bing (Microsoft), Yandex, LibreTranslator
- **Eşzamanlı işlem**: Arayüzde 256'ya kadar (çekirdek şu an 32 aktif slot)
- **Toplu çeviri**: 2000'e kadar yapılandırılabilir
- **Proxy rotasyonu**: Çoklu kaynak + doğrulama
- **Akıllı fallback**: Google isteğinde proxy/aiohttp hata verirse direkt requests

### 🎨 Modern Arayüz
- **Profesyonel temalar**: Koyu, Açık, Solarized, Göz-dostu
- **Gerçek zamanlı izleme**: Anlık hız, ilerleme ve durum
- **İki dil desteği**: İngilizce & Türkçe arayüz
- **Otomatik kaydetme**: Zaman damgalı klasörlere çıktı

### 🔧 Akıllı İşleme
- **Akıllı ayrıştırıcı**: Kod parçaları, dosya yolları, teknik terimleri filtreler
- **Bağlam koruma**: Karakter isimleri ve placeholder'lar bozulmaz
- **Ren'Py etiket desteği**: {color}, {size} gibi format tag'leri korunur

### 🛡️ Güvenilirlik
- **Hata yakalama**: Yeniden deneme & loglama
- **Oran sınırlama**: Motor bazlı akıllı gecikme
- **Proxy yönetimi**: Çalışan proxy istatistikleri

## 📦 Kurulum

```bash
git clone https://github.com/kullanici/RenLocalizer-V2.git
cd RenLocalizer-V2
pip install -r requirements.txt
python run.py
```

Windows PowerShell için:
```powershell
$env:PYTHONPATH="$(Get-Location)"; python run.py
```

## 🚀 Hızlı Başlangıç
1. Uygulamayı aç (`python run.py`)
2. `.rpy` dosyalarının bulunduğu klasörü seç
3. Kaynak ve hedef dili seç (örn. EN → TR)
4. Motoru ve batch ayarlarını yapılandır
5. Çeviriyi başlat – ilerlemeyi canlı takip et
6. Çeviriler otomatik kaydedilecek (veya manuel kaydedebilirsin)

## ⚙️ Ayarlar
- Eşzamanlı thread sayısı (1–256)
- Batch boyutu (1–2000)
- İstek gecikmesi (0–5 sn)
- Maksimum yeniden deneme
- Proxy kullan / kapat

## 🌍 Motor Durum Tablosu
| Motor | Durum | Not |
|-------|-------|-----|
| Google | ✅ Aktif | Web istemci + proxy fallback |
| DeepL | ✅ Aktif | API anahtarı sadece kullanırsan gerekli |
| Bing / Microsoft | ⏳ Planlandı | Henüz eklenmedi |
| Yandex | ⏳ Planlandı | Henüz eklenmedi |
| LibreTranslator | ⏳ Planlandı | Self-host seçeneği gelecekte |

## 🧠 Ayrıştırma Mantığı
- Kod blokları, label tanımları, python blokları hariç tutulur
- Sadece gerçek diyalog ve kullanıcıya görünen metinler alınır
- Dosya yolları, değişkenler, `%s`, `{name}` vb. korunur

## 📁 Proje Yapısı
```
src/
  core/ (çeviri, parser, proxy)
  gui/  (arayüz ve temalar)
  utils/ (config)
run.py (başlatıcı)
README.md / README.tr.md
LICENSE
```

## 🔐 API Anahtarları
Şu an yalnızca DeepL için API anahtarı anlamlı; diğer motorlar eklendiğinde etkinleşecek.

## 🧪 Test & Katkı
Pull Request gönderebilirsin. Önerilen geliştirmeler:
- Yeni motor entegrasyonu
- Performans optimizasyonu
- Ek dil desteği
- UI geliştirmeleri

## ❓ Sorun Giderme
| Problem | Çözüm |
|---------|-------|
| Module not found 'src' | `PYTHONPATH` ayarla veya kök klasörden çalıştır |
| Yavaş çeviri | Thread ve batch değerlerini yükselt, gecikmeyi düşür |
| Rate limit | Proxy aç veya motor değiştir |
| Bozuk tag | Placeholder koruma açık mı kontrol et |

## 📄 Lisans
Bu proje **GPL-3.0-or-later** lisansı ile dağıtılmaktadır. Ayrıntılar için `LICENSE` dosyasına bakın.

## 💬 İletişim
Issue açabilir veya katkı sağlayabilirsin. Open source topluluğuna katkılar memnuniyetle karşılanır.

---
**RenLocalizer V2** – Ren'Py projeleri için profesyonel çeviri hızlandırıcısı.
