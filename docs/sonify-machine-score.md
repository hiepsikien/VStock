# Máy đo chấm điểm sonify

Phương án chấm phần máy đo. Người đo nghe sau, trên cùng một rổ, và không cộng vào vector.

Giai đoạn 1 là một lượt đo trên object `Score` cộng với nến nguồn. Luật nhận một thay đổi của renderer nằm ở mục 8, và chưa chạy được trên bốn file đang có. Bốn định nghĩa khóa trước khi viết máy nằm ở mục 3 (`m`), mục 4 (F5), mục 6 (hai quan sát chưa phải cổng), và mục 4 (F6).

Máy đọc `Score` trong không gian Đô và nến đã đưa vào `render`. MusicXML không thay `Score`: lúc xuất, `key.semitones` được cộng vào cao độ, bass có `octave-change`, còn regime và `score.liquidity` không có trên XML. Đọc XML rồi map về thang Đô sẽ trượt cung. File WAV để ở một phép kiểm phát riêng. `humanize` chỉ đẩy velocity. Cao độ và chữ dynamic in ra không đổi, nên không làm lệch vector.

Các hằng số dưới đây lấy từ `backend/app/sonify/` trên `main`: `quantize.py`, `dynamics.py`, `chords.py`, `form.py`, `phrasing.py`, `render.py`, `daily_frame.py`, `playback.py`.

## 1. Sản phẩm công bố

Máy giai đoạn 1 là `measure_daily` trong `backend/app/sonify/meter.py`. Nó nhận nến và `Score` đã render, trả một `DailyRecord`.

`planner_character`, `price_low`, `price_high` và `source_groups` không nằm trên `Score`. Máy chỉ khớp `render` khi các đối số đó được truyền lại đúng giá trị đã dùng lúc viết bản. Bỏ `planner_character` thì F6 chấm với `character=None`.

Mỗi bản cho ra ba khối:

| Khối | Ý nghĩa |
|---|---|
| Cổng | Đạt hoặc trượt. Chỉ những hợp đồng renderer hôm nay đang giữ. |
| Trung thực | Phần hình giá còn lại trên đường giai điệu đã khâu, và chữ liquidity như một kiểm tra hồi quy. |
| Hợp lệ | Ngữ pháp đếm được: âm hợp âm, dẫn giọng, độ nhàm. Ngưỡng phần vị của M3 và M4 chưa khóa. |

Điểm công bố là bộ ba này. Sheet thêm một điểm tổng để đọc nhanh. Đó là trung bình không trọng số của những tỷ lệ đã nằm trên `[0, 1]`: F1, F2 sau khi Spearman được đưa về `(ρ+1)/2`, F4, và M1 của lead/support. Thành phần thiếu được bỏ, không tính là `0`. Giá trị ghi kèm số thành phần trên mẫu số `4`, ví dụ `0,74 · 3/4`. Cổng, F3, F5, F6, M2, M3, M4 và bốn đối chứng đứng ngoài, vì chúng chưa cùng thang hoặc mục 8 chưa dùng chúng làm điểm. Tổng có trọng số vẫn chờ rổ nghe. Chip `QA` vẫn chỉ là ba cổng.

App mobile hiện một chip `QA` trong khối nghe của giao hưởng ngày. Chip mở đúng bản ghi này: cổng, F, M, và bốn đối chứng. Mỗi dòng có nút `i` mở câu giải thích của chỉ số đó. Jazz, guitar, ambient, tối giản, và span `1W`–`1Y` không có chip, vì giai đoạn 1 chưa chấm những bản đó. `humanize` không đổi số trên sheet.

`bar_quantization_loss` trong `quantize.py` đứng ngoài vector. Đó là mục tiêu planner đang tối thiểu. `research/sonify/harmony_benchmark.py` so số nốt bị bẻ giữa Markov và vòng lặp cố định trên lưới 30 ô (`range(30)`, `assign_source_bars`), trong lúc `render()` mặc định đóng khung 34 ô. Script đó chẩn đoán planner. Nó không phải harness của giai đoạn 1. Bộ đo mới tự dựng lưới framed.

