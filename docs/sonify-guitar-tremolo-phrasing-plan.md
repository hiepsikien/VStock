# Tremolo theo câu, và scale chỉ trên đoạn dài đã gấp

> Tham chiếu: [`docs/sonify-guitar-group1-scales-plan.md`](./sonify-guitar-group1-scales-plan.md), [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md) mục 3.0, [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md) Mục 2.1.B
> Phạm vi: thân Barrios đúng vân tay `1D`, hàng khách của chương dài, và cửa scale trên `tremolo` cùng bốn pattern chủ. Bach, Brouwer và Sor không đổi luật riêng. Villa vẫn khóa pattern cả thân theo mood. Chưa sửa code.

## Việc cần nghe được

Một ngày Barrios không còn một pattern tremolo cho cả thân. Câu thân đầu là Preludio có khung. Câu ngân sau đó là tremolo. Câu chạy khác `calm` là `choro`. Hai câu hát này đứng cạnh nhau ngay trên `1D`. Luật «không đứng cạnh» là luật phần của chương dài.

Một đoạn giá đã dài ít nhất một ô và `net_span >= 6` được nghe thành scale thật trên tremolo hoặc trên pattern chủ. Cú 2–7 eighth để pattern hát tiếp. Tremolo trượt cửa mà chỉ nằm ở rìa thì phần Nhóm 3 còn. Tremolo trượt cửa nằm giữa thì mất cả passage.

Trên chính phiên MWG này, scale mới nghe được là overlay Nhóm 3 trên câu `choro` và câu `andante`. Cửa nhường ô có thể vẫn không mở passage nào trên ngày đó.

## Vì sao bản hiện tại nghe vậy

`_assign_macro` khóa một pattern khi `ctx.bars <= 40` và không có `trio` hay `bridge`. `1D` là 34 ô, 120 BPM, `4/4`, nên `_dominant_pattern` gọi `_daily_barrios_pattern`. `rally` và `selloff` với `rel_span >= 0.014` thành tremolo cả thân. `_select_body` đã có luật theo câu. Macro ghi đè luật đó trên mọi bản `render()` có khung.

`_Ctx` không có trường span. Vân tay của lời gọi đó là `bpm == 120`, `bars == 34`, `kind == "4/4"`.

`DAILY_ENSEMBLE_SPEC` là 34 ô: warmup 2, thân 30, cooldown 2. Eighth `224–232` là ô 28, nằm trong thân 30 ô. Đo chiều 28/10/2026 từng ghi Barrios `1D` là 15 ô tremolo và 2 ô pedal. Doc dynamics ghi 29 ô tremolo trên `1D` selloff. Hai số không cùng một bài. «2 ô pedal» chỉ là pedal đầu. Cooldown thêm 2 ô. Chưa đo lại trên cùng snapshot thì chưa biến một số ô thành fixture.

Cùng snapshot chiều đó, 225 phút, đóng cửa 75,8 → 76,0, 21 xung. Villa khóa `thumb_cantabile`. 20 xung dài 2–7 eighth rơi ở bước kéo ô trọn. Một xung đúng một ô, `net_span` 19, span `224–232`, sống qua cửa cắt rồi `_assign` không vẽ được câu liền bậc trên giai điệu `74 71 65 65 67 67 65 60` rồi đích `57`. Tỷ lệ scale `1D` của cả Villa và Barrios là 0%. Snapshot đó không chứng minh scale đã mở.

Chương dài hơn 40 ô, từ hai vùng, đi `_barrios_palette` rồi `_barrios_region_patterns`. Hai phần kết ở guest đầu. Từ ba phần, phần cuối trở về pattern mở. Hàng 4/4 từ 90 đến 100 BPM, pattern mở tremolo, hiện là `tremolo`, `preludio`, `andante`. Chương I và IV của tháng MWG hôm đó là volatile 96 BPM, hai phần: tremolo rồi Preludio.

## `1D` chọn theo câu

Chỉ thân Barrios khớp `bpm == 120`, `bars == 34`, `4/4` rời nhánh một pattern. Từng câu thân lấy `_select_body`. Nhánh `bars <= 40` còn lại khóa một pattern cho cả thân. Nhánh đó không duyệt từng `regime_slot`.

