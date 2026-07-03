# GES Fizibilite Aracı — Proje Brief & Yürütme Planı

*Sürüm: R1 · Tarih: 3 Temmuz 2026*
*Amaç: Bu belge hem insan (karar/onay) hem de otonom kodlama oturumları (loop-orkestra) için tek referans kaynağıdır.*

---

## 0. Bir bakışta (TL;DR)

- **Ne yapıyoruz:** Bir GES yatırımının (çatı **ve** arazi) fizibil olup olmadığını — depolamalı/depolamasız senaryolarla, Türkiye/EPDK regülasyonuna göre — otomatik hesaplayıp rapor üreten bir araç.
- **Neden yapılabilir:** İşin zor matematiği (üretim + finans + batarya) olgun, ücretsiz, akademik olarak doğrulanmış açık kaynak kütüphanelerde hazır.
- **Bizim özgün işimiz:** Türkiye regülasyon/tarife katmanı + rapor. Moat burası.
- **Rakip boşluğu:** PVCase teknik çizimi yapıyor; finansal modelleme, fizibilite ve regülasyon üretimi yapmıyor.
- **Tahmin:** İyi bağlam beslemesiyle çalışan MVP ~2–4 hafta takvim, ~10–20M token.

---

## 1. Amaç ve Bağlam

### 1.1 Problem
Türkiye'de bir işletme "çatıma/araziye GES kursam mantıklı mı, kaç yılda döner, batarya eklemeli miyim?" sorusuna hızlı ve güvenilir cevap alamıyor. Bu hesap bugün büyük ölçüde elle, Excel'de ve firmadan firmaya değişen varsayımlarla yapılıyor.

### 1.2 Pazar boşluğu
- **PVCase** (pazar lideri): 2017 Litvanya kökenli, 123,6M$ yatırım almış, 80+ ülkede 1.800+ müşteri. AutoCAD üzerine ObjectARX/.NET ile yazılmış ağır 3B geometri motoru. Fiyat ~2.990 USD/kullanıcı/yıl (+ zorunlu AutoCAD).
- **PVCase'in YAPMADIĞI:** finansal modelleme, teklif/fizibilite raporu üretimi, otomatik SLD/kablo boyutlandırma. → **Bizim fırsatımız tam burada.**

### 1.3 Neden şimdi
- Saatlik mahsuplaşmaya geçiş fizibilite hesabını kökten değiştiriyor → doğru araca ihtiyaç arttı.
- Hibrit (depolamalı) çatı GES 2 Nisan 2026 yönetmeliğiyle tanımlandı → depolama senaryosu artık kritik karar.
- Trafo/bağlantı kapasitesi darboğazı → yatırım öncesi "gerçekçi mi?" analizi değer kazandı.

---

## 2. Hedef (Vizyon)

**Rakip bir AutoCAD eklentisi değil, bağımsız bir fizibilite motoru.**

Girdi: saha/çatı alanı, son 12 ay tüketim profili, trafo gücü, konum, tesis çalışma profili (vardiya).
Çıktı: iki senaryolu (sadece güneş / güneş + depolama) karşılaştırmalı fizibilite raporu — CAPEX, yıllık üretim, öz-tüketim oranı, geri ödeme süresi, NPV/LCOE, regülasyon uygunluğu.

**Farklılaşma ekseni:** çekirdek CAD yerleşiminde PVCase ile yarışmıyoruz; onun boş bıraktığı **regülasyon + finans + rapor** katmanını dolduruyoruz.

---

## 3. Teknik Genel Bakış

### 3.1 Mimari katmanlar
1. **Girdi katmanı** — tüketim verisi (CSV/fatura), saha parametreleri, konum.
2. **Üretim motoru** — pvlib (PVGIS verisiyle yıllık/saatlik üretim).
3. **Finans + batarya motoru** — PySAM/SAM (CAPEX, NPV, LCOE, geri ödeme, batarya dispatch).
4. **Regülasyon kural motoru (ÖZGÜN)** — EPDK kuralları, config-driven.
5. **Senaryo karşılaştırma** — depolamalı vs depolamasız.
6. **Rapor üreteci** — şablon → PDF/HTML.
7. **Arayüz** — MVP'de basit form; ürünleşince web.

### 3.2 Hazır açık kaynak motorlar