## 2. Đồng hồ và chuỗi giá thô

Giai đoạn 1 dùng bản ngày, giao hưởng, `4/4`. `playback.py` khóa 34 ô: ô `0–1` là đầu khung, ô `2–31` là thân giá, ô `32–33` là cuối khung. `assign_daily_ambient_bars` trải mọi nến lên đúng 30 ô thân. Hai ô đầu và hai ô cuối có nhóm nguồn rỗng.

`r` dựng cùng cách `_compose`: với mỗi ô, `resample` các giá đóng cửa của nhóm nguồn ra 8 móc, rồi `price_to_scale_index` trên `c_major_scale`. Bản ngày để `mode` mặc định `"major"`, nên thang là Đô trưởng. Ô khung không có nến thì không sinh `r`. Móc của thân là `bar * 8 + beat * 2`, với `beat` tính bằng phách đen. Phách mạnh là móc `0` và `4`.

Trong `DAILY_ENSEMBLE_SPEC`, hai đầu khung có kind `intro` và `outro`, không phải `warmup` và `cooldown`. `liquidity_windows_for` chỉ bỏ kind `warmup` / `cooldown`, nên vẫn đưa ô `0–1` và `32–33` vào `score.liquidity`. Hai cửa sổ đó không có nến. Volume của chúng là median mà `average_liquidity` lấp vào chỗ trống. Mọi chỉ số thanh khoản cắt theo ô `2–31`, không cắt theo kind của section.

## 3. Đường `m`

`m` là đường khâu của `score.high`, `score.lead` và `score.support`, trong không gian Đô của `Score`, trên thân ô `2–31`. Violin một mình không phải contour của bản.

`melody_parts` chia đường đã snap. Cello (`support`) nhận đoạn chìm dưới Sol3 (MIDI `55`, `violin_lowest`) và giữ đến khi giá lên lại Đô4 (MIDI `60`, `cello_handback`). Flute (`high`) nhận đỉnh câu. Violin (`lead`) nhận phần còn lại. Hai bè chồng nhau lúc giao: cello với violin tối đa `CELLO_OVERLAP` (2 móc), flute với violin tối đa `FLUTE_OVERLAP` (2 móc) rồi violin nhường.

Tại mỗi móc `t` của thân, các bè đang kêu là nốt có `midi` phủ `t`:

1. Có `high` thì `high` sở hữu móc đó, kể cả hai móc chồng với violin. Đỉnh tai nghe nằm trên flute, và phải có mặt trong F4.
2. Không có `high`, mà `lead` và `support` cùng kêu: bè có onset muộn hơn sở hữu móc. Lead-in của dovetail chép cùng cao độ. Trail giữ nốt cũ đè dưới bè vừa nhận dòng. Onset muộn là bè đang giữ dòng.
3. Còn lại thì bè duy nhất đang kêu sở hữu móc.

Nốt sở hữu đổi sang chỉ số thang Đô. Không cộng `key.semitones`.

Lead và support lưu đúng MIDI đã snap. High không lưu MIDI đó. `flute_harmony_pitch` viết quãng 3 hoặc quãng 5 đúng phía trên nốt snap (3, 4 hoặc 7 semitone), ưu tiên âm hợp âm. Vòng sau đó trong `_flute_and_violin_dovetail` hạ từng bát độ cho tới khi nốt không vượt `flute_ceiling`. Trần này là 88 với giọng Đô. `register_for` trừ thêm `key.semitones` khi giọng nằm phía thăng. Đỉnh giá của mọi phiên bị min–max kéo tới MIDI 96, cao hơn trần.

Bước ngược có hệ thống nằm lúc vượt trần, giữa vùng cao, không nằm ở móc `r` đạt cực đại. Giai điệu từ Đô6 (84) lên Rê6 (86) là lúc nốt vượt `violin_ceiling` (84) và quãng 3 chạm `flute_ceiling`. Flute đang ở Mi6 (88). Nốt mới là Fa6 (89), vượt trần, bị hạ thành Fa5 (77). Giá đi lên một bậc thang. Đường khâu đi xuống sáu bậc.