Tuần một phiên là 32 ô, 90 BPM, một `regime_slot`, nên vẫn đi nhánh đó và vẫn một pattern cho cả thân. Tuần hai đến năm phiên là 64–160 ô. Barrios hơn 40 ô và từ hai vùng đi `_barrios_palette`, hàng 90–100. Hàng `tremolo`, `andante` chỉ khi pattern mở là tremolo, tức vùng đầu là `selloff`, `volatile`, hoặc finale. Tuần `calm` hoặc `rally` ở 90 BPM mở bằng Preludio. Hai phần thì vẫn Preludio, `andante`.

Thứ tự trong `_select_body`:

- Câu thân đầu, `bpm >= 90`: Preludio. Câu đó đang ngân vẫn là Preludio. `1D` có pedal, `_catedral_preludio` đúng, nên đây là lưới 16 móc kép.
- Câu có nốt giữ từ bốn móc đơn, BPM trong 90–140: tremolo. Đã có hai câu tremolo liền trước thì câu này là `andante`. `1D` không có `trio` hay `bridge`, nên không lấy `thumb_cantabile`.
- Câu chạy, mood khác `calm`, `bpm > 100`, `4/4`: `choro`.
- Câu chạy `calm`, hoặc câu còn lại: Preludio có khung.

Một phiên bán rộng vì thế nghe Preludio, tremolo, tremolo, `andante` khi các câu sau câu mở đều ngân. `rel_span` của cả ngày không còn biến mọi ô thành tremolo.

`_daily_barrios_pattern` chỉ được gọi từ nhánh vân tay trong `_dominant_pattern`. Thân `1D` không đi qua hàm đó. Hàm có thể để trong file. Không thêm một đường gọi khác.

## Cửa scale: đủ một ô, và đã gấp

Cửa áp cho mọi lần mở scale trên `tremolo`, `etude1`, `etude11`, `thumb_cantabile`, và Preludio có khung, kể cả khi xung không đụng Nhóm 2. Đo trên xung gốc, trước khi cắt: `target - start >= epb` và `net_span >= 6`. Cùng hai số với `_major_bridge`, và ở đây chúng chỉ quyết định ô tremolo cùng ô pattern chủ có được nhường hay không.

Xung qua cửa thì tremolo đi cùng vòng nhường ô với pattern chủ. Ô đầu vùng liên tiếp đứng ngoài passage. Ô đầu nằm giữa thì giữ phía trước khi phía trước còn ít nhất 2 eighth. Phía sau không thuộc passage này. Mảnh sau khi kéo không còn đủ một ô thì bỏ mảnh đó. Không nới span ra ngoài biên của chính xung. Một ô tremolo trọn giữa xung Sor là ô đầu của vùng một ô. Vòng cắt loại ô đầu trước, rồi mới xét `_blocked_inside`, nên ô đó đã ra khỏi khoảng trước khi hàm này thấy. Passage của hình `[0, 32)` với tremolo tại `[16, 24)` là đúng `[0, 16)`.

Muốn nhường tremolo thì vùng đã mở trước xung, và ô tremolo trong xung không phải ô đầu. `_blocked_inside` không hủy ô đó. Với `epb = 8`, vùng mở ở eighth 0, xung `[8, 32)`, `net_span >= 6`, `[8, 24)` vẫn tremolo và `[24, 32)` là Sor: passage là `[8, 32)`. Nếu tremolo vẫn đi lối `_GROUP1`, gọt hai đầu để lại `[24, 32)`. Nếu tremolo đã ra khỏi `_GROUP1` mà `_blocked_inside` vẫn hủy ô tremolo giữa, passage biến mất.

Xung trượt cửa:

- `tremolo` vẫn bị gọt như `_GROUP1`. Tremolo ở rìa bị cắt và phần Nhóm 3 còn. Tremolo nằm giữa thì mất cả passage.
- `etude1`, `etude11`, `thumb_cantabile`, và Preludio có khung không được nhường khi ô đó không phải ô đầu vùng, và không được phủ scale lên giữa vòng 16 móc kép, sextuplet, hay khung canto. Cửa này chỉ lộ trên ô chủ đã nằm sau ô đầu. Ô đầu vùng hôm nay đã bị bước loại ô đầu cắt ra, nên một test đè đúng ô đầu sẽ xanh trước khi luật `net_span` chạy.

