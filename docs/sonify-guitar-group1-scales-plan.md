# Scale thật trên pattern đang bị cấm

> Tham chiếu: [`docs/sonify-guitar-scales-plan.md`](./sonify-guitar-scales-plan.md) Mục 2.1.B và 2.6, [`docs/sonify-classical-guitar.md`](./sonify-classical-guitar.md)
> Phạm vi: Villa-Lobos (`etude1`, `etude11`, `thumb_cantabile`) và Barrios (`thumb_cantabile`, `preludio` khi `_catedral_preludio` đúng). Cùng tên `thumb_cantabile` dùng bước của `ctx.ensemble`: Villa là `villa_scale_step`, Barrios là `barrios_scale_step`. `tremolo` giữ cửa cấm. Bach, Brouwer và Sor không đổi luật riêng. Preludio không khung giữ overlay Nhóm 3.

## Việc cần nghe được

Đoạn scale là dấu hiệu của một nhịp giá chạy lên hoặc chạy xuống. Người nghe nhận ra nó vì bè Cao rời pattern đang hát và chạy một câu liền bậc, một chiều, có hairpin cùng hướng với xung. Câu đó dùng đúng bước của tác giả. Pattern không bị đổi nốt bên trong lưới.

Đoạn scale là `ScalePassage` như các pattern Nhóm 3: `_line` vẽ đường, `_install_lead` đặt bè Cao, hairpin in lại sau sóng volume. Luật lực là Mục 2.6.C của plan gốc, với các cửa sổ được bổ sung ở dưới.

## Vì sao Villa-Lobos và Barrios đang im

Cửa `_touches_excluded` xóa cả passage khi `[start, target]` chạm một ô `tremolo`, `etude1`, `etude11`, `thumb_cantabile`, hoặc preludio có khung. Trên MWG ngày 28/10/2026, phiên selloff có 17 xung. Sor hát `elegiaque` và nhận 9 đoạn. Villa khóa `thumb_cantabile` và nhận 0. Barrios khóa `tremolo` và nhận 0. Chương IV của tháng: Villa là `etude1` suốt 84 ô, Barrios là `tremolo` cộng preludio, cả hai nhận 0 trong khi Sor nhận 28 đoạn.

## `tremolo` đứng ngoài

Tremolo đã là câu chạy của Barrios. Mỗi phách lặp một cao độ giá qua `p–a–m–i`. Giá đổi thì cao độ cụm đổi. `tremolo` ở lại trong `_GROUP1`. Ô phẳng `f` và `volatile` vẫn chỉ nhận `perpetual` như hiện tại. Xung nằm trọn trên tremolo không sinh passage.

## Cắt khoảng, rồi mới xét ngân sách

`_touches_excluded` hôm nay hủy cả passage khi rìa chạm một ô cấm. Một xung Sor dài, chỉ đè vài eighth của étude hoặc tremolo, mất luôn phần Nhóm 3. Luật mới cắt khoảng trước `_gap_ok` và trước khi trừ `room`.

Thứ tự, trên `[start, target]` của xung:

