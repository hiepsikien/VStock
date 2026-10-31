# Torroba: A–B–A, tempo, và bass ngắn

> **Trạng thái**: đề xuất. Chưa vào code.
> **Thay cho**: hàng “một pattern cả chương” trong [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 2, và hàng `BPM ≤ 72 → castillo` trong [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md) mục 7.
> **Giữ**: 1D một pattern. Texture (Arada, Float, Rasgueado, …) vẫn không lên dòng chương. Không thêm id pattern mới. Không sửa cờ `bridge` / `trio` trong `span.py`, vì các nhà khác đọc cùng form đó.

Ba việc cùng một đợt: mọi chương ngoài 1D hát ít nhất hai pattern theo A–B–A, pattern khớp nhịp và BPM, bass dây buông không ngân chồng. Dòng tên trên chart in đúng hàng đó.

---

## 1. Việc đang nghe

ACB 1M, Guitar, Torroba, giọng nhà Si♭. Bốn chương:

| Chương | Nhịp đang chạy | Mood | Tên trong file audio | Pattern đang hát |
|---|---|---|---|---|
| I | 4/4, 96 | selloff | Sonatina | Cả chương Sonatina. Không có vùng B |
| II | 3/4, 72 | calm | Castillo — Juglar — Castillo | 0:25–1:55 Castillo, 1:55–2:55 Juglar, 2:55–4:15 Castillo |
| III | 6/8, 120 | selloff | trống, chưa soạn | Sẽ là Castillo — Sonatina — Castillo |
| IV | 4/4, 96 | rally | trống, chưa soạn | Cả chương Sonatina nếu mọi slot cùng rally |

Chương II tại 2:50 đang ở ô 68, năm giây cuối của Juglar. Giá chương này chỉ chạy 21.00–21.45. Juglar lưới thưa đánh lại cùng dây buông mỗi phách. Castillo hai bên ngân cả nốt hát và bass suốt ô, 2,5 giây, rồi ô sau búng lại.

Chart chỉ in `Suite ACB 1M in B-flat`. File chương II đã có `movementName`. Phòng nghe lấy manifest một lần lúc tiếng bắt đầu; lúc đó chương II chưa ghi tên, và lượt làm mới không chạy lại.

---

## 2. A–B–A cho mọi chương ngoài 1D

1D là ngày 34 ô, 4/4. `_Ctx` không có field span. Cửa giữ một pattern là `bars == 34 and kind == "4/4"`. Tuần một phiên là 32 ô, không lọt cửa này.

Mọi thân Torroba còn lại chia ba vùng ô bằng nhau, tính trên ô thân, bỏ warmup, cooldown, intro, outro. Vùng 0 và vùng 2 hát primary. Vùng 1 hát contrast. Câu lấy pattern của ô thân đầu tiên của câu. Chương đã có `bridge` hoặc `trio` giữ nguyên vùng B đó, không chia ba thêm một lần nữa.

Ít hơn ba câu thân: câu đầu A, câu giữa B, câu cuối A. Một câu thân duy nhất vẫn là một pattern. Tuần và các chương tháng đều dài hơn cửa đó.

`form_pattern_ids` đọc cùng cách chia. Dòng chương là `A — B — A` khi hai tên khác nhau. Hai đầu trùng nhau vẫn in đủ ba chỗ, ví dụ `Sonatina — Olite — Sonatina`.

Pedal không đổi pattern.

---

## 3. Pattern theo nhịp và BPM

Ba bảng dưới là primary. Contrast lấy ở mục 4. Cửa `bpm <= 72 → castillo` bỏ. Mood đọc trên các ô của đúng vùng, cùng `_majority_mood`.

Chỉ đứng pattern có lưới của nhịp đó.

| 4/4, 90–108 BPM | Pattern | Vì sao |
|---|---|---|
| calm | Castillo | Nốt hát dài, sau khi bass rút còn một phách |
| rally | Sonatina | Rải móc đơn, bass một móc |
| selloff | Sonatina | Cùng lưới, vòng hợp âm đi xuống |
| volatile | Olite | Lưới 4/4 của chương nhanh |

Fandanguillo và Danza không vào 4/4. 1W là 90. 1M I, 1M IV, 3M I, tháng mở 1Y (100) và tháng 12 (96) là 4/4. 3M III là 108, vẫn bảng này.

| 3/4, 60–72 BPM | Pattern | Vì sao |
|---|---|---|
| mọi mood | Castillo | Đây là tempo của nốt ngân |

1M II là 72. 3M II là 60. Chương giữa 1Y là 66. Juglar không còn là cả vùng B. Một vùng Juglar dài một phút, nốt lặp trên giá đi ngang, là đoạn monotone ở chương II.

| 6/8, 108–120 BPM | Pattern | Vì sao |
|---|---|---|
| calm | Danza | Hợp âm staccato, đúng tempo scherzo |
| rally | Alcaniz | Điệu 6/8 |
| volatile | Fandanguillo | Quạt, lưới 6/8 |
| selloff | Sonatina | Vẫn chạy móc. Castillo ngân cả ô không đứng ở 120 |

1M III là 120. Scherzo 1Y (closer, sau khi guitar đổi 3/4 sang 6/8) là 108.

---

## 4. Contrast, vẫn trong cùng nhịp

B khác A. Cùng họ nhịp.

| A | B trên 4/4 | B trên 3/4 | B trên 6/8 |
|---|---|---|---|
| Castillo | Sonatina | Sonatina | — |
| Sonatina | Olite khi vùng A là rally. Castillo khi vùng A là selloff hoặc calm | Castillo | Fandanguillo |
| Olite | Sonatina | — | — |
| Danza | — | — | Sonatina |
| Alcaniz | — | — | Danza |
| Fandanguillo | — | — | Alcaniz |

3/4 không có hàng Danza hay Fandanguillo. Hai điệu đó ở 60–72 nghe đặc hơn Sonatina, và Sonatina đã có bass một móc.

ACB 1M sau bảng này:

| Chương | Hôm nay | Sau |
|---|---|---|
| I, selloff, 4/4 96 | Sonatina | Sonatina — Castillo — Sonatina |
| II, calm, 3/4 72 | Castillo — Juglar — Castillo | Castillo — Sonatina — Castillo |
| III, selloff, 6/8 120 | Castillo — Sonatina — Castillo | Sonatina — Fandanguillo — Sonatina |
| IV, rally, 4/4 96 | Sonatina | Sonatina — Olite — Sonatina |

---

## 5. Bass dây buông

Ù đến từ búng lại cùng dây Mi, La hoặc Rê trong khi tiếng trước còn ngân.

Thân bài, mọi pattern Torroba:

- Bass dài tối đa một phách đen.
- Trước cú bass sau có ít nhất một móc đơn nghỉ, kể cả khi sang ô.
- Cùng cao độ với cú bass ngay trước thì bỏ cú mới, để lỗ nghỉ. Không buộc dây.
- Lead của Castillo vẫn ngân cả ô. Thứ bị cắt là bass.

Chỗ sửa:

- `_render_castillo_bar`: bass đang là `written(origin, epb, …)`, cả ô. 3/4 ở 72 BPM là 2,5 giây. Đổi thành một phách ở móc 0.
- `_render_juglar_bar` lưới thưa: bass đang là một phách trên mỗi phách 0, 1 và 2. Giữ một cú ở phách 0, dài một móc đơn.
- Cửa intro/outro trong `guitar_torroba_doors.py` đang `bass_length=ctx.epb`. Cửa pedal rút còn một phách ở ô đầu, các ô cửa sau nghỉ bass nếu cùng cao độ.

Juglar còn trong `_PATTERN_TITLE` và trong cửa 3/4. Scheduler không giao cả vùng B cho nó.

---

## 6. Dòng tên trên chart

Chuỗi vẫn là `pattern_form`: `Sonatina — Castillo — Sonatina (4/4, 96 BPM)`. 1D để tên pattern trên title và `movement` là null, như hiện tại.

`ReplayRoom` chỉ gọi lại span khi `audible` chuyển true, rồi chỉ điền tên còn trống. Chương soạn xong sau lượt đó đứng trống suốt bài. Sửa: mỗi lần sang chương, nếu `name` của chương đó trống thì lấy lại span và ghi tên mới. Chương đã có tên giữ nguyên.

`SPAN_REVISION` tăng một nấc. File audio soạn trước đợt này hết hạn, vì hàng pattern và độ dài bass đổi. Tên in ra từ lần soạn mới.

---

## 7. Chỗ sửa khi thực hiện

- `backend/app/sonify/guitar_torroba.py`: `_torroba_primary`, `_torroba_contrast`, `_render_castillo_bar`, `_render_juglar_bar`.
- `backend/app/sonify/guitar_patterns.py`: nhánh Torroba trong `_assign_macro` và `form_pattern_ids`.
- `backend/app/sonify/guitar_torroba_doors.py`: `bass_length` của cửa Castillo và Juglar.
- `backend/app/sonify/audio.py`: `SPAN_REVISION`.
- `src/musicalize/ReplayRoom.tsx`: lấy lại tên khi vào chương còn trống.
- `backend/tests/test_program.py`: tên A–B–A của chương 4/4 không bridge, và 1D vẫn một tên.
- `backend/tests/test_sonify_guitar_torroba.py`: bảng mục 3 và mục 4, bass thân không dài quá một phách, hai cú bass cùng cao độ không chồng.
- `docs/sonify-guitar-torroba-castillos-frames.md` mục 2: thay bảng “một pattern cả chương” bằng bảng mục 3 và mục 4 của file này.

Không đụng `span.py`.