Xung 2–7 eighth trên tremolo hoặc trên pattern chủ không thành passage. Bước kéo ô trọn đã chặn cú ngắn hơn một ô. Ca `net_span < 6` mà xung vẫn dài ít nhất một ô là ca cửa thứ hai phải chứng minh riêng.

Nhóm 3 giữ overlay từ 2 eighth trên Sor, `andante`, `choro`, `villa_pattern`, `chord_melody`, và Preludio không khung. Cửa một ô không áp cho các pattern đó.

Đổi pattern `1D` đưa những cú ngắn hôm nay đang nằm trên tremolo sang `choro` hoặc `andante`. Overlay từ 2 eighth áp trên hai pattern đó. Đó là scale sẽ nghe trên phiên MWG này. Cú ngắn rơi trên Preludio có khung vẫn không thành passage.

`realize_scale_passage` trả `None` khi `_line` không vẽ được câu liền bậc. `select_scale_plan` chỉ trừ `room` sau khi accept thành công. Ô MWG `74 71 65… 57` không cần luật ngân sách mới. Không nới bước hai bán cung để ép câu đó thành scale. Tỷ lệ scale `1D` của Villa và Barrios có thể vẫn là 0% sau đợt này. Passage trên ô nhường cần một fixture giá liền bậc, dài ít nhất một ô, `net_span >= 6`.

Với `epb = 8`:

- Xung `[18, 21)` trên tremolo hoặc `thumb_cantabile`: dài 3 eighth. Không qua cửa độ dài. Không có passage. Ca này không chứng minh cửa `net_span`.
- Xung `[8, 24)`, `net_span` 5, vùng `etude1` mở ở eighth 0: ô étude trong xung không phải ô đầu. Hôm nay passage là `[8, 24)`. Sau plan thì không còn passage, và không có scale giữa vòng 16 móc kép. Xung `[0, 24)` với ô étude mở ở eighth 16 đã thành `[0, 16)` bởi bước loại ô đầu, nên không chứng minh cửa này.
- Tremolo `net_span` 5 chỉ chiếm rìa `[16, 24)` của xung `[0, 24)`: gọt rìa như `_GROUP1`. Passage còn `[0, 16)`. Tremolo nằm giữa `[8, 16)` thì mất cả passage.
- Xung `[8, 40)`, `net_span` 8, vùng tremolo mở ở eighth 8: qua cửa. Ô đầu vùng là `[8, 16)`, đứng ngoài. Passage là `[16, 40)`. Nếu tremolo vẫn là `_GROUP1`, cả xung này bị gọt hết.
- Xung `[12, 22)`, `net_span` 7, cả khoảng là tremolo hoặc pattern chủ: dài hơn một ô và đã gấp, nhưng sau khi kéo ô trọn không còn một ô nguyên. Bỏ. Không kéo thành `[8, 24)`. Cùng xung trên `choro` hoặc `andante` vẫn là overlay Nhóm 3.
- Xung `[0, 32)`, `net_span` 8, một ô tremolo trọn ở `[16, 24)`: ô đó là ô đầu của vùng một ô. Passage là `[0, 16)`. Ô tremolo đứng ngoài. Phía sau không thuộc passage này. «Phía trước còn» vẫn đúng nếu passage nuốt phía sau bằng một khoảng thủng.
- Xung `[8, 32)`, `net_span` 8, vùng tremolo mở ở eighth 0, `[8, 24)` vẫn tremolo, `[24, 32)` là Sor: ô tremolo trong xung không phải ô đầu. Passage là `[8, 32)`. `_blocked_inside` không hủy. Sor, Bach, Brouwer trong bản thật không có ô tremolo. Snapshot MWG của ba nhà không bắt hai nhánh trộn này.

Trần 30% và khoảng thở một ô giữ nguyên. Hai xung cùng chiếm một ô thì xung có `score` cao hơn giữ ô đó.

