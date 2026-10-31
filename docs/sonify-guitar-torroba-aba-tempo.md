# Torroba: A–B–A, tempo, và bass ngắn

> **Trạng thái**: đề xuất. Chưa vào code.
> **Thay cho**: hàng “một pattern cả chương” trong [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 2, và hàng `BPM ≤ 72 → castillo` trong [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md) mục 7.
> **Giữ**: 1D một pattern, id lấy bảng 4/4 mới. Texture (Arada, Float, Rasgueado, …) vẫn không lên dòng chương. Không thêm id pattern mới. Không sửa cờ `bridge` / `trio` trong `span.py`, vì các nhà khác đọc cùng form đó.

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

Chương II tại 2:50 đang ở ô 68, năm giây cuối của Juglar. Giá chương này chỉ chạy 21.00–21.45. Castillo hai bên ngân cả nốt hát và bass suốt ô, 2,5 giây, rồi ô sau búng lại.

Juglar có ba texture, chọn trong `_grid_state`. Chỉ một texture là tremolo có accent.

| Texture | Cửa | Nghe |
|---|---|---|
| `full` | `rise >= 3`, câu chưa đóng | Bộ ba 3:2 mỗi phách. Accent chỉ cú đầu của móc 0. Đây là tremolo *Simancas* |
| `pushed` | `rise < 3`, và câu Juglar ngay trước cũng thưa vì `rise < 3` | Vẫn đủ ba cú, không accent. Hai cú sau thấp hơn một nấc `_under_lead` |
| `thin` | Câu đóng, hoặc `rise < 3` khi câu trước không thưa | Một nốt ngân hết phách. Cú 2 và cú 3 nghỉ. Không có tremolo |

Chương II là tích lũy, biên giá hẹp, nên hầu hết câu có `rise < 3`. Những câu đó lần lượt `thin` rồi `pushed`. Câu đóng luôn `thin`. Ô 68 nằm cuối vùng B, đúng câu đóng. Lưới đang hát là một nốt đen mỗi phách và bass dây buông cũng dài một phách, búng lại ở phách 0, 1 và 2. Bộ ba không được viết. Cửa intro/outro của Juglar cũng không có bộ ba. Tremolo có accent chỉ xuất hiện khi một câu trong vùng B vươn từ 3 trở lên và chưa đóng. Bản này gần như không có câu đó.

Chart chỉ in `Suite ACB 1M in B-flat`. File chương II đã có `movementName`. Phòng nghe lấy manifest một lần lúc tiếng bắt đầu; lúc đó chương II chưa ghi tên, và lượt làm mới không chạy lại.

---

## 2. A–B–A theo slot đã có

1D là ngày 34 ô, 4/4. Cửa `bars == 34 and kind == "4/4"` giữ một pattern. Id lấy bảng 4/4 ở mục 3. Rally của ngày đó là Olite, selloff là Castillo. Nhánh này không giữ bảng cũ, nơi cả hai mood đều là Sonatina. Test “vẫn một tên” cũng khóa id.

Chương đã có từ ba slot phrase, và không có `bridge` hay `trio`, không cắt theo số ô. Chương I guitar sau `_retarget_pedal(intro=4, outro=4)` là khoảng 36, 24 và 28 ô trên `regime_slot` 0, 1, 2, `bridge=False`. Chương IV cùng kiểu. `_assign_macro` hôm nay, khi không có contrast, gọi `_torroba_primary` từng slot. Cả chương selloff nên cả ba slot ra Sonatina.

Slot 0 và slot cuối hát một primary. Mọi slot nằm giữa hát một contrast. Không chia những slot đó thành ba phần ô. 88 ô thân không chia hết cho 3, và câu lấy pattern của ô đầu sẽ đẩy vùng B thêm một lần nữa.

Chương đã có `bridge` hoặc `trio` giữ vùng B đó. Không chia thêm.

Một slot phrase, và không phải ngày 34 ô: tuần một phiên là 32 ô. Chia ô thân của slot đó làm ba phần. Ô dư về phần cuối, cùng `split_into`. Câu lấy pattern của ô đầu tiên trong slot.

Hai slot phrase và không có bridge, như tháng mở 1Y và tuần hai phiên: slot 0 là primary. Slot 1 chia đôi theo ô. Nửa đầu là contrast. Nửa sau chép primary. Ô lẻ của nửa đó về phía trở lại.

Tuần từ ba phiên trở lên giữ biên phiên. Mỗi phiên đã là một slot. Phiên đầu và phiên cuối hát primary. Mọi phiên ở giữa hát cùng một contrast. Hàng này thay “mỗi phiên một pattern”. Nó không cắt ngang một phiên. Tuần năm phiên là một hàng A–B–A, không phải năm lần chọn riêng.

Primary chọn một lần, từ mood của vùng mở: `_majority_mood` trên slot 0, hoặc trên các ô A của chương có bridge. Vùng cuối chép đúng id đó. Không gọi `_torroba_primary` lần nữa. Hai đầu tự đọc mood của mình thì dòng không còn A–B–A, và `pattern_form` gộp hai tên kề nhau thành một.

Contrast là hàng mục 4 của primary đó. Hàng Castillo trên 3/4 đọc mood của vùng mở: calm thì Juglar, selloff thì Danza. `_contrast_pattern` hôm nay truyền mood của vùng giữa vào `_torroba_contrast`. Kế hoạch này không truyền mood đó.

`form_pattern_ids` hôm nay trả một tên khi không có bridge, dù hàng đã là ba id. Chương I và IV vẫn in một tên nếu hàm này chưa đọc cách chia trên. Hàm trả `[primary, contrast, primary]`. `pattern_form` chỉ gộp tên kề nhau. Castillo — Olite — Castillo vẫn là ba tên, vì hai Castillo không kề nhau.

Câu không khung đi `_select_body` rồi `_torroba_primary`. Mỗi câu một pattern, không ép A–B–A. Id lấy bảng mới. Cửa `bpm <= 72 → castillo` cũng bỏ trên đường này.

Pedal không đổi pattern.

---

## 3. Pattern theo nhịp và BPM

Ba bảng dưới là primary của vùng mở. Vùng cuối chép id đó. Contrast lấy ở mục 4, từ primary và từ mood của vùng mở. Cửa `bpm <= 72 → castillo` bỏ.

Chỉ đứng pattern có lưới của nhịp đó.

Sonatina chỉ còn một ô trong cả bảy pattern: B của 4/4 khi A là Olite. Rally, selloff, chương 3/4 và scherzo không giao cả vùng A cho Sonatina.

Juglar chỉ đứng trên 3/4. Trên 4/4 và 6/8, `_render_juglar_bar` rơi `_downbeat_only`: một nốt, không bộ ba. Danza đã có lưới 3/4 (hợp âm staccato ở móc 0, đáp ở móc 1, 2 và 4) và lưới 6/8 (hợp âm ở móc 0 và 3). Danza không vào 4/4.

| 4/4, 90–108 BPM | A | Vì sao |
|---|---|---|
| calm | Castillo | Nốt hát dài, bass một phách |
| rally | Olite | Nét chạy 4/4, không trải Sonatina cả vùng |
| selloff | Castillo | Nốt dài. Vòng hợp âm đi xuống vẫn ở dialect |
| volatile | Olite | Lưới 4/4 của chương nhanh |

1W là 90. 1M I, 1M IV, 3M I, tháng mở 1Y (100) và tháng 12 (96) là 4/4. 3M III là 108, vẫn bảng này.

| 3/4, 60–72 BPM | A | Vì sao |
|---|---|---|
| calm | Castillo | Tempo của nốt ngân |
| rally | Juglar | Bộ ba tremolo trên 3/4 |
| selloff | Castillo | Nốt dài |
| volatile | Danza | Hợp âm staccato đã có lưới 3/4 |

1M II là 72. 3M II là 60. Chương giữa 1Y là 66.

| 6/8, 108–120 BPM | A | Vì sao |
|---|---|---|
| calm | Danza | Hợp âm staccato, đúng tempo scherzo |
| rally | Alcaniz | Điệu 6/8 |
| volatile | Fandanguillo | Quạt, lưới 6/8 |
| selloff | Fandanguillo | Vẫn là điệu. Castillo ngân cả ô không đứng ở 120 |

1M III là 120. Scherzo 1Y (closer, sau khi guitar đổi 3/4 sang 6/8) là 108.

---

## 4. Contrast, vẫn trong cùng nhịp

B khác A. Cùng họ nhịp.

| A | B trên 4/4 | B trên 3/4 | B trên 6/8 |
|---|---|---|---|
| Castillo | Olite | Juglar khi vùng A là calm. Danza khi vùng A là selloff | — |
| Olite | Sonatina | — | — |
| Juglar | — | Danza | — |
| Danza | — | Juglar | Alcaniz |
| Alcaniz | — | — | Danza |
| Fandanguillo | — | — | Danza |

Sonatina không có hàng A. Nó chỉ là B của Olite trên 4/4, tức chương 4/4 `volatile`, và chương 4/4 `rally` vì rally chọn Olite làm A.

Vùng Juglar hát bộ ba trên mọi câu của vùng, kể cả câu `closes`. Ô 68 là câu đóng cuối vùng B. `thin` phủ cả câu đóng thì 2:50 vẫn là một nốt mỗi phách. `thin` của Juglar chỉ là ô cuối của vùng. Vùng B hết ở ô 70, nên ô 68 là ô áp chót và 2:50 là bộ ba. Ô cuối vùng hát một nốt hết phách, đó là chỗ thở.

`_grid_state` dùng chung cho Juglar, Alcaniz và Olite. Nhánh `rise < 3` thành `full` chỉ khi pattern là `torroba_tremolo`. Alcaniz giữ ô mềm. Olite giữ ô thưa. `pushed` của hai pattern đó giữ. Juglar không dùng `pushed`: câu `rise < 3` là `full`, có accent ở móc 0. Giá đi ngang vẫn ra bộ ba, vì cao độ lặp là tremolo của *Simancas*.

ACB 1M sau bảng này:

| Chương | Hôm nay | Sau |
|---|---|---|
| I, selloff, 4/4 96 | Sonatina | Castillo — Olite — Castillo |
| II, calm, 3/4 72 | Castillo — Juglar — Castillo, Juglar đang thưa | Castillo — Juglar — Castillo, thân Juglar là bộ ba |
| III, selloff, 6/8 120 | Castillo — Sonatina — Castillo | Fandanguillo — Danza — Fandanguillo |
| IV, rally, 4/4 96 | Sonatina | Olite — Sonatina — Olite |

---

## 5. Bass dây buông

Ù hết khi bass Castillo không còn ngân cả ô, và bass Juglar không còn búng mỗi phách.

Luật độ dài chỉ cho thân Castillo, thân Juglar, và ô cửa đang ngân cả ô:

- Một cú ở móc 0, dài một phách.
- Cú sau cách ít nhất một móc đơn. Với một cú mỗi ô, cú sau đã nằm ở ô kế.
- Không bỏ cú mới chỉ vì cùng cao độ. Luật đó tắt pedal Castillo khi hợp âm đứng yên, và xóa hai cú dây buông trong ô của Danza 6/8, Alcaniz và Olite.

Lead của Castillo vẫn ngân cả ô. Kiểu 7 và kiểu 8 chỉ mở khi BPM ≤ 72, nên Castillo của chương I ở 96 BPM vẫn là nốt hát ngân, bass một phách.

`_juglar_motor` đã là bass dài một móc ở phách 0. Chỉ `_juglar_hold` đang `bass_length=ctx.epb`. Cửa Castillo đang `bass_length=ctx.epb` rút còn một phách ở móc 0. Cửa còn lại giữ cú điệu.

---

## 6. Dòng tên trên chart

Chuỗi vẫn là `pattern_form`: `Castillo — Juglar — Castillo (3/4, 72 BPM)`. 1D để tên pattern trên title và `movement` là null, như hiện tại.

`ReplayRoom` chỉ gọi lại span khi `audible` chuyển true, rồi bỏ qua chương đã có tên. Effect thêm index chương. Lần lấy đó điền mọi tên đang trống, không chỉ chương vừa vào. Tên vẫn trống nếu file soạn xong trong lúc đang đứng ở chương đó. Dòng hiện khi sang chương sau.

`SPAN_REVISION` tăng một nấc. File audio soạn trước đợt này hết hạn, vì hàng pattern và độ dài bass đổi. Tên in ra từ lần soạn mới.

---

## 7. Chỗ sửa khi thực hiện

- `backend/app/sonify/guitar_torroba.py`: `_torroba_primary`, `_torroba_contrast`, `_grid_state` chỉ nhánh Juglar, `_render_castillo_bar`, `_render_juglar_bar`. `_select_body` đi cùng bảng mới, vẫn một pattern mỗi câu.
- `backend/app/sonify/guitar_patterns.py`: nhánh Torroba trong `_assign_macro` và `form_pattern_ids`. Hàm tên đọc cách chia mục 2, kể cả chương không có bridge.
- `backend/app/sonify/guitar_torroba_doors.py`: `bass_length` của cửa Castillo và của `_juglar_hold`. `_juglar_motor` giữ nguyên.
- `backend/app/sonify/audio.py`: `SPAN_REVISION`.
- `src/musicalize/ReplayRoom.tsx`: effect phụ thuộc index chương và điền mọi tên đang trống.
- `backend/tests/test_program.py`: chương I và IV in ba tên. Ngày 34 ô vẫn một tên, selloff là Castillo, rally là Olite.
- `backend/tests/test_sonify_guitar_torroba.py`: bảng mục 3 và mục 4, ô 68 của vùng Juglar là bộ ba, ô cuối vùng là nốt đen, bass Castillo và Juglar không dài quá một phách, Alcaniz và Olite vẫn còn `thin` và `pushed`.
- `backend/tests/test_sonify_guitar_torroba_doors.py`: cửa Castillo và `_juglar_hold` đổi độ dài bass. `_juglar_motor` không đổi.
- `docs/sonify-guitar-torroba-castillos-frames.md` mục 2 và `docs/sonify-guitar-torroba-plan.md` mục 7: thay hàng một pattern và hàng `BPM ≤ 72 → castillo` bằng bảng mục 3 và mục 4 của file này.

Không đụng `span.py`.