Đỉnh phiên là MIDI 96. Với quãng 3, nốt flute ở đó là Mi7 (100), hạ một lần về Mi6 (88). Bước viết liền trước đi từ Si6, hạ về Rê7 rồi về 86. Hướng của bước đó vẫn đi lên, cùng chiều với giá.

F1 giữ mọi bước MIDI đã ghi trên high, kể cả nốt đã hạ. Không đi tìm một bước ngược tại móc đỉnh để xác nhận chỉ số. Không thấy bước đó ở cực đại của `r` không có nghĩa là máy đo bỏ qua lần hạ bát độ. F4 cũng lấy cực trị trên MIDI đã ghi. Không lấy lại hướng của nốt snap. F2 chỉ dùng móc lead và support. F3 tách hai tập. Tập lead/support là độ bẻ của snap. Tập high gồm quãng 3 hoặc quãng 5, và gồm cả bước −7 bậc thang của mỗi lần hạ bát độ. Độ lệch hai hoặc bốn bậc trên high chưa phải toàn bộ hóa đơn của bè đó.

Móc không bè giai điệu nào kêu thì `m` khuyết. Không giữ nốt violin vừa nghỉ nếu high hoặc support đang kêu. F1 bỏ một bước chỉ khi `m` khuyết ở một trong hai đầu, hoặc khi `Δr` bằng 0. Giữ nốt violin qua mọi chỗ nó nghỉ sẽ bỏ đúng những bước giá đi lúc dòng đã chuyển sang flute hoặc cello. F1 còn lại chỉ trả lời câu violin có nhúc nhích đúng hướng hay không.

## 4. Vector trung thực

| Mã | Cách tính | Bỏ qua khi | Cách đọc |
|---|---|---|---|
| F1 hướng | Tỷ lệ bước mà dấu `Δr` và dấu `Δm` trùng nhau, trên đường khâu. `m` là MIDI đã ghi, kể cả nốt flute đã hạ bát độ | Dưới 3 bậc thang khác nhau trong `r` | `1` bám hướng. Quanh `0,5` mất contour. Bước ngược lúc vượt trần nằm giữa vùng cao và ở lại trong tỷ lệ. Không yêu cầu nó rơi đúng móc cực đại của `r` |
| F2 mức | Spearman(`r`, `m`) trên phách mạnh thuộc lead hoặc support | Cùng điều kiện ít bậc thang. Móc high không vào phép này | Khớp thứ hạng trong phiên. Không đo phần trăm lợi suất |
| F3 độ bẻ | Trung bình `\|m − r\|` trên phách mạnh, đơn vị bậc thang. Báo riêng lead/support và high | Luôn báo hai số khi có móc | Số lead/support là hóa đơn của snap. Số high gồm quãng 3 hoặc quãng 5 và các bước −7 bậc của lần hạ |
| F4 điểm ngoặt | Recall cực trị của `r` nổi ít nhất 1 bậc thang, khớp cực trị của `m` cùng hướng trong ±1 ô. Cực trị của `m` lấy trên MIDI đã ghi, kể cả nốt đã hạ | Thân không có cực trị nổi | Không lấy lại cực trị của nốt snap. Không thấy bước ngược tại cực đại của `r` không có nghĩa là lần hạ bị bỏ |
| F5 chữ liquidity | Spearman giữa volume cửa sổ (`average_liquidity`) và hạng `p < mp < mf < f` của `score.liquidity`, chỉ cửa sổ nằm trong ô `2–31` | Mọi cửa sổ ô `2–31` cùng một chữ. Span dưới `2×` chưa đủ để bỏ: cửa sổ volume `≤ 0` vẫn là `p` | Kiểm tra hồi quy của `marking_for_volume`. Không phải thanh khoản nghe được |
| F6 regime | Trung bình `chord_bias` trên catalog planner đã xét, trừ trung bình cùng hàm của hợp âm đã chọn trên ô `2–31` | Ô `0–1` và `32–33` | Dương khi hợp âm đã chọn rẻ hơn catalog. Xáo làm lift đổi khi nhãn đổi. Về gần `0` chỉ khi lift gốc đang dương rõ |