**pvlib — üretim motoru**
- Repo: https://github.com/pvlib/pvlib-python (~1.500 ★, BSD-3, güncel v0.15.2)
- Ne yapar: ışınım → elektrik üretimi; 100+ doğrulanmış model; PVGIS/PVWatts veri çekme.
- Çatı + arazi: her ikisi de; sabit eğim + tek/çift eksenli takip (arazide standart) destekli.

**PySAM / SAM — finans + batarya motoru**
- Repo (Python): https://github.com/NREL/pysam (~127 ★ — düşük görünür ama NREL resmî sarmalayıcı)
- Repo (ana): https://github.com/NREL/SAM
- Ne yapar: techno-ekonomik model; NPV, LCOE, geri ödeme; PV + batarya; sayaç-arkası (öz-tüketim) ve PPA senaryoları.
- Çatı + arazi: SAM zaten en çok arazi (utility-scale) için kullanılan araç; çatı C&I de destekli.

**Opsiyonel (ileri faz)**
- REopt (maliyet-optimal depolama boyutlandırma): https://github.com/NREL/REopt.jl
- PyPSA (enerji sistem optimizasyonu): https://github.com/PyPSA/PyPSA

### 3.3 Özgün olarak yazılacak tek parça
Türkiye/EPDK **regülasyon kural motoru** + tarife/kur verisi + rapor şablonu + tutkal kodu. Kurallar **koda gömülmez**, config (YAML/JSON) olarak tutulur ki regülasyon değişince kod değişmesin.

---

## 4. Tech Stack

| Katman | Seçim | Gerekçe |
|---|---|---|
| Dil | **Python 3.11+** | pvlib ve PySAM Python; tek dilde bütünlük |
| Üretim | **pvlib** | Doğrulanmış, ücretsiz, PVGIS entegre |
| Finans/batarya | **NREL-PySAM** | Sektör standardı techno-ekonomi |
| Işınım verisi | **PVGIS API** | Ücretsiz, Türkiye kapsamlı |
| Regülasyon | **Config-driven rules (YAML) + Python** | Bakımı kolay, regülasyon kaymasına dayanıklı |
| API | **FastAPI** | Hafif, tip güvenli, hızlı |
| Rapor | **Jinja2 + WeasyPrint** (HTML→PDF) | Profesyonel görünüm, kolay şablon |
| Arayüz (MVP) | **Streamlit** | En hızlı iç-araç doğrulaması |
| Arayüz (ürün) | **React/Next.js** | Ürünleşme fazında |
| Veri | **SQLite → Postgres** | MVP basit, sonra ölçek |
| Test | **pytest + golden-file** | SAM çıktısına karşı doğrulama |

---

## 5. Kapsam: Çatı + Arazi

- **Motorlar her ikisini de destekler.** Fark hesapta değil, regülasyon/maliyet kalemlerinde.
- **Çatı dalı:** lisanssız 25 kW sınırı, öz-tüketim (5.1.j/5.1.ç), mahsuplaşma, hibrit tanımı, düşük CAPEX, kısa izin.
- **Arazi dalı:** 5.1.h (sanayi/tarımsal sulama), arazi temini, imar değişikliği, ÇED, ENH maliyeti, zemin/statik, sigorta, daha ağır bağlantı riski.
- Regülasyon kural motoru bu iki dalı ayrı config olarak tutar; araç en baştan ikisini de destekler.

---

## 6. Goal Otomatları (loop-orkestra yürütme birimleri)

Her goal, `develop` dalına inecek, otonom doğrulanabilir, bağımsız bir iş birimidir. Sıra bağımlılığı korunur. Her goal'ün net kabul kriteri + testi vardır ki gece otonom çalışsın.

**G0 — İskelet & CI**
- Repo yapısı, poetry/uv, lint, pytest, CI. Boş modül arayüzleri.
- Kabul: `pytest` yeşil, CI geçer.

**G1 — Girdi modülü**
- 12 aylık tüketim CSV/fatura parse; saha parametre şeması (pydantic).
- Kabul: örnek CSV doğru parse; hatalı girdi net hata verir.

**G2 — Üretim motoru (pvlib entegrasyonu)**
- Konum → PVGIS veri çekme → yıllık/saatlik üretim.
- Kabul: bilinen bir konum için üretim, referans değere ±%X içinde.

