# Torroba: A–B–A, tempo, và bass ngắn

> **Trạng thái**: đã vào code.
> **Thay cho**: hàng “một pattern cả chương” trong [`docs/sonify-guitar-torroba-castillos-frames.md`](./sonify-guitar-torroba-castillos-frames.md) mục 2, và hàng `BPM ≤ 72 → castillo` trong [`docs/sonify-guitar-torroba-plan.md`](./sonify-guitar-torroba-plan.md) mục 7.
> **Giữ**: 1D một pattern, id lấy bảng 4/4 mới. Texture (Arada, Float, Rasgueado, …) vẫn không lên dòng chương. Không thêm id pattern mới. Không sửa cờ `bridge` / `trio` trong `span.py`, vì các nhà khác đọc cùng form đó.

Ba việc cùng một đợt: mọi chương ngoài 1D hát ít nhất hai pattern theo A–B–A, pattern khớp nhịp và BPM, bass dây buông không ngân chồng. Dòng tên trên chart in đúng hàng đó.

---

## 1. Việc đang nghe

ACB 1M, Guitar, Torroba, giọng nhà Si♭. Bốn chương. Cột nhịp và BPM đã là **sau retarget tempo** (đợt 96–140); cột pattern là bảng pattern **trước** đợt này, tức cái đang nghe ở rev 69. Trạng thái đã vào code nằm ở bảng `Hôm nay / Sau` cuối mục 4.

| Chương | Nhịp đang chạy | Mood | Tên trong file audio | Pattern đang hát |
|---|---|---|---|---|
| I | 4/4, 104 | selloff | Sonatina | Cả chương Sonatina. Không có vùng B |
| II | 3/4, 96 | calm | Castillo — Juglar — Castillo | 0:19–1:26 Castillo, 1:26–2:11 Juglar, 2:11–3:00 Castillo |
| III | 6/8, 120 | selloff | trống, chưa soạn | Sẽ là Castillo — Sonatina — Castillo |
| IV | 4/4, 120 | rally | trống, chưa soạn | Cả chương Sonatina nếu mọi slot cùng rally |

Chương II tại 2:07 đang ở ô 68, gần bốn giây cuối của vùng Juglar. Giá chương này chỉ chạy 21.00–21.45. Castillo hai bên ngân cả nốt hát và bass suốt ô, 1,875 giây ở 96 BPM, rồi ô sau búng lại.

Ba mốc trên là `bars × beats / bpm` của chính chương II sau retarget: 96 ô 3/4 ở 96 BPM là 1,875 giây một ô, nên ô 10 (hết warmup) ở 0:19, ô 46 (đầu vùng B) ở 1:26, ô 70 (A trở lại) ở 2:11, hết ô 96 ở 3:00. Không chép lại mốc của bản 72 BPM: cùng những ô đó ở 72 BPM là 0:25 / 1:55 / 2:55 / 4:00, đúng bằng mốc cũ, nên phép đo khớp.

Juglar có ba texture, chọn trong `_grid_state`. Chỉ một texture là tremolo có accent.

| Texture | Cửa | Nghe |
|---|---|---|
| `full` | `rise >= 3`, câu chưa đóng | Ba chùm bốn cú p-a-m-i mỗi phách: ngón cái ở phách, ba ngón ở `+0,25 / 0,5 / 0,75`. Accent chỉ cú đầu của phách 0. Đây là tremolo *Simancas* |
| `pushed` | Không còn ra cho Juglar: `_grid_state` trả `full` cho mọi câu `torroba_tremolo`, kể cả câu `rise < 3` | Nếu có thì vẫn là chùm bốn cú, ba ngón theo `JUGLAR_FINGERS` (0 / −3 / −4) |
| `thin` | Câu lẻ không nằm trong hàng pattern, hoặc ô cuối vùng (chọn sau, trong `_render_juglar_bar`) | Một nốt ngân hết phách. Ba ngón nghỉ, chỉ còn cú móc 0. Không có tremolo |

Chương II là tích lũy, biên giá hẹp, nên hầu hết câu có `rise < 3`. Với Juglar, điều đó **không** đổi lưới: câu `rise < 3` và câu đóng cũng là `full`, nên cả vùng B hát ba chùm bốn cú mỗi ô. `pushed` và `thin` không ra trong một vùng Juglar đủ dài; `thin` chỉ còn ở câu lẻ. Ô cuối vùng được chọn trong `_render_juglar_bar`: ô 69 hát một nốt hết phách. Ô 68 cách ô đó một ô, nên vẫn là ba chùm bốn cú. Cửa intro/outro của Juglar cũng giữ lưới móc đơn, không có chùm: chùm chỉ thuộc thân bài, nên đừng “đồng bộ” cửa theo thân bài.