`score.liquidity` chính là `marking_for_volume` áp lên các cửa sổ `average_liquidity`. Spearman giữa một bậc thang đơn điệu và input của chính nó thì cao mỗi khi có nhiều hơn một chữ. Đảo volume mà giữ nguyên chữ thì F5 đổi dấu dù không có nốt nào được viết lại. Chữ piano (`piano_marking` gập còn `p` / `mp`), trần `mp` của bass, và groove `chamber` / `half` đứng ngoài F5. Sửa những chỗ đó thì F5 không đổi. Mục 8 không dùng “F5 tăng” để nhận một thay đổi động lực nghe được.

`DAILY_ENSEMBLE_SPEC` bật `borrowed=True`. `REGIME_BIAS` chỉ có 12 hợp âm diatonic. Tra một hợp âm mượn thì thiếu khóa. Planner chấm những hợp âm đó bằng `chord_bias`: hợp âm trong `CHORDS` lấy `_ROOT_REGIME_BIAS` cộng delta character. Hợp âm ngoài bảng lấy sàn `0.08` cộng `_BORROWED_DELTA`. F6 gọi đúng hàm đó, với cùng `character` đã truyền vào planner. Catalog là `chords_for_spec(True)`. Lift bằng trung bình chi phí catalog trừ trung bình chi phí hợp âm đã chọn. Chi phí thấp là được ưu tiên, nên hợp âm đúng regime cho lift dương. Viết phép trừ ngược lại thì “F6 tăng” ở mục 8 nghĩa là hợp âm đắt hơn catalog.

`_ROOT_REGIME_BIAS`: uptrend ưu tiên `C` (chi phí `0`), phạt `A` `0,35` và `E` `0,45`. Downtrend ưu tiên `A`, phạt `C` và `G` `0,35`. Sideway ưu tiên `C`. Đây là chi phí. Thấp là được ưu tiên.

Phiên có dưới 3 bậc thang trong `r`: bỏ F1, F2, F4. Ghi số bậc của `m` thành quan sát. Không có cổng “giai điệu thân không vượt 2 bậc thang”. Giá đứng yên vẫn bị snap sang âm hợp âm, và Markov vẫn đổi hợp âm. Khóa cổng đó thì mọi bản phẳng trượt.

Giá được kéo min–max vào thang của riêng bản. Cỡ bước nhảy mang hình trong phiên. Biên độ lợi suất không nằm trong F2 hay F3.

## 5. Vector hợp lệ

M1 và M2 đọc đường khâu và `score.low`, không đọc riêng violin. M3 và M4 là số thô. Ngưỡng phần vị của chúng hoãn đến khi có rổ.

| Mã | Đối tượng | Vai trò ở giai đoạn 1 |
|---|---|---|
| M1 âm hợp âm | Phách mạnh đang kêu trên đường khâu, pitch class thuộc hợp âm của ô | Lead và support là hợp đồng snap: một lần trượt là lỗi của lượng tử hóa, ghi trên bản. High là quãng phối khí, ghi riêng, không nhập vào tỷ lệ snap |
| M2 dẫn giọng | Bước của `score.low` quá quãng 8. Bước của đường khâu quá quãng 8 không được bước ngược liền sau. Quãng 5 song song trên phách mạnh: cả hai quãng là quãng 5 đúng và cả hai bè cùng đi một hướng. Bước xiên và bước ngược chiều không tính | Số thô. Đây là chỉ số M duy nhất mục 8 có thể dùng, và cũng chỉ sau khi có rổ |
| M3 âm chung | Khi đổi hợp âm, số pitch class giữ lại. Báo trung bình và tỷ lệ lần đổi không chung âm | Số thô. Chưa có ngưỡng |
| M4 nhàm | Entropy bigram pitch-class của đường khâu, hợp âm dài nhất trên thân, số chữ `score.liquidity` khác nhau trong ô `2–31` | Số thô. Chưa có ngưỡng. Calm được phép hẹp chỉ sau khi ngưỡng lấy theo phân vị của cùng character |
| M5 khung | Ô `0` mở `p`. Ô `33` tới `ppp`. Hai đầu khung đạp chủ âm của hợp âm ô đó | Cổng. `apply_daily_frame` đang viết đúng hợp đồng này cho giao hưởng |

