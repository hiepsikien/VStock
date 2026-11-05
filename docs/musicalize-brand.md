# Musicalize — logo và chỗ đặt logo

Tài liệu này chốt cách đưa logo vào mặt nghe Musicalize. Nó không đổi luật của
`docs/musicalize-plan.md` và `docs/musicalize-ui-redesign.md`; nó chỉ định nghĩa
mark, màu và vị trí.

Bộ file: `assets/brand-musicalize/` (README có bảng token và kích thước).
Sinh lại toàn bộ: `python3 scripts/generate_musicalize_brand.py`.

## 1. Đã xem gì

| File | Điều đáng chú ý |
|---|---|
| `src/musicalize/palette.ts` | nền `#08090C`, panel `#0F1319`, ba màu nhấn: cyan `#3EE0E0` (dữ liệu), magenta `#E040A0` (tiếng), amber `#F5B942` (playhead) |
| `src/musicalize/type.ts` | wordmark = sans hệ thống, 13/16, 700, tracking **3**, uppercase; `display` là serif Georgia |
| `src/musicalize/TopBar.tsx` | cao 56, nền `panel`, viền dưới hairline; brand hiện tại = wordmark + **ô vuông magenta 6px**; `compact` khi `< 720` |
| `docs/musicalize-ui-redesign.md` | "viền mảnh thay vì bóng đổ", "không gradient trang trí", "magenta không bao giờ làm nền một khối lớn hơn một hàng hoặc nút play" |
| `App.web.tsx` | bản web **chỉ** render Musicalize, `document.title = 'Musicalize'`, nhưng `app.config.ts` vẫn khai icon/favicon của VStock |

Kết luận ngắn: đây là một phòng thu ban đêm, gần như đơn sắc, ba màu nhấn có
nghĩa riêng, chữ nhỏ và thưa. Logo phải sống trong khuôn đó.

## 2. Vì sao logo nền trắng không vào được

| # | Vấn đề | Bằng chứng |
|---|---|---|
| 1 | **Tấm nền trắng** | Ở 18–20px trong topbar, thứ đọc được duy nhất là hình chữ nhật trắng; nốt nhạc bên trong biến mất. |
| 2 | **Tím không có trong hệ** | Mark bản nháp dùng `#8B5CF6`, palette chỉ có magenta `#E040A0` và cyan `#3EE0E0`. Không có màu thứ tư nào để "thuộc về". |
| 3 | **Hồng lệch tông** | `#EC4899` sáng và ngả đỏ; `#E040A0` đậm hơn, ngả magenta. Cạnh nhau, logo trông như của app khác. |
| 4 | **Gradient là trang trí** | Luật của mặt nghe: không gradient trang trí. Gradient chỉ được phép khi nó mang nghĩa (xem mục 3). |
| 5 | **Nét quá dày** | Bản nháp là logo tròn, dày, nhiều chi tiết; UI dùng vạch 1px, chữ 11–13px, khoảng trắng rộng. Đặt cạnh nhau là hai ngôn ngữ. |
| 6 | **Wordmark lệch hệ** | Bản nháp dùng font tròn, chữ thường, không tracking. Trong app, wordmark là uppercase 13px tracking 3. Hai thứ không thể cùng tồn tại. |
| 7 | **Không có bản 1 màu** | Favicon 16px, notification Android, in ấn đều cần một màu. Bản gradient không thu nhỏ được. |

## 3. Phương án màu

Giữ đúng ba token, bỏ nền trắng, và biến gradient thành thứ có nghĩa:

| Biến thể | Màu | Dùng |
|---|---|---|
| **Studio flat** (mặc định trong UI) | nốt `paper #F4F1EA` + ba vạch `magenta #E040A0` | topbar, footer, mọi nền tối |
| **Spectrum** | vạch chuyển `magenta → cyan`, giữa là `#8F90C0` | app icon, splash, OG, store |
| **Mono** | tất cả `paper`, hoặc tất cả `ink` trên nền sáng | favicon, notification, in, light UI |

Vì sao `magenta → cyan` chứ không phải `tím → hồng`:

- Hai đầu gradient **chính là hai màu nhấn có nghĩa** của sản phẩm: tiếng và dữ liệu. Gradient kể đúng câu chuyện của Musicalize thay vì chỉ để đẹp.
- Điểm giữa của phép trộn là periwinkle `#8F90C0` — vẫn giữ được cảm giác tím–hồng của bản nháp.
- Không sinh ra token thứ tư, nên UI không phải học thêm màu.
- Gradient chỉ sống trên ba vạch, không phủ lên thân nốt: ở 32px nó vẫn là ba khối màu rõ, không thành vệt mờ.

Nếu bạn muốn giữ tím thật, cách duy nhất đúng là thêm `brandViolet` vào
`palette.ts` và **chỉ** dùng nó trong file icon — không dùng trong UI. Đây là
quyết định sản phẩm, không phải quyết định mỹ thuật; mình khuyên không.

## 4. Mark: giữ ý, sửa hình