Chart chỉ in `Suite ACB 1M in B-flat`. File chương II đã có `movementName`. Phòng nghe lấy manifest một lần lúc tiếng bắt đầu; lúc đó chương II chưa ghi tên, và lượt làm mới không chạy lại.

---

## 2. A–B–A theo slot đã có

1D là ngày 34 ô, 4/4. Cửa `bars == 34 and kind == "4/4"` giữ một pattern. Id lấy bảng 4/4 ở mục 3. Rally của ngày đó là Olite, selloff là Castillo. Nhánh này không giữ bảng cũ, nơi cả hai mood đều là Sonatina. Test “vẫn một tên” cũng khóa id.

Chương đã có từ ba slot phrase, và không có `bridge` hay `trio`, không cắt theo số ô. Chương I guitar sau `_retarget_pedal(intro=4, outro=4)` là 36, 24 và 28 ô trên `regime_slot` 0, 1, 2, `bridge=False`. Chương IV sau `outro=8` là 36, 24 và 24 ô, cùng luật ba slot. Số 36, 24, 28 chỉ đúng chương I. Ở rev 69, `_assign_macro` khi không có contrast gọi `_torroba_primary` từng slot, và cả chương selloff ra Sonatina. Sau [đợt tempo](./sonify-guitar-torroba-tempo-plan.md), primary của 4/4 selloff là Castillo và cả chương selloff ra `Castillo — Danza — Castillo`.

Slot 0 và slot cuối hát một primary. Slot giữa không hát contrast suốt 24 ô. Ở 96 BPM đó là một phút Olite nằm giữa Castillo, đúng dạng hai bài đặt cạnh nhau. Bridge là 8 ô nằm giữa slot đó. Hai đầu slot giữa vẫn hát primary. 24 ô thì 8, 8, 8. Slot khác 24 ô: 8 ô vẫn nằm giữa, hai đầu đi theo `split_into` của phần còn lại, ô lẻ về phía cuối slot.

Chương đã có `bridge` hoặc `trio` giữ nguyên vùng B đó. Chương II và scherzo không cắt 8 ô. Không chia thêm.

Một slot phrase, và không phải ngày 34 ô: tuần một phiên là 32 ô. `split_into(32, 3)` ra 10, 11, 11. Phần dư nằm trên hai phần cuối, mỗi phần thêm một ô. Không phải 10, 10, 12. Câu lấy pattern của ô đầu tiên trong slot.

Hai slot phrase và không có bridge, như tháng mở 1Y và tuần hai phiên: slot 0 là primary. Slot 1 chia đôi theo ô. Nửa đầu là contrast. Nửa sau chép primary. Ô lẻ của nửa đó về phía trở lại. Vùng chỉ toàn warmup, intro, outro hoặc cooldown không phải một slot. Outro của tháng mở đứng slot 2, nên tháng đó vẫn là hai slot phrase. Slot 1 dài 36 ô, nửa contrast là 18 ô.

Tuần từ ba phiên trở lên không giao contrast cho mọi phiên giữa. Tuần năm phiên theo luật đó thì B chiếm ba phiên. Contrast là 8 ô phrase nằm giữa phiên giữa. Đếm từ 0, phiên giữa là `count // 2`. Ba phiên thì phiên 1. Năm phiên thì phiên 2. Bốn phiên thì phiên 2, phiên bắt đầu đúng điểm giữa bài. 32 ô phrase của phiên giữa ra 12, 8, 12. Hai đầu phiên đó và mọi phiên khác hát primary. Hàng này không cắt ngang một phiên.

Primary chọn một lần, từ mood của slot 0: `_majority_mood` trên slot đó. Chương có bridge cũng chỉ đếm slot 0. Các ô A nếu gồm cả đoạn trở lại thì đoạn cuối vẫn kéo primary. Vùng cuối chép đúng id đó. Không gọi `_torroba_primary` lần nữa. Hai đầu tự đọc mood của mình thì dòng không còn A–B–A, và `pattern_form` gộp hai tên kề nhau thành một.

Contrast là hàng mục 4 của primary đó. Hàng Castillo trên 3/4 đọc mood của slot 0: calm thì Juglar, selloff thì Danza. `_contrast_pattern` hôm nay truyền mood của vùng giữa vào `_torroba_contrast`. Kế hoạch này không truyền mood đó.