## 6. Quan sát, chưa phải cổng

Hai kiểm tra sau ghi vào bản ghi. Chúng không chặn một thay đổi của renderer.

**Mode.** `movement_mode` nhận character và regime đóng. Selloff ra thứ dù regime đóng là gì. Volatile ra thứ chỉ khi regime đóng là downtrend. Regime đóng đó là `classify_window` trên 5 nến cuối và MA của chúng, cùng cửa sổ `boundary_regimes`. `score.regimes` cuối là regime lấy ở đầu câu nhạc (5 nến nguồn đầu của câu), không phải cửa đóng. Quan sát so `score.mode` với `movement_mode(character, closing)` dùng đúng cửa sổ 5 nến cuối. Không truyền `score.regimes` cuối vào hàm này.

Bản ngày không gọi `movement_mode`. `render` truyền `character` và để `mode` mặc định `"major"`. `score.mode` của mọi phiên selloff, và mọi phiên volatile có regime đóng là downtrend, khác kết quả hàm. Character vẫn vào planner qua `_CHARACTER_BAR_CHANGE` (`volatile` `0,45`, `calm` `0,80`, `rally` và `selloff` `0,60`). Quan sát này cho biết dây mode chưa nối, và chưa phải cổng.

**Phiên phẳng.** Điều kiện bỏ F1, F2, F4 khi `r` có dưới 3 bậc là rõ. Trần “`m` không vượt 2 bậc thang” thì renderer không giữ.

Cổng đang khóa, vì renderer đang giữ:

- Volume span dưới `2×` và mọi cửa sổ ô `2–31` có volume dương: `marking_for_volume` trả `mf` cho các cửa sổ đó. `volume ≤ 0` trả `p` trước khi xét `MIN_SPAN_RATIO`, nên một cửa sổ im trong phiên này vẫn là `p` và các cửa sổ dương vẫn là `mf`. Spearman của F5 khi đó vẫn xác định. Cổng “mọi cửa sổ là `mf`” không áp vào phiên có cửa sổ im.
- M5, như bảng trên.
- Mọi nến nguồn nằm trên ô `2–31`.

## 7. Bản đối chứng

Đối chứng làm trên cặp (chuỗi đem so, bản `Score` đã viết). Không render lại.

F1 là tỷ lệ bước cùng dấu, từ `0` đến `1`. Gần `1` là bám hướng, quanh `0,5` là mất contour, gần `0` là đi ngược. Tỷ lệ không có dấu âm. Đảo giá rồi chấm lại giai điệu cũ làm tỷ lệ tụt và xoay quanh `0,5`. Render lại một hệ đang bám giá thì F1 đứng yên, và phép thử không còn nói gì về chỉ số. Biên `0,02` ở mục 8 áp vào tỷ lệ này.

| Phá, trên bản đã viết | Kỳ vọng |
|---|---|
| Dựng `r` từ chuỗi giá đảo. Giữ `m` | F1 tụt, xoay quanh `0,5`. F5 đứng |
| Dựng volume cửa sổ từ chuỗi volume đảo. Cờ `auction` đi cùng volume của đúng cây nến. Giữ `score.liquidity` | F5 đổi dấu. Không nốt nào đổi. Đây là bằng chứng F5 đo hàm gán chữ. Cờ ở lại chỉ số cũ sẽ loại nhầm nến ATO/ATC |
| Xáo nhãn regime, tính lại `chord_bias` trên cùng hợp âm | Khi nhãn đổi, F6 của đối chứng khác F6 gốc. Lift về gần `0` chỉ khi lift gốc đang dương rõ. Thân một regime thì xáo không đổi nhãn và F6 của đối chứng là `None` |
| Hoán vị cao độ đường khâu, giữ nhịp và chỗ nghỉ | F1 và M1 của lead/support đổ |