## Tremolo và Preludio không đứng cạnh nhau ở chương dài

`_barrios_region_patterns` đưa phần cuối về pattern mở khi có từ ba phần. Guest cuối của các phần giữa vì thế cũng không được là pattern hát còn lại. Hàng bỏ hẳn pattern đó, không chỉ tách hai pattern bằng một ghế.

- Pattern mở là tremolo, `4/4`, `bpm > 100`: hàng là `tremolo`, `choro`, `thumb_cantabile`. Preludio không có trong chương.
- Pattern mở là Preludio, cùng cửa tempo: hàng là `preludio`, `choro`, `andante`. Tremolo không có trong chương.
- Pattern mở là `choro`, cùng cửa tempo: hàng là `choro`, `thumb_cantabile`, `andante`. Tremolo và Preludio đều không có trong chương. Đây là chủ đích của reprise, không phải tremolo còn một phần nào đó.
- `4/4` từ 90 đến 100 BPM, pattern mở là tremolo: hàng là `tremolo`, `andante`. Hai phần thành tremolo, `andante`. Ba phần thành tremolo, `andante`, tremolo.
- Cùng cửa tempo, pattern mở là Preludio: hàng là `preludio`, `andante`.

`6/8` trên 100 BPM giữ hàng điệu hiện có. Hàng đó không đặt tremolo cạnh Preludio.

Trên `1D`, câu thân đầu vẫn Preludio có khung rồi câu ngân kế là tremolo. Luật phần không sửa thứ tự `_select_body`. Câu tremolo thứ ba liền vẫn là `andante`, hoặc `thumb_cantabile` khi câu thuộc `trio` hay `bridge`.

## Giữ nguyên

- Villa vẫn một pattern cho cả thân theo mood. `selloff` vẫn `thumb_cantabile`. Cửa một ô và `net_span >= 6` là cửa scale trên ô đó.
- Ô đầu vùng pattern chủ, và ô đầu vùng tremolo khi xung đã qua cửa, không nằm trong passage.
- Bach, Brouwer, Sor, ngân sách 30%, hairpin, và bước scale của từng tác giả giữ plan đang có. Số passage của ba nhà trên cùng snapshot MWG giữ nguyên, vì bản thật của họ không có ô tremolo.
- Preludio không khung vẫn overlay Nhóm 3.
- Tuần Barrios một phiên, 32 ô, 90 BPM, giữ một pattern cho cả thân. Tuần hai đến năm phiên đi hàng 90–100 ở mục chương dài, theo pattern mở của vùng đầu.

## Sửa trong code

`guitar_patterns.py`

- Thân Barrios chỉ khi `bpm == 120`, `bars == 34`, `4/4` không lấy một pattern từ `_dominant_pattern`. Từng câu thân lấy `_select_body`. Nhánh `bars <= 40` của các bài còn lại giữ nguyên.
- Không thêm lời gọi `_daily_barrios_pattern`.
- `_barrios_palette` dùng các hàng ở mục chương dài. Hàng mở bằng `choro` không còn tremolo và không còn Preludio.

`guitar_scale_passages.py`

- Cửa `target - start >= epb` và `net_span >= 6` trên xung gốc quyết định ô `tremolo` và bốn pattern chủ có được nhường hay không, kể cả khi xung không đụng Nhóm 2. Tremolo trượt cửa ở rìa thì phần Nhóm 3 dài ít nhất 2 eighth còn. Tremolo trượt cửa ở giữa thì mất cả passage.
- Xung trượt cửa trên ô chủ không phải ô đầu: `etude1`, `etude11`, `thumb_cantabile`, và Preludio có khung không nhường, và không phủ scale giữa vòng của pattern. Vùng `etude1` mở ở eighth 0, xung `[8, 24)`, `net_span` 5, hết passage.
- Xung qua cửa: `tremolo` đi cùng vòng nhường ô với pattern chủ. Ô đầu vùng đứng ngoài. Ô đầu nằm giữa thì passage là phía trước, đúng tới đầu ô đó. Ô tremolo sau ô đầu, nằm trong cùng xung, được nhường, và `_blocked_inside` không hủy passage. Không nới span ra ngoài xung.