`form_pattern_ids` hôm nay trả một tên khi không có bridge, dù hàng đã là ba id. Chương I và IV vẫn in một tên nếu hàm này chưa đọc cách chia trên. Hàm trả `[primary, contrast, primary]`. Contrast của chương không bridge là 8 ô giữa slot giữa, không phải cả slot. `pattern_form` chỉ gộp tên kề nhau. Castillo — Olite — Castillo vẫn là ba tên, vì hai Castillo không kề nhau.

Câu không khung đi `_select_body` rồi `_torroba_primary`. Mỗi câu một pattern, không ép A–B–A. Id lấy bảng mới. Cửa `bpm <= 72 → castillo` cũng bỏ trên đường này.

Pedal không đổi pattern.

---

## 3. Pattern theo nhịp và BPM

Ba bảng dưới là primary của slot 0. Vùng cuối chép id đó. Contrast lấy ở mục 4, từ primary và từ mood của slot 0. Cửa `bpm <= 72 → castillo` đã bỏ: `_torroba_primary` và `_torroba_contrast` không đọc `ctx.bpm` nữa, nên mỗi bảng dưới đúng ở **mọi** tempo, và bảng đọc `ctx.kind` chứ không đọc số BPM. Ba header chỉ ghi dải BPM có thật sau retarget, không phải một cửa.

Chỉ đứng pattern có lưới của nhịp đó.

Sonatina không còn ô nào trong bảng: `_torroba_primary` không trả nó, và không contrast nào trả nó, kể cả B của Olite (B của Olite trên 4/4 là Castillo). Renderer `sonatina` vẫn còn, chỉ mở khi test hay lời gọi ép nó; chương không đi qua đường đó. Rally, selloff, chương 3/4 và scherzo không giao cả vùng A cho Sonatina.

Juglar chỉ đứng trên 3/4. Trên 4/4 và 6/8, `_render_juglar_bar` rơi `_downbeat_only`: một nốt, không chùm. Danza đã có lưới 3/4 (hợp âm staccato ở móc 0, đáp ở móc 1, 2 và 4) và lưới 6/8 (hợp âm ở móc 0 và 3). Danza không vào 4/4.

| 4/4, 96–132 BPM | A | Vì sao |
|---|---|---|
| calm | Castillo | Nốt hát dài, bass một phách |
| rally | Olite | Nét chạy 4/4, không trải Sonatina cả vùng |
| selloff | Castillo | Nốt dài. Vòng hợp âm đi xuống vẫn ở dialect |
| volatile | Olite | Lưới 4/4 của chương nhanh |

Sau retarget, 4/4 chỉ còn ở rally và volatile. Đo bằng `tmp/diag_torroba_specs.py`: 1W rally, 1M IV, 1Q I và tháng 12 của 1Y đều **120**; volatile **132** (3M III từ 108). Chương `calm` và `selloff` 4/4 đổi sang 3/4 trong `retarget_torroba_meter` **trước** khi đọc sàn, nên chúng đọc bảng 3/4. 1D giữ **96** vì đi `GUITAR_BPM['torroba']`, không có `_spec`.

| 3/4, 96–124 BPM | A | Vì sao |
|---|---|---|
| calm | Castillo | Nốt hát dài, bass một phách; Juglar là contrast |
| rally | Juglar | Ba chùm bốn cú trên 3/4 |
| selloff | Castillo | Nốt dài |
| volatile | Danza | Hợp âm staccato đã có lưới 3/4 |

1M II là **96**. 3M II là **96**. Chương giữa 1Y là **96**. selloff 3/4 là 104, rally 112, volatile 124. 3M III ở calm đổi sang 3/4 và giữ 108, vẫn bảng này.

Hai hàng nhanh của bảng này — `rally` 112 và `volatile` 124 — chỉ xảy ra ở những ô **vốn đã** 3/4: `1M II`, `3M II`, và chương 2 / 5 / 8 / 11 của `1Y`. Ô 4/4 chỉ đổi sang 3/4 khi mood là `calm` hoặc `selloff` (`retarget_torroba_meter`), và hai mood đó đọc 96 / 104. Nên chương để nghe thử tremolo ở 7,5 và 8,3 cú/giây là `1M II` / `3M II`, hoặc ô 3/4 của `1Y`. Quét 112 mã × `1M`/`3M`/`1Y` (`tmp/diag_juglar_fast.py`): 169 chương 3/4 từ 112 BPM trở lên, **cả 169 hát Juglar**, không có chương nào rơi về `sonatina`.