Cách đọc dùng được là lift đổi khi nhãn thực sự đổi. Lift về gần `0` chỉ đúng khi lift gốc đang dương rõ. Trên thân ba regime, ba cụm có thể triệt tiêu nhau nên F6 gốc đã sát `0`. Xáo phá cặp, hợp âm đã chọn đắt hơn catalog, và lift âm hơn. F6 đứng yên sau khi xáo chỉ được đọc là hợp âm không phân biệt regime khi nhãn thực sự bị đổi. Thân một regime không có nhãn khác để phá cặp. Đối chứng khi đó bị bỏ, `f6` là `None`.

## 8. Luật nhận một thay đổi, chưa chạy

Bốn file trong `research/sonify/out` là nến, không phải bản đã chấm. Bốn phiên không đủ để có trung vị theo tầng character. Biên `0,02` của F1 nhỏ hơn dao động của một trung vị trên cỡ mẫu đó.

Khi rổ đóng băng có khoảng vài chục phiên mỗi character, một thay đổi của renderer được nhận nếu cả bốn điều sau đúng, trên tầng `variant × span × character`:

1. Mọi bản vẫn qua các cổng mục 6.
2. Trung vị F1 không giảm quá biên đã đăng ký trước khi chạy. F1 là tỷ lệ `0–1`. Biên `0,02` áp vào tỷ lệ đó, và chỉ được giữ nếu cỡ mẫu làm dao động của trung vị nhỏ hơn biên đó.
3. Ít nhất một trung vị khác cải thiện quá biên đã đăng ký: F3 của tập lead/support giảm, F6 tăng (hợp âm đã chọn rẻ hơn catalog hơn), hoặc M2 đỡ hơn. F5 không nằm trong danh sách này. M3 và M4 chỉ vào danh sách sau khi ngưỡng phần vị đã khóa.
4. Không có tầng nào đi ngược quá biên đó.

Trước lúc đó, giai đoạn 1 chỉ ghi, trên mỗi phiên, bản ghi sau.

## 9. Bản ghi của một phiên

- Cổng mục 6, và hai quan sát mục 6 (mode, biên giai điệu của phiên phẳng).
- F1–F6. F3 có hai số. F5 ghi rõ là kiểm tra chữ.
- M1 tách lead/support và high. M2, M3, M4 là số thô. M5 là cổng.
- Tầng: variant, span, character, số bậc thang phân biệt của `r`, số bậc của `m`, volume span ratio, số móc high.
- Bốn đối chứng mục 7, tính trên cùng `Score`. Xáo regime ghi `labels_changed`. Khi nhãn không đổi, `f6` của đối chứng là `None`. Phép thứ tư hoán vị cao độ đường khâu. Thiếu phép đó thì không còn chỗ làm F1 và M1 của lead/support đổ.
- Điểm tổng trên sheet, tính lúc mở sheet từ bốn tỷ lệ mục 1. Không ghi thêm một trường vào `DailyRecord`.

Chưa làm trong giai đoạn này: tổng có trọng số, guitar và jazz, nhịp khác `4/4`, bản `1W`–`1Y`, chấm WAV, và luật mục 8. Ô 32 của `1W`, khi tới lượt, ra khỏi F1. Ô đó cố ý lấy giá mở phiên sau.

## 10. Người đo

Người đo nghe mù, không thấy số, trên đúng rổ đóng băng.

Hai việc:

1. Gán phiên vào một trong bốn ô: tăng, giảm, ngang, đảo. Đối chiếu với F1 và F4 để biết đường khâu có đo cái tai bắt được hay không.
2. Đánh dấu ô nghe giả hoặc gãy. Chỗ nhiều người cùng đánh dấu mà vector không thấy thì thêm một chỉ số. Chỗ người nghe không đồng thuận thì để ngoài máy.

Người đo trả lời hai việc đó. Một thang 1–10 rồi hồi quy ra trọng số sẽ biến một vòng nghe thành định nghĩa của máy.