1. Cắt các ô `tremolo` và các ô pedal (`_PEDAL`: `intro`, `outro`, `warmup`, `cooldown`) ở hai đầu. Bỏ qua bước này thì scale rơi vào ô cửa.
2. Ô bị nhường chỉ tính trên `[start, target)`. Eighth đích đứng ngoài khoảng chiếm. `passage_eighths` là `target - start`, còn `scale_eighths` vẫn gồm eighth đích (`range(start, target + 1)`). `_touched_bars` lấy `range(start // epb, target // epb + 1)`. Khi `target` rơi đúng vạch ô, ô sau nằm trong range đó dù passage chỉ chạm eighth đích. Bước kéo ô trọn không dùng range đó và không nuốt ô chỉ chứa eighth đích. Câu này chỉ khóa ô của eighth đích lúc kéo ô trọn. Bước 4 vẫn dời `target`. Nốt đích là `ctx.melody` tại `target` sau khi khoảng đã ổn định.
3. Với mỗi đoạn pattern chủ (`etude1`, `etude11`, `thumb_cantabile`, preludio có khung) có eighth trong `[start, target)`, kéo đoạn đó vào các ô trọn. Mảnh pattern chủ không đủ một ô thì bỏ riêng mảnh đó. Vòng 16 móc kép, chùm sextuplet và khung canto không bị khoét giữa ô.
4. Ô đầu của một vùng pattern chủ liên tiếp không nằm trong passage, kể cả khi passage đã mở từ Nhóm 3 ở phía trước. Ô đó ở biên thì co biên. Ô đó ở giữa thì tách hai phía tại đầu ô đó. Phía trước còn ít nhất 2 eighth thì cắt `target` về đầu ô đó và giữ phía trước. Phía sau không thuộc passage này. Phía trước ngắn hơn 2 eighth thì bỏ phía trước và đưa `start` lên eighth đầu tiên sau ô đầu vùng. Ô đầu vẫn không thuộc passage. Phía sau còn ít nhất 2 eighth thì giữ. Cả hai phía đều ngắn hơn 2 eighth thì hủy. Co biên xong, và sau cả hai nhánh khi ô đầu nằm giữa, đều lặp bước 4, rồi bước 1, rồi bước 5, đến khi `start` và `target` không đổi. Bước 5 trong vòng lặp thấy tremolo hoặc pedal ở giữa thì hủy passage và dừng. Đây là biên để co, không phải lỗ. `_covers_group2_opening` là luật khác: hàm trả về đúng khi ô đầu vùng Nhóm 2 nằm trong khoảng, rồi `_passage_allowed` hủy cả passage, kể cả khi ô đó nằm ở biên. Ô đầu Nhóm 2 giữ đúng hàm đó. Chỉ pattern chủ được co.
5. `tremolo` hoặc pedal còn nằm giữa khoảng thì hủy cả passage. Tremolo hoặc pedal vừa bị đẩy ra rìa bởi bước 4 thì do bước 1 trong vòng lặp cắt, không do bước 5 hủy.
6. Sau khi vòng lặp đã đứng, khoảng liền còn lại ngắn hơn 2 eighth thì hủy. Bước 6 đo khoảng sau vòng lặp, không đo phía đã bỏ ở bước 4. Khoảng Nhóm 3 còn lại giữ luật overlay hiện có, kể cả khi ngắn hơn một ô, miễn cả passage còn ít nhất 2 eighth.

`passage_eighths` là `target - start` của khoảng đã cắt. `retreat_spans` được cắt theo cùng khoảng. Khoảng thở một ô đo trên khoảng này. `score` giữ nguyên score của xung giá.

Một vùng étude đã có một ô lưới, xung phủ ô trọn kế tiếp, thì ô đó được nhận. Xung chỉ ngắn hơn một ô trên chính pattern chủ thì không có passage từ mảnh đó. Câu Nhóm 3 phía trước vẫn còn nếu còn ít nhất 2 eighth. Xung Sor phủ trọn ô đầu étude rồi sang ô étude sau, mà phía trước còn ít nhất 2 eighth, thì `target` về đầu ô étude đó. Đoạn Sor còn. Ô étude sau không bị nuốt.

Với `epb = 8`, vùng `etude1` mở ở eighth 16 và xung là `[15, 40)`. Ô đầu là `[16, 24)`. Phía trước còn 1 eighth. Bước 4 bỏ phía trước, đưa `start` lên 24, và giữ `[24, 40)` vì phía sau còn 16 eighth. Ô `[16, 24)` không thuộc passage. Hai ô étude sau vẫn là chỗ scale được mở. Vòng lặp chạy lại bước 4 trên `[24, 40)` nên ô đầu của một vùng pattern phía sau cũng không nằm trong passage.

Với `epb = 8`, xung `[0, 32)`, tremolo `[8, 16)`, ô đầu étude `[16, 24)`. Phía trước dài 16 eighth nên nhánh giữ phía trước đưa `target` về 16. Khoảng `[0, 16)` còn nguyên ô tremolo ở cuối. Vòng lặp chạy bước 1 và cắt ô đó. Passage còn `[0, 8)`, phần Sor phía trước. Tremolo không được hát.

Với `epb = 8`, xung `[0, 24)`, tremolo `[8, 16)`, ô đầu étude `[16, 24)`. Ô đầu nằm ở biên cuối. Co biên đưa `target` về 16, rồi vòng lặp cắt tremolo. Passage còn `[0, 8)`.

Với `epb = 8`, xung `[0, 32)`, ô đầu étude `[0, 8)`, tremolo `[8, 16)`. Ô đầu nằm ở biên đầu. Co biên đưa `start` lên 8, rồi vòng lặp cắt tremolo. Passage còn `[16, 32)`.

## Pattern chủ nhường cả ô