**G3 — Finans motoru (PySAM entegrasyonu)**
- PV-only techno-ekonomik: CAPEX, NPV, LCOE, geri ödeme.
- Kabul: SAM GUI ile aynı girdide golden-file eşleşmesi.

**G4 — Batarya senaryosu (PySAM)**
- PV + batarya dispatch; öz-tüketim optimizasyonu.
- Kabul: depolamalı senaryo tutarlı çıktı; tek/çok vardiya farkı gözlemlenir.

**G5 — Regülasyon kural motoru (ÖZGÜN, config-driven)**
- EPDK kuralları YAML; çatı + arazi dalları; 25 kW, mahsuplaşma, hibrit, 5.1.h.
- Kabul: kural birim testleri; regülasyon değişimi sadece config ile.

**G6 — Senaryo karşılaştırma & karar mantığı**
- İki senaryoyu yan yana; "hangisi daha mantıklı" mantığı.
- Kabul: örnek tesis profilinde doğru öneri.

**G7 — Rapor üreteci**
- Jinja2 şablon → PDF; senin formatın.
- Kabul: örnek girdiyle tam rapor üretir.

**G8 — Arayüz (Streamlit MVP)**
- Form → hesap → rapor indir.
- Kabul: uçtan uca akış çalışır.

**G9 — Doğrulama & regresyon paketi**
- Golden-file seti, gerçek vaka(lar)la kalibrasyon.
- Kabul: regresyon testleri yeşil.

> **loop-orkestra disiplini:** `main` daima manuel-merge; otonom işler `develop`'a iner. `project_profile` operasyonel disiplini kontrol eder. Etkileşimli abonelik limitleri sıkı korunur; SDK/headless çağrı yok.

---

## 7. Session Öncesi Context Pompalama (priming)

Her otonom oturumdan önce doğru bağlamı beslemek, token ve süreyi **2–3 kat** düşürür. Yöntem:

### 7.1 Kalıcı bağlam dosyaları (repo kökünde)
- `PROJECT_BRIEF.md` (bu belge) — değişmeyen amaç/hedef/mimari.
- `PROGRESS.md` — checkpoint takibi; her goal sonunda güncellenir.
- `REGULATION_NOTES.md` — EPDK kural özetleri + kaynak linkleri.
- `DECISIONS.md` — kilitlenmiş mimari kararlar (tek dil Python, config-driven kurallar, AutoCAD'e bağımsızlık vb.).

### 7.2 Oturum başı priming sırası
1. İlgili goal'ün tanımını + kabul kriterini ver.
2. Sadece o goal'ün dokunacağı modül dosyalarını bağlama al (tümünü değil).
3. İlgili kütüphane dokümanının **linkini** ver (pvlib/PySAM ilgili sayfa), tüm dokümanı değil.
4. Golden-file/referans değeri varsa onu ver.
5. "Sadece bu goal'ü tamamla, kapsamı genişletme" sınırını koy.

### 7.3 Not: kodlama oturumlarının dili
Bu brief Türkçe (senin referansın için). Ancak Claude Code/Codex'e beslenen **talimat dosyaları İngilizce** olduğunda performans daha iyi. Önerilen priming başlığı örneği (İngilizce):

```
You are implementing GOAL G3 of the GES feasibility engine.
Scope: PV-only techno-economic model via NREL-PySAM.
Do ONLY G3. Do not touch other modules.
Acceptance: golden-file match with SAM GUI output for the reference case in /tests/golden/g3_reference.json.
Reference docs: https://nrel-pysam.readthedocs.io
When done, update PROGRESS.md and stop.
```

### 7.4 Beslenecek dış kaynaklar (elde hazır olsun)
- pvlib ve PySAM ilgili doküman sayfaları
- Güncel EPDK Lisanssız Üretim Yönetmeliği (+ 2 Nisan 2026 değişikliği)
- İstenen rapor formatı örneği
- Gerçek bir 12 aylık tüketim verisi örneği
- Güncel Türkiye tarife/kur verisi

---

## 8. Hedefler, Testler, Kazanımlar

### 8.1 Başarı hedefleri (ölçülebilir)
- Bir tesis için uçtan uca fizibilite raporu **< 2 dakikada** üretilebiliyor.
- Üretim tahmini referans araca karşı kabul edilen tolerans içinde.
- Finansal çıktı SAM ile golden-file eşleşiyor.
- Regülasyon değişikliği **sadece config** ile uygulanabiliyor (kod değişmeden).
- Çatı ve arazi, ayrı senaryo olarak çalışıyor.

### 8.2 Test stratejisi
- **Birim testleri:** regülasyon kuralları (her madde ayrı test).
- **Golden-file testleri:** finans çıktısı SAM referansına karşı.
- **Entegrasyon testi:** girdi → üretim → finans → rapor uçtan uca.
- **Regresyon paketi:** gerçek vaka(lar); her goal sonrası çalışır.
- **Kalibrasyon:** bilinen bir gerçek tesisin verisiyle doğrulama.

### 8.3 Kazanımlar
- **Ürün:** PVCase'in boş bıraktığı finans+regülasyon katmanında farklılaşan bir araç.
- **Hız:** haftalarca süren elle fizibilite → dakikalar.
- **Güven:** doğrulanmış motorlar üzerine kurulu, denetlenebilir hesap.
- **Bakım:** regülasyon kayması config ile yönetilir; teknik borç düşük.
- **Genişleme:** aynı iskelet üstüne arazi, hibrit, PPA senaryoları eklenir.

---

## 9. Build Tahmini

- **Token:** iyi bağlamla ~10–20M; kötü spesifikasyonla 35M+.
- **Süre:** "token × hız" yanıltıcıdır; darboğaz iterasyon döngüsü + rate limit + senin review'un. loop-orkestra gece + iyi priming ile sağlam MVP ~2–4 hafta takvim.
- **Doğruluk (iki katman):**
  - *Kod doğruluğu:* yüksek (doğrulanmış kütüphaneler).
  - *Domain doğruluğu:* senin regülasyon doğrulamana + girdi verisi kalitesine bağlı; asıl risk "regülasyon değişince eskiyen varsayım".

---

## 10. Riskler & Notlar

- **Regülasyon kayması:** en büyük domain riski (saatlik mahsuplaşma canlı örnek). → config-driven kural motoru zorunlu.
- **Tarife/kur oynaklığı:** güncellenebilir veri kaynağı; sabit gömme yasak.
- **Girdi kalitesi:** tüketim profili yanlışsa sonuç yanlış → girdi doğrulaması güçlü olmalı.
- **Lisans:** pvlib BSD-3 (ticari OK); SAM/PySAM açık kaynak — ticari kullanım koşulları sürüm bazında teyit edilmeli.
- **Kapsam kayması:** PVCase'in 3B CAD motorunu yeniden yazma tuzağına düşme; kapsam finans+regülasyon+rapor.

---

## 11. Kaynaklar

**Açık kaynak kütüphaneler**
- pvlib: https://github.com/pvlib/pvlib-python · https://pvlib-python.readthedocs.io
- PySAM: https://github.com/NREL/pysam · https://nrel-pysam.readthedocs.io
- SAM: https://github.com/NREL/SAM · https://sam.nrel.gov
- REopt: https://github.com/NREL/REopt.jl
- PyPSA: https://github.com/PyPSA/PyPSA
- Veri: PVGIS (https://re.jrc.ec.europa.eu/pvg_tools/), PVWatts

**Rakip & pazar**
- PVcase: https://pvcase.com
- SurgePV PVCase incelemesi 2026: https://www.surgepv.com/reviews/pvcase

**Regülasyon (Türkiye)**
- EPDK Lisanssız Üretim: https://www.epdk.gov.tr
- Mevzuat (Yönetmelik): https://www.mevzuat.gov.tr
- Sektör içerikleri: MY Enerjisolar, EÇE Enerji, Pronet, GENSED (2025–2026)

**AutoCAD API (referans, çekirdek için gerekli değil)**
- ObjectARX / AutoLISP: https://help.autodesk.com

---

*Not: Bu belge yaşayan bir dokümandır. Regülasyon başlıkları hızla değişebilir; uygulamaya geçmeden önce güncel EPDK metniyle doğrulanmalıdır. Sürüm arttıkça (R2, R3…) DECISIONS.md ile senkron tutulmalıdır.*
