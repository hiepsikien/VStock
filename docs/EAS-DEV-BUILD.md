# Dev build (side-by-side với production)

Bản **Dev** dùng bundle ID riêng — cài song song với App Store / TestFlight, **không ghi đè** production.

| | Production | Development |
|---|---|---|
| Name | VStock | VStock (Dev) |
| iOS bundle | `com.nguyendinhanh.vstock` | `com.nguyendinhanh.vstock.dev` |
| Android package | `com.nguyendinhanh.vstock` | `com.nguyendinhanh.vstock.dev` |
| Scheme | `vstock` | `vstock-dev` |

Controlled by `APP_VARIANT=development` (`app.config.ts` + `eas.json`).

Backend **không** tách: cả hai app có thể dùng cùng API URL.

---

## Local builds (ưu tiên khi EAS hết quota)

Cần Xcode + Apple team đã đăng nhập. Sinh lại `ios/` (gitignored) với bundle Dev.

```bash
cd ~/Projects/VStock

# Build + cài Dev app lên iPhone (lần đầu / sau khi đổi native deps)
npm run ios:dev

# Simulator
npm run ios:dev:sim

# Các ngày sau: chỉ Metro, rồi mở app Dev (hoặc quét QR)
npm run start:dev
```

Sau khi binary có `expo-dev-client`: mở app → launcher → nhập `http://YOUR_MAC_IP:8081`, hoặc long-press 3 ngón tay (shake thường kém ổn định).

Dùng `.env` / `.env.development` cho `EXPO_PUBLIC_*` (API URL, Sentry DSN, …).

**Không** chạy bare `expo run:ios` / `npx expo run:ios` khi máy đã có bản store — thiếu `APP_VARIANT=development` sẽ dùng bundle production và **ghi đè** app store.

### Signing

1. App ID `com.nguyendinhanh.vstock.dev` phải tồn tại (Apple Developer hoặc Xcode tự tạo khi sign).
2. Nếu Xcode hỏi: mở `ios/*.xcworkspace` → Signing & Capabilities → chọn Team.
3. Trên máy: trust developer certificate nếu iOS hỏi; bật **Developer Mode**.

### Khi nào phải rebuild native?

Chỉ khi đổi native: plugin mới, permissions, upgrade Expo SDK.  
Đổi JS/TS thuần → `npm run start:dev`, **không** cần `ios:dev` lại.

---

## EAS builds (cloud — khi còn quota)

```bash
npm run build:ios:dev      # Internal, bundle Dev (`APP_VARIANT=development`)
npm run build:ios:sim      # Simulator
npm run build:ios:testflight  # App Store / TestFlight (bundle production)
npm run build:android:dev
```

Lần đầu EAS: `npx eas-cli login` (projectId đã có trong `app.config.ts`).

API bake trong profile `development` / `preview` / `production`:

`EXPO_PUBLIC_API_URL=http://34.124.179.140:8000`

Đổi IP trong `eas.json` rồi **rebuild** nếu VM đổi IP.

---

## Kiểm tra alerts (dev client)

1. Tạo cảnh báo giá trong app  
2. Cho phép thông báo  
3. Đưa app ra nền / khóa máy  
4. Đợi OS chạy background task (có thể 15–30+ phút)

Expo Go **không** đủ cho `expo-background-task` + local notifications — cần Dev / production binary.

---

## Scripts npm

```bash
npm run start:dev          # Metro + APP_VARIANT=development
npm run ios:dev            # Local: build + cài Dev lên device
npm run ios:dev:sim        # Local: Dev trên Simulator
npm run android:dev        # Local: Dev Android
npm run prebuild:dev       # Chỉ regenerate ios/android (Dev)
npm run build:ios:dev      # EAS cloud (Dev bundle)
npm run build:ios:testflight
```