Trong các ô passage chiếm, bè Cao là câu scale. Bè Trung để trống: `_rewrite_support` không trồng nốt trên bốn pattern này. Chuông đã bị gỡ bởi `bell_bars -= scale_eighths`. Đáp xuống `target` thì lưới pattern trở lại ở ô sau. Nốt đích là `ctx.melody` tại eighth đó.

`realize_scale_passage` hôm nay viết lại cả ba bè. `_rewrite_bass` xóa bass trong `[start, target)` rồi trồng gốc hoặc bậc 5 trên `ctx.strong`. `4/4` có `strong_eighths = (0, 4)`, nên đường đó đánh bass hai lần một ô và bỏ phách 2, phách 4. Bốn pattern chủ cần số lần gảy riêng. Cao độ vẫn tìm gốc hoặc bậc 5, chơi được với câu scale. Với `etude1`, `etude11` và Preludio, không còn gốc hoặc bậc 5 nào `_playable` thì `realize_scale_passage` trả `None` và passage không được nhận. Với thumb, nốt chỉ được tính là tìm thấy khi vừa `_playable` vừa có cao độ vang trong `48…64`. Sàn guitar là vang 40, và `assert_playable` nhận bass thumb tới 64, nên một nốt vang `40…47` vẫn qua cửa chơi được. Nốt đó không phải nốt gốc thumb. Hết nốt trong `48…64` thì trả `None`. `_rewrite_bass` hôm nay bỏ qua nốt không đặt được rồi vẫn nhận passage, nên ô thumb hoặc étude có thể mất bass.

- `etude1` và `etude11` chỉ được chọn ở `4/4`. `etude1`: một nốt, tấn công ở đầu ô, ngân hết `epb`. `etude11`: một nốt ở mỗi eighth `0, 2, 4, 6`, mỗi nốt ngân một phách. Lịch đó đủ cho `4/4`. Vòng sextuplet nghỉ.
- `thumb_cantabile`, cả Villa và Barrios: câu hát đang nằm ở voice 3. Giữ bass theo `_rewrite_bass` là giữ nguyên câu ngón cái. Nốt gốc thay câu đó: một nốt, tấn công ở đầu ô, ngân hết ô. Cửa sổ là cao độ vang `48…64`, tức cao độ viết `48 - semitones` … `64 - semitones` trong `_place_thumb`. Hai nốt chập phách yếu nghỉ. Câu scale hát ở bè Cao.
- Preludio có khung: bass hai ô là một nốt dài `2 * epb`, ghép từng cặp trong `_preludio_bass`. Giữ nốt đó khi cả hai ô của cặp thuộc passage và nốt còn `_playable` với câu scale. Passage chiếm một ô của cặp thì cắt nốt tại biên ô: ô trong passage lấy gốc trên phách mạnh (`ctx.strong`), ô ngoài passage giữ bass của pattern.

## Câu scale nghe ra tác giả

Hạt nốt và retreat lấy từ plan gốc. Dưới 88 BPM đi móc đơn. Từ 88 đi móc kép. Villa bước bằng `villa_scale_step` (diatonic cộng `sus2`, `add9`, `7sus4`). Dây buông của `villa_open_candidates` chỉ được thử khi câu đi móc kép. `_groups_ok` bỏ qua mọi slot có `dur16 != 1`, nên dưới 88 BPM kiểm tra đó trống và dây buông có thể lọt vào. Dưới 88, câu Villa chỉ dùng `villa_scale_step`.

Barrios bước bằng `barrios_scale_step`. Nốt dẫn nửa cung chỉ ngay trước phách mạnh hoặc trước nốt đích, đúng `barrios_chromatic_approach`.

## Hairpin theo Mục 2.6.C

Cửa sổ lấy từ pattern chiếm nhiều eighth nhất trong `[start, target)` đã cắt. Hòa thì lấy pattern tại `start`. Một ô étude nằm trong passage Sor dài vẫn dùng cửa sổ của Sor.

`etude1` và `etude11` chưa có trong `_KINETIC_PATTERNS`. Pattern không có tên lấy cửa sổ Hát `52…82`. Hai tên này vào `_KINETIC_PATTERNS`, nên cũng vào `_LOUD_DOWN_PATTERNS` vì tập đó là `_KINETIC_PATTERNS` cộng `elogio_pizz` và `bach_chaconne`. Khi passage có đa số eighth là étude, cửa sổ là Động năng `46…90`, và sóng xuống được mở tại `loud` nếu `passage.start` là phách mạnh.

