# React + FastAPI Dönüşüm Notları (Manuel İşlemler)

Bu belge, projenin tek bir Python scriptinden (**CLI**), modern bir Web Uygulamasına (**React + FastAPI**) dönüştürülmesi sırasında yapılan işlemleri ve teknik kararları içerir.

## 1. Mimari Değişikliği
Proje iki ana parçaya ayrıldı:
- **`backend/`**: Python mantığı, veritabanı ve LLM iletişimi.
- **`frontend/`**: Kullanıcı arayüzü (React).
- **`docker-compose`**: Bu iki servisi ve dosya paylaşımlarını yöneten orkestratör.

## 2. Frontend Kurulumu (Manuel Adımlar)
Frontend, modern ve hızlı bir geliştirme ortamı için **Vite** kullanılarak oluşturuldu.

1. **İskeletin Oluşturulması:**
   ```bash
   npm create vite@latest frontend -- --template react
   ```
2. **Paketlerin Yüklenmesi:**
   ```bash
   cd frontend
   npm install
   # Markdown render etmek için ek kütüphane
   npm install react-markdown
   ```
3. **Docker Uyumluluğu:**
   - `Dockerfile` oluşturuldu (`node:22-alpine` tabanlı).
   - Vite config, Docker'dan erişilebilmesi için `--host` parametresiyle başlatıldı.

## 3. Backend Dönüşümü (FastAPI)
`cv_pdf_watcher.py` dosyası parçalandı:
- **`watcher.py`**: Dosya izleme mantığı (Watchdog). `ON_ANALYSIS_COMPLETE` callback mekanizması eklendi.
- **`main.py`**: FastAPI sunucusu.
  - **WebSocket (`/ws`)**: Frontend'e canlı veri akışı sağlar.
  - **Arkaplan Thread**: FastAPI başladığında `watcher`'ı ayrı bir thread'de çalıştırır.

## 4. Kritik Docker Ayarları
Sistemin stabil çalışması için yapılan kritik ayarlar:

### a. Atomic Save Sorunu
Editörler dosyayı kaydederken *üzerine yazmak* yerine *silip yeni dosya* oluşturduğunda Docker'ın takibi kopuyordu.
- **Çözüm**: Docker'a tek bir dosya yerine, **ana klasörü (`/`)** `/host_data` olarak bağladık.
- Kod (`watcher.py`), dosyayı `/host_data/Alper_Erdogan_CV.pdf` yolundan okuyacak şekilde güncellendi.

### b. Node Versiyonu
Vite, eski Node.js sürümlerinde çalışmadığı için Frontend Dockerfile'ı `node:22-alpine` sürümüne güncellendi.

## 5. Başlatma Scripti
Tüm sistemi tek komutla ayağa kaldırmak için `start_app.sh` yazıldı:
```bash
./start_app.sh
```
Bu script, gerekli izinleri kontrol eder ve `docker-compose up --build` komutunu çalıştırır.