Giữ nguyên ý bạn đã duyệt — nốt kép + ba vạch tín hiệu — nhưng dựng lại:

| Trước (bản nháp) | Sau |
|---|---|
| dầm dốc, dày, bo tròn | dầm **ngang**, dày 44/1024, đầu mút **vuông** |
| ba vạch nằm trong lòng nốt và cả bên ngoài | chỉ **ba vạch bên phải**, đi lên dần |
| đầu nốt rất lớn, cột dày | đầu nốt `r 78`, cột `58` — nhẹ hơn, đọc được ở 18px |
| gradient phủ toàn bộ | thân nốt một màu; chỉ ba vạch mang màu |
| nền trắng | trong suốt |

Hình chỉ gồm hình chữ nhật, một hình bình hành và hình tròn — cùng bộ primitive
với vạch 2px và ô vuông 6px của UI. Ba vạch đi lên vừa là waveform vừa là biểu
đồ giá; dầm ngang giữ cho mark đứng yên, không "ngả" như bản dốc.

## 5. Bố trí

### 5.1 Topbar (chính)

```
┌──────────────────────────────────────────────────────────────┐
│ ▮▮ MUSICALIZE          ⌘K  ( Nghe lại ● Đang phát )  ● TRỰC TIẾP │ 56
└──────────────────────────────────────────────────────────────┘
```

- Mark **18px** cao (~22.8 rộng), cách wordmark **10px**.
- Wordmark giữ nguyên `type.wordmark`: 13/16, 700, tracking 3, uppercase, `text`.
- **Bỏ ô vuông magenta 6px**: mark đã có ba vạch magenta, giữ ô vuông là nói hai lần.
- Cụm brand rộng 142.8px thay vì 126px. Đo ở 390px: brand 142.8 + 12 + pill 184 + 32 padding = **371px** → còn 19px. Vừa.

### 5.2 Điện thoại hẹp

- `< 384px`: bỏ wordmark, giữ mark **20px** + pill. Cụm còn ~248px, thoải mái ở 320px.
- Hiện tại `TopBar.tsx` đã tràn nhẹ ở 360px (cần 366px); thêm mark sẽ thành 371px. Vì vậy mốc 384 là bắt buộc, không phải tùy chọn.
- Không đổi `compact = width < 720` (mốc ẩn `⌘K` và trạng thái); thêm một mốc riêng cho brand.

### 5.3 Ngoài app

| Bề mặt | File | Ghi chú |
|---|---|---|
| Favicon web | `favicon-32.png` (và 16) | mono trên đĩa `panel`; bản 16px nên là mono, không gradient |
| App icon iOS/Android | `icon-1024.png` | full-bleed `#08090C`, mark 62% bề ngang, để hệ điều hành tự bo góc |
| Android adaptive | `android-foreground-1024.png` + nền `#08090C` | mark trong vùng an toàn 55% |
| Android monochrome | `android-monochrome-1024.png` | silhouette một màu |
| Splash | `splash-1024.png` | chỉ mark, không wordmark, nền `#08090C` |
| OG / share | `og-1200x630.png` | lockup ngang căn giữa + `NGHE LẠI · TRỰC TIẾP` |

Bên trong app **không** đặt thêm logo ở đâu khác. Sân khấu, cột trái và dock đã
có đủ thứ để đọc; logo chỉ thuộc về thanh trên.

## 6. Điều không làm

- Không nền trắng, không đĩa than, không bóng đổ, không glow.
- Không dùng amber trong logo (amber = playhead).
- Không gradient trong topbar.
- Không wordmark kiểu chữ thường/bo tròn: đã có `type.wordmark` làm chuẩn.
- Không đặt logo làm watermark giữa sân khấu khi chưa chọn mã.

## 7. Wiring khi bạn duyệt

1. `src/musicalize/TopBar.tsx`
   - thêm `<Image source={require('../../assets/brand-musicalize/exports/mark-18.png')} style={{height:18,width:23}} />` trước wordmark;
   - bỏ `brandDot`;
   - thêm mốc `const noWordmark = width < 384;` và ẩn `<Text wordmark>` khi đúng.
2. `app.config.ts` (chỉ khi bản phát hành là Musicalize)
   - `icon`, `android.adaptiveIcon.*`, `web.favicon` trỏ về bộ file trên;
   - `adaptiveIcon.backgroundColor: '#08090C'`.
3. `App.web.tsx` — thêm `<link rel="icon">` 32px và 16px, `apple-touch-icon` 180, thẻ `og:image` trỏ `og-1200x630.png`.

Chưa sửa file nào trong lượt này: đây là bản đề xuất kèm asset, để bạn chốt màu
và vị trí trước.

## 8. Cần bạn chốt

1. **Gradient**: `magenta → cyan` (đề xuất) hay giữ tím bằng token mới?
2. **App icon**: Spectrum hay Studio flat (một sắc magenta)?
3. **Mark trong topbar**: 18px như đề xuất, hay 16px cho chắc chắn vừa ở 360px?