| 6/8, 108–140 BPM | A | Vì sao |
|---|---|---|
| calm | Danza | Hợp âm staccato, đúng tempo scherzo |
| rally | Alcaniz | Điệu 6/8 |
| volatile | Fandanguillo | Quạt, lưới 6/8 |
| selloff | Fandanguillo | Vẫn là điệu. Castillo ngân cả ô không đứng ở 120 |

1M III là **120**. Scherzo 1Y (closer, sau khi guitar đổi 3/4 sang 6/8) rally là 120, calm là 108. 6/8 selloff là 116, volatile 140.

---

## 4. Contrast, vẫn trong cùng nhịp

B khác A. Cùng họ nhịp.

| A | B trên 4/4 | B trên 3/4 | B trên 6/8 |
|---|---|---|---|
| Castillo | Olite | Juglar khi vùng A là calm. Danza khi vùng A là selloff | — |
| Olite | Castillo | — | — |
| Juglar | — | Danza | — |
| Danza | — | Juglar | Alcaniz |
| Alcaniz | — | — | Danza |
| Fandanguillo | — | — | Danza |

Bảng không còn ô Sonatina. Câu `_torroba_contrast(..., "olite")` trên 4/4 trả Castillo, và trên 4/4 chỉ có Olite làm A (rally, volatile), nên dòng tên của hai chương đó là `Olite — Castillo — Olite`. Sonatina chỉ còn là renderer gọi tay trong test.

Vùng Juglar hát ba chùm bốn cú trên mọi ô của vùng, trừ ô cuối. Chương II, sau warmup 6 ô, vùng B là ô 46 đến hết ô 69. Ô 70 là ô đầu của A trở lại. Ô cuối vùng là 69. Ô 68 là ô áp chót, và 2:07 rơi vào ô đó.

`_grid_state` gán một chế độ cho cả câu. Câu đóng của đoạn này phủ cả ô 68 và ô 69. Gán `full` thì ô 69 cũng thành chùm. Gán `thin` thì 2:07 vẫn là nốt đen. Ô cuối vùng được chọn trong `_render_juglar_bar`: ô 69 hát một nốt hết phách, mọi ô Juglar trước đó hát ba chùm bốn cú, kể cả câu đóng bên trong vùng. Câu `closes` của Juglar không còn là `thin`.

`_castillos_figure_plan` hôm nay gắn kiểu 9 cho cả câu `thin`. Kiểu 9 chỉ gắn ô cuối của vùng Juglar. Không phủ cả câu.

`_grid_state` dùng chung cho Juglar, Alcaniz và Olite. Nhánh `rise < 3` thành `full` chỉ khi pattern là `torroba_tremolo`. Alcaniz giữ ô mềm. Olite giữ ô thưa. `pushed` của hai pattern đó giữ. Juglar không dùng `pushed`: câu `rise < 3` là `full`, có accent ở cú đầu phách 0. Giá đi ngang vẫn ra chùm bốn cú, vì cao độ lặp là tremolo của *Simancas*.

ACB 1M sau bảng này:

| Chương | Hôm nay | Sau |
|---|---|---|
| I, selloff, 3/4 104 | Sonatina | Castillo — Danza — Castillo |
| II, calm, 3/4 96 | Castillo — Juglar — Castillo, Juglar đang thưa | Castillo — Juglar — Castillo, ô 68 là chùm, ô 69 là nốt đen |
| III, selloff, 6/8 120 | Castillo — Sonatina — Castillo | Fandanguillo — Danza — Fandanguillo |
| IV, rally, 4/4 120 | Sonatina | Olite — Castillo — Olite |

---

## 5. Bass dây buông

Ù hết khi bass Castillo không còn ngân cả ô, và bass Juglar không còn búng mỗi phách.

Luật độ dài chỉ cho thân Castillo, thân Juglar, và ô cửa đang ngân cả ô:

- Một cú ở móc 0, dài một phách.
- Cú sau cách ít nhất một móc đơn. Với một cú mỗi ô, cú sau đã nằm ở ô kế.
- Không bỏ cú mới chỉ vì cùng cao độ. Luật đó tắt pedal Castillo khi hợp âm đứng yên, và xóa hai cú dây buông trong ô của Danza 6/8, Alcaniz và Olite.

Lead của Castillo vẫn ngân cả ô. Không còn cửa `BPM ≤ 72` nào trong code, nên kiểu 7 và kiểu 8 không mở theo tempo nữa; Castillo của chương I ở 104 BPM vẫn là nốt hát ngân, bass một phách.