`docs/sonify-classical-guitar.md` mục 3.0

- Dòng `1D` của Barrios hết khóa một pattern cho cả thân. Vân tay `120 / 34 / 4/4` đi theo câu, Preludio có khung ở câu thân đầu. Tuần một phiên vẫn một pattern cho cả thân. Tuần nhiều phiên và chương 90–100 BPM viết theo hàng khách mới, và ghi pattern mở của vùng đầu.
- Bảng macro và hàng 90–100 BPM, hàng trên 100 BPM, viết lại theo hàng khách ở trên.

`docs/sonify-guitar-group1-scales-plan.md`

- `tremolo` ra khỏi `_GROUP1` chỉ khi xung gốc đã qua cửa một ô và `net_span >= 6`. Ô tremolo sau ô đầu, đã được nhường, không còn làm `_blocked_inside` hủy passage.
- Bốn pattern chủ cũng chỉ nhường ô khi xung đó qua cùng cửa. Cửa trượt thì ô chủ ở lại pattern.

## Kiểm tra

- `1D` Barrios có khung, `selloff`, `rel_span >= 0.014`, `bpm == 120`, `bars == 34`, `4/4`: câu thân đầu là Preludio lưới 16 móc kép. Câu ngân kế, giữ từ bốn móc đơn, là tremolo. Hai câu tremolo liền rồi tới `andante`. Câu chạy khác `calm` là `choro`. Fixture không khung không đủ cho ca này.
- Tuần Barrios một phiên, 32 ô, 90 BPM: một pattern cho cả thân. Tuần từ hai phiên, 90 BPM, `4/4`, vùng đầu `selloff`, `volatile`, hoặc finale: cùng hàng `tremolo`, `andante` với chương I và IV. Tuần `calm` hoặc `rally`, hai phần: Preludio, `andante`.
- Xung 3 eighth trên tremolo hoặc trên `thumb_cantabile` không có passage.
- Xung `[8, 24)`, `epb = 8`, `net_span` 5, vùng `etude1` mở ở eighth 0: không còn passage, không có scale giữa vòng 16 móc kép.
- Xung dài ít nhất một ô, `net_span < 6`, tremolo ở rìa: rìa bị gọt, phần Nhóm 3 còn. Tremolo ở giữa: không còn passage.
- Xung `[8, 40)`, `epb = 8`, `net_span >= 6`, vùng tremolo mở ở eighth 8: passage là `[16, 40)`.
- Xung `[12, 22)`, `net_span >= 6`, trên tremolo hoặc pattern chủ: không có passage và span không bị nới. Cùng xung trên `choro`: passage Nhóm 3 còn.
- Xung 3 eighth trên câu `choro` của cùng `1D`: passage còn.
- Fixture trộn, `epb = 8`, xung `[0, 32)`, `net_span >= 6`, tremolo đúng một ô tại `[16, 24)`: passage là `[0, 16)`.
- Fixture trộn, `epb = 8`, vùng tremolo mở ở eighth 0, xung `[8, 32)`, `net_span >= 6`, `[8, 24)` tremolo, `[24, 32)` Sor: passage là `[8, 32)`. Kết quả `[24, 32)` và passage rỗng đều sai.
- Fixture giá liền bậc, dài ít nhất một ô, `net_span >= 6`, trên tremolo hoặc pattern chủ: có passage trên các ô trọn phía sau ô đầu vùng.
- Ô giá nhảy quá rộng để `_line` vẽ liền bậc: `realize_scale_passage` trả `None`, và `room` không bị trừ.
- Chương 96 BPM, hai phần, pattern mở tremolo: tremolo, `andante`.
- Chương 96 BPM, ba phần, pattern mở tremolo: tremolo, `andante`, tremolo.
- Chương 96 BPM, pattern mở Preludio: không có phần tremolo.
- Chương `4/4` trên 100 BPM, pattern mở `choro`: không có phần tremolo và không có phần Preludio.
- Sor, Bach, Brouwer: cùng số passage trên cùng snapshot MWG.