`thumb_cantabile` thêm vào `_HAT_PATTERNS`. Fallback hiện đã là Hát. Ghi tên để cửa sổ không phụ thuộc vào nhánh mặc định. `preludio` đã nằm trong Hát.

Đích của ô trọn là eighth đầu ô sau, tức phách mạnh, nên `_target_is_pillar` đúng. Sóng xuống đưa cú sát đích về `soft`. Nốt đích lấy sàn `max(soft, _BASS + 2)`, không về `soft`. `_BASS` đoạn scale ghi là `60`, sàn không dưới `62`.

Thumb và Preludio là Hát. Sóng xuống mở tại `min(loud, max(prev + 8, _MELODY_APEX))`. Cửa đó chỉ thành `loud` khi `prev + 8` đã chạm `loud`.

`apply_guitar_wave` chọn nốt hát của `thumb_cantabile` ở voice `low`, rồi affine và snap vuốt voice đó. Trên ô thumb đã nhường, nốt gốc là bass. Sau sóng volume, nốt đó còn đúng velocity bass đã ghi, không bị chọn làm nốt hát. Hairpin bè Cao vẫn in lại sau sóng và gắn cờ `hairpin`, cùng đường với passage hiện có.

## Ngân sách

Bốn pattern chủ không có scale nội tại Nhóm 2, nên không cộng vào `base_intrinsic_eighths` ở bước 1. `replaced_base_intrinsic_eighths = 0`. Chi phí ở bước chọn passage là đủ `passage_eighths`. Trần 30% vẫn áp. Một chương 84 ô `etude1` có room khoảng một phần ba thân bài. Trần đó là cố ý.

Xung vừa chạm Nhóm 2 vừa chạm pattern chủ phải là cầu nối dài trên chính xung giá: `target - start ≥ epb` và `net_span ≥ 6`, đo trước khi cắt. Thiếu một trong hai thì hủy cả passage. Ô Nhóm 2 giữ bass đặc trưng của Mục 2.1.B. Ô chủ lấy bass mới ở trên. Ô đầu vùng Nhóm 2 vẫn hủy cả passage qua `_covers_group2_opening`, kể cả khi ô đó ở biên. Co biên chỉ áp cho ô đầu pattern chủ.

## Sửa trong code

`guitar_scale_passages.py`

- `_GROUP1` chỉ còn `tremolo`.
- Cắt khoảng theo mục «Cắt khoảng» trước khi tạo `ScalePassage`, trước `_gap_ok`, và trước khi trừ `room`.
- `_rewrite_bass` có nhánh số lần gảy cho bốn pattern chủ. `etude1`, `etude11` và Preludio trả `None` khi không còn gốc hoặc bậc 5 nào `_playable`. Thumb trả `None` khi không còn nốt vừa `_playable` vừa vang trong `48…64`.
- `_rewrite_support` trả support đã xóa vùng, không trồng thêm, khi ô thuộc bốn pattern chủ. Bốn pattern này đứng ngoài câu Mục 2.5 giữ một nốt bè giữa trên mỗi phách mạnh khi câu đi móc đơn.
- `_rewrite_bass` của thumb quét tới cao độ viết `64 - semitones`. Trần bass vang 53 không cắt cửa `48…64`.
- `_color_line` chỉ gọi `villa_open_candidates` khi `ctx.bpm >= SCALE_SIXTEENTH_MIN_BPM` và slot có `dur16 == 1`. Móc đơn trong thân câu dài hơn hai ô không được thử.
- `etude1` và `etude11` vào `_KINETIC_PATTERNS`. `thumb_cantabile` vào `_HAT_PATTERNS`.

`guitar_wave.py`

- Ô `thumb_cantabile` đã nằm trong `scale_eighths` không lấy voice `low` làm nốt hát của snap. Nốt gốc của ô đó giữ velocity bass đã ghi qua `_apply_affine`.

`guitar.py`, `guitar_villa.py`, `guitar_barrios.py`

- Không thêm đường đổi cao độ bên trong vòng étude, sextuplet, canto, hay ngón cái.

`guitar_patterns.py`

- Eighth thuộc `scale_eighths` tiếp tục đứng ngoài extra của `_shape_dynamics`, pickup và caesura.

## Kiểm tra

`test_group1_drops_the_whole_passage` hôm nay vừa đòi passage rỗng trên étude, thumb và preludio có khung, vừa khẳng định xung cắt qua tremolo không bị rút ngắn. Mệnh đề thứ hai đổi thành: phần Nhóm 3 còn lại được giữ. Xung `(0, 8)` trên preludio có khung có thể vẫn rỗng vì nó đè ô đầu vùng. Test xanh ở ca đó không chứng minh scale đã được mở.

