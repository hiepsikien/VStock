# VStock — Thời điểm lên Apple App Store

> Ghi nhận thống nhất product (2026-07-22): **TestFlight sớm, App Store khi lõi + HTTPS sẵn; không cần chờ đủ 3 nhân vật Companion.**

Liên quan: [COMPANION-AI.md](./COMPANION-AI.md), [EAS-DEV-BUILD.md](./EAS-DEV-BUILD.md), [DEPLOY-GCE.md](./DEPLOY-GCE.md).

---

## 1. Kết luận

**Chưa nên submit App Store public ngay.**

Thời điểm phù hợp: sau khi **lõi sản phẩm chứng khoán** và **hạ tầng production** ổn định, đã chạy **TestFlight** với người dùng thật. Companion AI (Vy / chuyên gia fundamental / virtual friend) **không phải điều kiện** để launch — có thể vào bản sau hoặc ẩn sau feature flag.

---

## 2. Checklist trước khi public Store

Lên App Store (public) khi gần đạt hết:

| # | Hạng mục | Ghi chú |
|---|----------|---------|
| 1 | **Apple Developer Program** | $99/năm — hiện docs EAS ghi *chưa có* (2026-07-20) |
| 2 | **TestFlight** ≥ 1–2 tuần | Vài người thật dùng trong giờ phiên |
| 3 | **API production HTTPS + domain** | GCE đang HTTP — ATS trên iOS sẽ chặn gọi HTTP thường |
| 4 | **Lõi app ổn** | Watchlist, Detail, chart, tin, PE/KQKD; empty/error state chấp nhận được |
| 5 | **Privacy & App Review** | Mô tả quyền (notifications nếu có); disclaimer không phải tư vấn đầu tư; privacy policy (đặc biệt nếu chat Gemini gửi nội dung lên server) |
| 6 | **Companion (Vy)** | Đóng hộp bug nặng (mutate list / số liệu) **hoặc** tắt Companion ở bản store đầu |

---

## 3. Nên đợi / tách pha

| Việc | Gợi ý |
|------|--------|
| Chuyên gia fundamental (Companion pha 2) | **Sau** store v1 — không chặn launch |
| Virtual friend cảm xúc (Companion pha 3) | **Sau nữa** — review + compliance nhạy hơn |
| Background price alerts | TestFlight trước; có thể v1.1 nếu native chưa chín |
| Đủ 3 nhân vật Companion | **Không** bắt buộc trước lần lên Store đầu |

---

## 4. Mốc thực tế đề xuất

```text
Ngay → vài tuần
  → Đăng ký Apple Developer
  → EAS build (preview/production)
  → TestFlight nội bộ          ← “đưa lên Apple” giai đoạn này

Khi HTTPS + lõi ổn + privacy/disclaimer xong
  → Submit App Store public

Song song / sau launch
  → Companion pha 2, pha 3 (xem COMPANION-AI.md)
```

| Giai đoạn | Việc | Store public? |
|-----------|------|----------------|
| A | Apple Developer + EAS + TestFlight | Không — chỉ internal/beta |
| B | HTTPS API + harden lõi + privacy | Chuẩn bị review |
| C | Submit App Store | Có |
| D | Companion mở rộng | Post-launch |

---

## 5. Ghi chú kỹ thuật liên quan Store

- **Dev client / alerts:** [EAS-DEV-BUILD.md](./EAS-DEV-BUILD.md) — không bắt buộc App Store để test device; cần Developer để build iPhone thật.
- **API URL:** bake trong native build (`EXPO_PUBLIC_API_URL`); đổi IP/domain → **rebuild**.
- **Companion client** (nickname, activity, FlatList): theo bản app; deploy GCE chỉ cập nhật backend.

---

## 6. Việc làm tiếp (khi quay lại track Store)

- [ ] Đăng ký Apple Developer + lấy Team ID  
- [ ] `eas init` / gắn `projectId`, commit `app.json`  
- [ ] Bật HTTPS + domain cho API GCE  
- [ ] Profile EAS `production` trỏ URL HTTPS  
- [ ] Privacy policy URL + disclaimer in-app  
- [ ] Quyết định: Companion **bật** hay **ẩn** ở v1.0  
- [ ] Build → TestFlight → iterate → Submit  