`_juglar_motor` đã là bass dài một móc ở phách 0 và giữ nguyên. `_juglar_hold` cũng búng bass **một phách** (`2` móc trong 3/4), không ngân cả ô. Thân Juglar búng bass lại ở cả ba phách, qua `_fitting_bass` với ưu tiên `(2, 1)` móc, nên cú bass dài đúng một phách — bass ngắn mà vẫn là một bè: nó hát `max(ba ngón) + 2`, xem mục 5.1 của [`docs/sonify-guitar-torroba-tempo-plan.md`](./sonify-guitar-torroba-tempo-plan.md). Cửa Castillo cũng rút bass còn một phách ở móc 0; cửa còn lại giữ cú điệu.

---

## 6. Dòng tên trên chart

Chuỗi vẫn là `pattern_form`: `Castillo — Juglar — Castillo (3/4, 96 BPM)`. 1D để tên pattern trên title và `movement` là null, như hiện tại.

`ReplayRoom` hỏi lại span khi tiếng đã phát và chương đang nghe còn trống tên. Mỗi lần hỏi điền mọi tên đang trống. Hỏi lại cho đến khi chương đó có tên, hoặc server báo file đã soạn mà tên vẫn trống. Đứng yên ở chương đang nghe vẫn thấy dòng tên.

`SPAN_REVISION` tăng một nấc. File audio soạn trước đợt này hết hạn, vì hàng pattern, tempo và độ dài bass đổi. Lần này `"69"` → `"70"`, sau khi hàng pattern đổi (`aba-tempo`) và hình Juglar đổi sang chùm bốn cú ([`docs/sonify-guitar-torroba-tempo-plan.md`](./sonify-guitar-torroba-tempo-plan.md) mục 6). Tên in ra từ lần soạn mới.

---

## 7. Chỗ sửa khi thực hiện

- `backend/app/sonify/guitar_torroba.py`: `_torroba_primary`, `_torroba_contrast`, `_grid_state` chỉ nhánh Juglar, `_render_castillo_bar`, `_render_juglar_bar` chọn ô cuối vùng, `_castillos_figure_plan` gắn kiểu 9 đúng ô đó. `_select_body` đi cùng bảng mới, vẫn một pattern mỗi câu. Lần đổi hình Juglar sau đó cũng nằm trong file này: `JUGLAR_FINGERS` / `JUGLAR_STEP` / `_juglar_thumb`, `_first_of_beat`, `_juglar_cluster`, `_respell_juglar_cluster`, `apply_juglar_thumb`.
- `backend/app/sonify/guitar_patterns.py`: nhánh Torroba trong `_assign_macro` và `form_pattern_ids`. Hàm tên đọc cách chia mục 2, kể cả chương không có bridge. Một dòng `low = apply_juglar_thumb(ctx, lead, low, patterns)` ngay sau arch.
- `backend/app/sonify/guitar_torroba_doors.py`: `bass_length` của cửa Castillo và của `_juglar_hold`. `_juglar_motor` giữ nguyên, và cửa `torroba_tremolo` vẫn một cú mỗi đầu phách — chùm chỉ thuộc thân bài.
- `backend/app/sonify/audio.py`: `SPAN_REVISION`.
- `src/musicalize/ReplayRoom.tsx`: effect phụ thuộc index chương và điền mọi tên đang trống.
- `backend/tests/test_program.py`: chương I và IV in ba tên, và contrast chỉ dài 8 ô giữa slot giữa. Ngày 34 ô vẫn một tên, selloff là Castillo, rally là Olite. Tuần một phiên chia 10, 11, 11.
- `backend/tests/test_sonify_guitar_torroba.py`: bảng mục 3 và mục 4, ô 68 của vùng Juglar là một chùm bốn cú, ô 69 là nốt đen, kiểu 9 không phủ ô 68, bass Castillo và Juglar không dài quá một phách, Alcaniz và Olite vẫn còn `thin` và `pushed`. Bốn test Juglar khóa thêm: chùm là 1 ngón cái + 3 ngón, `divisions = 4` và chín `<type>16th</type>` không tuplet, cú hát ở `+0,25`, và ngón cái `max(ngón) + 2` sau arch.
- `backend/tests/test_sonify_guitar_torroba_doors.py`: cửa Castillo và `_juglar_hold` đổi độ dài bass. `_juglar_motor` không đổi.
- `docs/sonify-guitar-torroba-castillos-frames.md` mục 2 và `docs/sonify-guitar-torroba-plan.md` mục 7: thay hàng một pattern và hàng `BPM ≤ 72 → castillo` bằng bảng mục 3 và mục 4 của file này.

Không đụng `span.py`.