Giữ: tremolo trọn ô thì passage rỗng. Preludio không khung giữ overlay cũ, xung `(0, 8)` vẫn có passage từ 0 đến 8. Bach và Brouwer đứng ngoài đợt này.

Thêm:

- Vùng pattern chủ đã có một ô lưới. Xung phủ ô trọn kế tiếp thì có passage trên ô đó. Xung ngắn hơn một ô trên chính vùng đó thì không.
- Passage Nhóm 3 chỉ chạm vài eighth étude hoặc tremolo ở rìa thì còn phần Nhóm 3, dài ít nhất 2 eighth. Xung Sor phủ trọn ô đầu étude và ô étude sau, phía trước còn ít nhất 2 eighth, thì `target` là đầu ô étude đó và đoạn Sor còn. Tremolo hoặc pedal ở giữa thì mất cả passage. Pedal ở rìa bị cắt, scale không rơi vào ô cửa.
- `epb = 8`, vùng `etude1` mở ở eighth 16, xung `[15, 40)`: passage là `[24, 40)`. Ô `[16, 24)` không thuộc passage.
- `epb = 8`, xung `[0, 32)`, tremolo `[8, 16)`, ô đầu étude `[16, 24)`: passage là `[0, 8)`. Tremolo sát trước ô đầu étude bị cắt. Phần Sor phía trước còn.
- `epb = 8`, xung `[0, 24)`, tremolo `[8, 16)`, ô đầu étude `[16, 24)`: co biên rồi vòng lặp, passage là `[0, 8)`.
- `epb = 8`, xung `[0, 32)`, ô đầu étude `[0, 8)`, tremolo `[8, 16)`: co biên rồi vòng lặp, passage là `[16, 32)`.
- `target` rơi đúng vạch ô thì ô sau không bị nhường. Nốt đích là `ctx.melody[target]`.
- Ô đầu vùng Nhóm 2 nằm trong khoảng thì cả passage bị hủy, kể cả khi ô đó ở biên. Co biên không áp cho Bach hay Brouwer.
- `thumb_cantabile` của Barrios nhận passage và bước bằng `barrios_scale_step`.
- Ô `etude1`, `etude11` hoặc Preludio không còn gốc hoặc bậc 5 nào `_playable` thì `realize_scale_passage` trả `None`. Ô thumb chỉ còn nốt vang `40…47` thì cũng trả `None`. Nốt vang `48…64` và `_playable` thì được nhận.
- Ô chủ đã nhường: bè giữa trống. Bass đúng số lần gảy — một nốt cả ô (`etude1`, thumb), một nốt mỗi phách (`etude11`), hoặc một nốt dài hai ô khi cả cặp Preludio thuộc passage. Cặp Preludio bị chiếm một ô thì ô trong passage có bass trên phách mạnh và ô ngoài giữ bass pattern.
- Nốt gốc thumb có cao độ vang trong `48…64`.
- Sóng xuống trên thumb hoặc Preludio không mở tại `loud` khi `prev` quanh `60`, và nốt đích không bằng `soft`.
- Sau `humanize(..., offset_at=lambda *_: 2)`, velocity bè Cao của étude giữ nguyên và còn cờ `hairpin`. Ca này đã có trên `study`. Lặp cho `etude1`.
- Dưới 88 BPM, câu Villa không chứa dây buông. Từ 88, dây buông chỉ vào slot móc kép. Passage étude 3 ô ở 96 BPM giữ nguyên các nốt móc đơn của 16 eighth đầu.
- Đô trưởng, hợp âm Si, `bass_high` 53: nốt gốc thumb vang 59. Rê trưởng, La thứ viết (vang thành Si thứ): nốt gốc thumb vang 59. Nốt vang `40…47` vẫn không được nhận.
- Tổng eighth scale của thân bài vẫn trong 30%. Chương toàn `etude1` có room bằng `floor(0.30 * body_eighths)`.

## Ngoài đợt này

Bộ chọn pattern theo mood giữ nguyên. Dò xung trên giá đóng, khoảng thở một ô, và hạt nốt theo `SCALE_SIXTEENTH_MIN_BPM` giữ nguyên. Nhóm 2 giữ cửa sổ nửa ô. Bach và Brouwer không thêm pattern vào đợt này.
