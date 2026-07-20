# EAS Development Build (alerts / native)

Bản **dev client** — không phải App Store. Cần để test `expo-background-task` + local notifications (Expo Go không đủ).

> **Trạng thái (2026-07-20):** Config trong repo đã sẵn (`eas.json`, `expo-dev-client`, scripts).  
> **Tạm dừng:** Chưa có **Apple Developer Program** ($99/năm) → chưa build lên iPhone thật.  
> **Làm lại khi:** Đã đăng ký [developer.apple.com](https://developer.apple.com/programs/) và có Team ID.

## Checklist khi quay lại (sau khi có Apple Developer)

- [ ] Tài khoản Expo: `npx eas-cli login`
- [ ] Gắn project: `npx eas-cli init` (ghi `extra.eas.projectId` vào `app.json` → commit)
- [ ] Build iPhone: `npm run build:ios:dev`
- [ ] Cài app từ link trên [expo.dev](https://expo.dev) + bật **Developer Mode** trên iPhone
- [ ] Chạy Metro: `npm run start:dev` (mở app VStock, **không** dùng Expo Go)
- [ ] Tạo price alert → cho phép thông báo → đưa app ra nền → đợi 15–30+ phút để OS chạy background task
- [ ] Nếu VM đổi IP: sửa `EXPO_PUBLIC_API_URL` trong `eas.json` rồi **rebuild**

**Không bắt buộc App Store / TestFlight** cho bước này — chỉ internal development build.

---

## Yêu cầu

| | |
|--|--|
| Tài khoản [Expo](https://expo.dev/signup) | Bắt buộc (miễn phí) |
| Apple Developer ($99/năm) | **Bắt buộc** nếu build lên **iPhone thật** — *đang chờ đăng ký* |
| Xcode / Simulator | Đủ nếu chỉ test trên **iOS Simulator** (profile `development-simulator`) |

## Bước 1 — Đăng nhập & gắn project (một lần)

Trên Mac, trong thư mục repo:

```bash
cd ~/Projects/VStock
npx eas-cli login
npx eas-cli init
```

`eas init` sẽ tạo project trên Expo và ghi `extra.eas.projectId` vào `app.json`.  
**Commit** `app.json` sau khi có `projectId` thật.

## Bước 2 — Build

### A) iPhone thật (khuyến nghị để test alerts nền) — *làm khi có Apple Developer*

```bash
npm run build:ios:dev
# tương đương: eas build --platform ios --profile development
```

- Lần đầu: đăng nhập Apple, chọn Team, để EAS quản lý certificates
- Khi xong: mở link build trên expo.dev → cài qua QR / link cài
- Bật **Developer Mode** trên iPhone (Settings → Privacy & Security)

### B) iOS Simulator (không cần Apple Developer device / có thể làm trước)

```bash
npm run build:ios:sim
# tương đương: eas build --platform ios --profile development-simulator
```

Tải `.tar.gz` → kéo app vào Simulator. Background task trên Simulator **hạn chế** hơn device thật.

### C) Android (APK) — không cần Apple

```bash
npm run build:android:dev
```

Cài APK từ trang build. Hữu ích nếu có máy Android để test alerts sớm hơn.

## Bước 3 — Chạy Metro với dev client

```bash
npm run start:dev
# tương đương: npx expo start --dev-client
```

Mở app **VStock** (icon trên máy) — không dùng Expo Go — rồi kết nối tới bundler (QR hoặc cùng Wi‑Fi).

API production đang bake trong profile `development` / `preview`:

`EXPO_PUBLIC_API_URL=http://34.142.248.53:8000`

Đổi IP trong `eas.json` nếu VM đổi IP, rồi **rebuild** (env native bake lúc build).

## Kiểm tra alerts

1. Trong app: tạo cảnh báo giá cho một mã
2. Cho phép thông báo khi hệ thống hỏi
3. Đưa app ra nền / khóa máy
4. Đợi OS chạy background task (có thể **15–30+ phút**, không phải realtime)
5. Khi giá khớp điều kiện → local notification

Debug nhanh khi app đang mở: alerts vẫn được check qua polling / `usePriceAlerts`.

## Khi nào phải rebuild?

Chỉ khi đổi native: plugin mới, `app.json` permissions, upgrade Expo SDK.  
Đổi JS/TS thuần → chỉ cần `npm run start:dev`, **không** rebuild EAS.

## Scripts npm

```bash
npm run start:dev          # Metro + dev client
npm run build:ios:dev      # EAS iOS device (cần Apple Developer)
npm run build:ios:sim      # EAS iOS simulator
npm run build:android:dev  # EAS Android
```

## Đã có sẵn trong repo

| File | Vai trò |
|------|---------|
| `eas.json` | Profiles `development`, `development-simulator`, `preview`, `production` |
| `app.json` | `expo-dev-client`, `expo-background-task`, `expo-notifications`, scheme `vstock` |
| `package.json` | Scripts build / `start:dev` |
